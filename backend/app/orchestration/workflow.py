"""
Autonomous Genomic Workflow Graph Orchestrator.
Manages multi-stage execution, checkpoint recovery, bounded retries, and cooperative cancellation.
"""
import time
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.orchestration.stages import (
    StageContext,
    check_for_cancellation,
    execute_annotation_stage,
    execute_evidence_stage,
    execute_explanation_stage,
    execute_finalize_stage,
    execute_parsing_stage,
    execute_prioritization_stage,
    execute_validation_stage,
)
from app.orchestration.state import StageCheckpoint, WorkflowState
from app.repositories.analysis_repository import analysis_repo


class WorkflowOrchestrator:
    """
    Coordinates multi-stage genomic workflow execution as a resilient state graph.
    """

    def __init__(self, context: Optional[StageContext] = None):
        self.context = context or StageContext()
        self.stage_pipeline = [
            ("VALIDATING", execute_validation_stage),
            ("PARSING", execute_parsing_stage),
            ("ANNOTATING", execute_annotation_stage),
            ("RETRIEVING_EVIDENCE", execute_evidence_stage),
            ("PRIORITIZING", execute_prioritization_stage),
            ("GENERATING_EXPLANATIONS", execute_explanation_stage),
            ("FINALIZE", execute_finalize_stage),
        ]

    def execute_workflow(self, db: Session, state: WorkflowState) -> WorkflowState:
        """
        Executes or resumes the genomic analysis workflow graph.
        """
        logger.info(f"Initiating autonomous workflow execution for job: {state.analysis_id}")

        for stage_name, stage_fn in self.stage_pipeline:
            # 1. Cooperative cancellation check
            if check_for_cancellation(state, db):
                logger.info(f"[{state.analysis_id}] Pipeline halted due to cancellation before stage '{stage_name}'.")
                self._persist_state_checkpoints(db, state)
                return state

            # 2. Check if stage was already completed or skipped in prior run (Resume logic)
            if state.is_stage_done(stage_name):
                logger.info(f"[{state.analysis_id}] Stage '{stage_name}' already verified done; advancing.")
                continue

            # 3. Execute stage with bounded retry policy
            success = self._execute_stage_with_retry(
                stage_name=stage_name,
                stage_fn=stage_fn,
                state=state,
                db=db
            )

            # Persist checkpoint state to DB after each stage
            self._persist_state_checkpoints(db, state)

            if not success:
                if state.is_cancelled:
                    logger.info(f"[{state.analysis_id}] Pipeline execution cancelled during stage '{stage_name}'.")
                    return state

                logger.error(f"[{state.analysis_id}] Pipeline aborted at stage '{stage_name}'.")
                state.status = "FAILED"
                state.current_stage = stage_name
                analysis_repo.update_status(
                    db,
                    job_id=state.analysis_id,
                    status="FAILED",
                    current_stage=stage_name,
                    error_code="STAGE_EXECUTION_FAILURE",
                    error_summary=state.error_summary or f"Failure in stage {stage_name}"
                )
                analysis_repo.add_event(
                    db, job_id=state.analysis_id, stage=stage_name, event_type="JOB_FAILED",
                    message=f"Pipeline aborted: {state.error_summary}"
                )
                return state

        return state

    def _execute_stage_with_retry(
        self,
        stage_name: str,
        stage_fn: Callable[[WorkflowState, Session, StageContext], None],
        state: WorkflowState,
        db: Session
    ) -> bool:
        """
        Executes a stage function with bounded exponential retries on transient errors.
        """
        checkpoint = state.get_or_create_checkpoint(stage_name)
        max_retries = state.max_retries_per_stage
        attempt = 0

        while attempt <= max_retries:
            # Check cancellation before attempt
            if check_for_cancellation(state, db):
                return False

            try:
                stage_fn(state, db, self.context)
                return True
            except Exception as exc:
                if check_for_cancellation(state, db):
                    return False

                attempt += 1
                checkpoint.retry_count = attempt
                err_msg = f"Attempt {attempt}/{max_retries + 1} failed: {type(exc).__name__}: {str(exc)}"
                logger.warning(f"[{state.analysis_id}][{stage_name}] {err_msg}")

                if attempt <= max_retries:
                    analysis_repo.add_event(
                        db, job_id=state.analysis_id, stage=stage_name, event_type="STAGE_RETRY",
                        message=f"Transient failure in {stage_name}; executing bounded retry {attempt}/{max_retries}.",
                        details={"error": str(exc), "retry_attempt": attempt}
                    )
                    time.sleep(0.5 * attempt)
                else:
                    state.record_stage_failure(stage_name, str(exc))
                    return False

        return False

    def _persist_state_checkpoints(self, db: Session, state: WorkflowState) -> None:
        """
        Persists stage checkpoint map into AnalysisJob configuration for recovery.
        """
        try:
            job = analysis_repo.get(db, state.analysis_id)
            if job:
                cfg = dict(job.configuration_json or {})
                checkpoints_dict = {
                    k: v.model_dump() for k, v in state.stage_checkpoints.items()
                }
                cfg["checkpoints"] = checkpoints_dict
                job.configuration_json = cfg
                db.commit()
        except Exception as e:
            logger.warning(f"Could not persist checkpoints for job {state.analysis_id}: {e}")

    def create_initial_state(
        self,
        analysis_id: str,
        dataset_id: str,
        file_path: str,
        genome_assembly: str,
        options: Dict[str, Any]
    ) -> WorkflowState:
        """
        Initializes fresh workflow state.
        """
        return WorkflowState(
            analysis_id=analysis_id,
            dataset_id=dataset_id,
            file_path=file_path,
            genome_assembly=genome_assembly,
            options=options,
            status="QUEUED",
            current_stage="QUEUED",
        )

    def load_state_from_job(
        self,
        db: Session,
        job_id: str,
        file_path: str
    ) -> Optional[WorkflowState]:
        """
        Reconstructs workflow state and completed checkpoints from database record for resume/recovery.
        """
        job = analysis_repo.get(db, job_id)
        if not job:
            return None

        cfg = job.configuration_json or {}
        options = cfg.get("options", {})
        assembly = cfg.get("genome_assembly", "GRCh38")

        raw_checkpoints = cfg.get("checkpoints", {})
        parsed_checkpoints = {}
        for k, v in raw_checkpoints.items():
            try:
                parsed_checkpoints[k] = StageCheckpoint(**v)
            except Exception:
                pass

        state = WorkflowState(
            analysis_id=job.id,
            dataset_id=job.dataset_id,
            file_path=file_path,
            genome_assembly=assembly,
            options=options,
            status=job.status,
            current_stage=job.current_stage,
            stage_checkpoints=parsed_checkpoints,
        )
        return state


orchestrator = WorkflowOrchestrator()
