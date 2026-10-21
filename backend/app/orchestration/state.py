"""
State model for autonomous multi-stage genomic workflow orchestration.
Encapsulates pipeline execution state, stage checkpoints, retry counters, and audit data.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StageCheckpoint(BaseModel):
    """
    Checkpoint metadata for a single workflow stage.
    """
    stage_name: str
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, SKIPPED, FAILED
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    metrics: Dict[str, Any] = Field(default_factory=dict)
    warning_messages: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class WorkflowState(BaseModel):
    """
    Persistent state schema for the genomic analysis workflow graph.
    Maintained and checkpointed across all pipeline stages.
    """
    analysis_id: str
    dataset_id: str
    file_path: str
    genome_assembly: str = "GRCh38"
    status: str = "QUEUED"  # QUEUED, RUNNING, COMPLETED, COMPLETED_WITH_WARNINGS, FAILED, CANCELLED
    current_stage: str = "QUEUED"

    # Feature options
    options: Dict[str, Any] = Field(default_factory=dict)

    # Variant tracking
    variants_count: int = 0
    parsed_variant_ids: List[str] = Field(default_factory=list)

    # Stage statuses
    validation_status: str = "NOT_STARTED"
    parsing_status: str = "NOT_STARTED"
    annotation_status: str = "NOT_STARTED"
    annotated_count: int = 0
    evidence_status: str = "NOT_STARTED"
    evidence_count: int = 0
    prioritization_status: str = "NOT_STARTED"
    prioritized_count: int = 0
    explanation_status: str = "NOT_STARTED"
    explanations_count: int = 0

    # Diagnostic messages
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    error_summary: Optional[str] = None

    # Checkpointing & Retries
    stage_checkpoints: Dict[str, StageCheckpoint] = Field(default_factory=dict)
    max_retries_per_stage: int = 2
    is_cancelled: bool = False

    def get_or_create_checkpoint(self, stage_name: str) -> StageCheckpoint:
        if stage_name not in self.stage_checkpoints:
            self.stage_checkpoints[stage_name] = StageCheckpoint(stage_name=stage_name)
        return self.stage_checkpoints[stage_name]

    def record_stage_start(self, stage_name: str) -> None:
        cp = self.get_or_create_checkpoint(stage_name)
        cp.status = "IN_PROGRESS"
        cp.started_at = utc_now_iso()
        cp.error_message = None
        self.current_stage = stage_name
        self.status = "RUNNING"

    def record_stage_complete(self, stage_name: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        cp = self.get_or_create_checkpoint(stage_name)
        cp.status = "COMPLETED"
        cp.completed_at = utc_now_iso()
        cp.error_message = None
        if metrics:
            cp.metrics.update(metrics)

    def record_stage_skipped(self, stage_name: str, reason: str = "Feature disabled") -> None:
        cp = self.get_or_create_checkpoint(stage_name)
        cp.status = "SKIPPED"
        cp.completed_at = utc_now_iso()
        cp.error_message = None
        cp.metrics["skip_reason"] = reason

    def record_stage_failure(self, stage_name: str, error: str) -> None:
        cp = self.get_or_create_checkpoint(stage_name)
        cp.status = "FAILED"
        cp.completed_at = utc_now_iso()
        cp.error_message = error
        self.errors.append(f"[{stage_name}] {error}")
        self.error_summary = error

    def is_stage_completed(self, stage_name: str) -> bool:
        cp = self.stage_checkpoints.get(stage_name)
        return cp is not None and cp.status == "COMPLETED"

    def is_stage_skipped(self, stage_name: str) -> bool:
        cp = self.stage_checkpoints.get(stage_name)
        return cp is not None and cp.status == "SKIPPED"

    def is_stage_done(self, stage_name: str) -> bool:
        return self.is_stage_completed(stage_name) or self.is_stage_skipped(stage_name)
