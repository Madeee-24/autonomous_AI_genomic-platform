"""
Unit tests for Autonomous Multi-Stage Workflow Orchestration:
State management, checkpoint recovery, bounded retries, and cooperative cancellation.
"""
import uuid
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.analysis import AnalysisJob
from app.models.dataset import Dataset
from app.orchestration.stages import StageContext
from app.orchestration.state import StageCheckpoint, WorkflowState
from app.orchestration.workflow import WorkflowOrchestrator
from app.repositories.analysis_repository import analysis_repo


@pytest.fixture
def in_memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def minimal_vcf(tmp_path) -> Path:
    vcf_content = (
        "##fileformat=VCFv4.2\n"
        "##reference=GRCh38\n"
        "##contig=<ID=chr17,length=83257441>\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        "chr17\t7674220\trs121913343\tC\tT\t100\tPASS\t.\n"
    )
    vcf_path = tmp_path / "test_orchestrator.vcf"
    vcf_path.write_text(vcf_content)
    return vcf_path


def test_workflow_state_transitions():
    state = WorkflowState(
        analysis_id="job-123",
        dataset_id="ds-123",
        file_path="/tmp/test.vcf",
        genome_assembly="GRCh38",
    )
    assert state.status == "QUEUED"
    assert state.is_stage_completed("VALIDATING") is False
    assert state.is_stage_done("VALIDATING") is False

    # Start stage
    state.record_stage_start("VALIDATING")
    assert state.current_stage == "VALIDATING"
    assert state.status == "RUNNING"
    cp = state.get_or_create_checkpoint("VALIDATING")
    assert cp.status == "IN_PROGRESS"
    assert cp.started_at is not None

    # Complete stage
    state.record_stage_complete("VALIDATING", {"variants_count": 10})
    assert state.is_stage_completed("VALIDATING") is True
    assert state.is_stage_done("VALIDATING") is True
    assert cp.status == "COMPLETED"
    assert cp.metrics["variants_count"] == 10

    # Skip stage
    state.record_stage_skipped("ANNOTATING", "VEP disabled")
    assert state.is_stage_skipped("ANNOTATING") is True
    assert state.is_stage_done("ANNOTATING") is True
    assert state.stage_checkpoints["ANNOTATING"].status == "SKIPPED"

    # Failure
    state.record_stage_failure("RETRIEVING_EVIDENCE", "Network timeout")
    assert state.stage_checkpoints["RETRIEVING_EVIDENCE"].status == "FAILED"
    assert state.error_summary == "Network timeout"
    assert len(state.errors) == 1


def test_orchestrator_initialization_and_checkpoints(in_memory_db, minimal_vcf):
    dataset = Dataset(
        id=str(uuid.uuid4()),
        original_filename="test.vcf",
        stored_filename="test.vcf",
        file_size_bytes=100,
        file_checksum="dummy",
        stored_file_path=str(minimal_vcf),
        assembly="GRCh38",
        validation_status="VALID",
    )
    in_memory_db.add(dataset)

    job = AnalysisJob(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        status="QUEUED",
        current_stage="QUEUED",
        configuration_json={
            "genome_assembly": "GRCh38",
            "options": {"annotate_with_vep": False},
        },
    )
    in_memory_db.add(job)
    in_memory_db.commit()

    orch = WorkflowOrchestrator()
    loaded_state = orch.load_state_from_job(in_memory_db, job.id, str(minimal_vcf))
    assert loaded_state is not None
    assert loaded_state.analysis_id == job.id
    assert loaded_state.genome_assembly == "GRCh38"
    assert loaded_state.options == {"annotate_with_vep": False}


def test_orchestrator_full_workflow_run(in_memory_db, minimal_vcf):
    dataset = Dataset(
        id=str(uuid.uuid4()),
        original_filename="test.vcf",
        stored_filename="test.vcf",
        file_size_bytes=minimal_vcf.stat().st_size,
        file_checksum="dummy",
        stored_file_path=str(minimal_vcf),
        assembly="GRCh38",
        validation_status="VALID",
    )
    in_memory_db.add(dataset)

    job = AnalysisJob(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        status="QUEUED",
        current_stage="QUEUED",
        configuration_json={
            "genome_assembly": "GRCh38",
            "options": {
                "annotate_with_vep": False,
                "retrieve_clinvar_evidence": False,
                "generate_ai_explanations": False,
            },
        },
    )
    in_memory_db.add(job)
    in_memory_db.commit()

    orch = WorkflowOrchestrator()
    state = orch.create_initial_state(
        analysis_id=job.id,
        dataset_id=dataset.id,
        file_path=str(minimal_vcf),
        genome_assembly="GRCh38",
        options={
            "annotate_with_vep": False,
            "retrieve_clinvar_evidence": False,
            "generate_ai_explanations": False,
        },
    )

    result_state = orch.execute_workflow(in_memory_db, state)
    assert result_state.status in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]
    assert result_state.current_stage == "FINISHED"
    assert result_state.variants_count == 1
    assert result_state.is_stage_completed("VALIDATING") is True
    assert result_state.is_stage_completed("PARSING") is True
    assert result_state.is_stage_skipped("ANNOTATING") is True
    assert result_state.is_stage_skipped("RETRIEVING_EVIDENCE") is True
    assert result_state.is_stage_completed("PRIORITIZING") is True
    assert result_state.is_stage_skipped("GENERATING_EXPLANATIONS") is True


def test_orchestrator_bounded_retry_recovery(in_memory_db):
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        id=job_id,
        dataset_id="ds-1",
        status="QUEUED",
        current_stage="QUEUED",
        configuration_json={},
    )
    in_memory_db.add(job)
    in_memory_db.commit()

    state = WorkflowState(
        analysis_id=job_id,
        dataset_id="ds-1",
        file_path="/dummy/test.vcf",
        max_retries_per_stage=2,
    )

    call_count = 0

    def flaky_stage(s: WorkflowState, db, ctx):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Transient network glitch")
        s.record_stage_complete("FLAKY_STAGE")

    orch = WorkflowOrchestrator()
    success = orch._execute_stage_with_retry("FLAKY_STAGE", flaky_stage, state, in_memory_db)

    assert success is True
    assert call_count == 2
    assert state.stage_checkpoints["FLAKY_STAGE"].retry_count == 1
    assert state.is_stage_completed("FLAKY_STAGE") is True


def test_orchestrator_retry_exhaustion_aborts(in_memory_db):
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        id=job_id,
        dataset_id="ds-1",
        status="QUEUED",
        current_stage="QUEUED",
        configuration_json={},
    )
    in_memory_db.add(job)
    in_memory_db.commit()

    state = WorkflowState(
        analysis_id=job_id,
        dataset_id="ds-1",
        file_path="/dummy/test.vcf",
        max_retries_per_stage=2,
    )

    def failing_stage(s: WorkflowState, db, ctx):
        raise RuntimeError("Permanent schema incompatibility")

    orch = WorkflowOrchestrator()
    success = orch._execute_stage_with_retry("FAILING_STAGE", failing_stage, state, in_memory_db)

    assert success is False
    assert state.stage_checkpoints["FAILING_STAGE"].status == "FAILED"
    assert "Permanent schema incompatibility" in state.stage_checkpoints["FAILING_STAGE"].error_message


def test_orchestrator_cooperative_cancellation(in_memory_db, minimal_vcf):
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        id=job_id,
        dataset_id="ds-1",
        status="CANCELLED",
        current_stage="CANCELLED",
        configuration_json={},
    )
    in_memory_db.add(job)
    in_memory_db.commit()

    state = WorkflowState(
        analysis_id=job_id,
        dataset_id="ds-1",
        file_path=str(minimal_vcf),
    )

    orch = WorkflowOrchestrator()
    res = orch.execute_workflow(in_memory_db, state)

    assert res.is_cancelled is True
    assert res.status == "CANCELLED"
    # Later stages should not have run
    assert state.is_stage_completed("PARSING") is False


def test_orchestrator_resume_skips_completed_stages(in_memory_db, minimal_vcf):
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        id=job_id,
        dataset_id="ds-1",
        status="FAILED",
        current_stage="PRIORITIZING",
        configuration_json={
            "checkpoints": {
                "VALIDATING": {"stage_name": "VALIDATING", "status": "COMPLETED"},
                "PARSING": {"stage_name": "PARSING", "status": "COMPLETED"},
            }
        },
    )
    in_memory_db.add(job)
    in_memory_db.commit()

    orch = WorkflowOrchestrator()
    state = orch.load_state_from_job(in_memory_db, job_id, str(minimal_vcf))
    assert state is not None
    assert state.is_stage_completed("VALIDATING") is True
    assert state.is_stage_completed("PARSING") is True

    # Track stage executions
    executed_stages = []

    def make_tracking_stage(name):
        def stage_fn(s: WorkflowState, db, ctx):
            executed_stages.append(name)
            s.record_stage_complete(name)
        return stage_fn

    custom_pipeline = [
        ("VALIDATING", make_tracking_stage("VALIDATING")),
        ("PARSING", make_tracking_stage("PARSING")),
        ("PRIORITIZING", make_tracking_stage("PRIORITIZING")),
        ("FINALIZE", make_tracking_stage("FINALIZE")),
    ]
    orch.stage_pipeline = custom_pipeline

    orch.execute_workflow(in_memory_db, state)

    # VALIDATING and PARSING should have been skipped!
    assert "VALIDATING" not in executed_stages
    assert "PARSING" not in executed_stages
    assert "PRIORITIZING" in executed_stages
    assert "FINALIZE" in executed_stages
