"""
Integration tests for Database Repositories and CRUD persistence.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.analysis import AnalysisJob
from app.models.annotation import Annotation
from app.models.dataset import Dataset
from app.models.evidence import EvidenceRecord
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant
from app.repositories.analysis_repository import analysis_repo
from app.repositories.dataset_repository import dataset_repo
from app.repositories.variant_repository import variant_repo


@pytest.fixture
def db_session():
    """
    Creates an isolated in-memory SQLite database for testing repository operations.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


def test_dataset_repository_crud(db_session: Session):
    dataset = Dataset(
        original_filename="sample.vcf",
        stored_filename="uuid_sample.vcf",
        stored_file_path="/data/uploads/uuid_sample.vcf",
        file_checksum="test_checksum_12345",
        file_size_bytes=2048,
        assembly="GRCh38",
        validation_status="VALID",
        validation_summary_json={"accepted_variants": 5}
    )

    created = dataset_repo.create(db_session, dataset)
    assert created.id is not None

    # Query by ID
    fetched = dataset_repo.get(db_session, created.id)
    assert fetched is not None
    assert fetched.original_filename == "sample.vcf"

    # Query by Checksum
    by_hash = dataset_repo.get_by_checksum(db_session, "test_checksum_12345")
    assert by_hash is not None
    assert by_hash.id == created.id

    assert dataset_repo.count(db_session) == 1

    # Delete
    deleted = dataset_repo.delete(db_session, created.id)
    assert deleted is True
    assert dataset_repo.count(db_session) == 0


def test_analysis_repository_workflow(db_session: Session):
    # 1. Create parent dataset
    dataset = dataset_repo.create(
        db_session,
        Dataset(
            original_filename="patient_sample.vcf",
            stored_filename="stored_patient.vcf",
            stored_file_path="/data/uploads/stored_patient.vcf",
            file_checksum="checksum_abc",
            file_size_bytes=5000,
            assembly="GRCh38",
            validation_status="VALID"
        )
    )

    # 2. Create Analysis Job
    job = analysis_repo.create(
        db_session,
        AnalysisJob(
            dataset_id=dataset.id,
            status="QUEUED",
            current_stage="INGESTION"
        )
    )
    assert job.id is not None
    assert job.status == "QUEUED"

    # 3. Update status & transitions
    updated = analysis_repo.update_status(
        db_session,
        job.id,
        status="RUNNING",
        current_stage="ANNOTATING"
    )
    assert updated.status == "RUNNING"
    assert updated.started_at is not None

    # 4. Add Workflow Events
    event1 = analysis_repo.add_event(
        db_session,
        job.id,
        stage="PARSING",
        event_type="STAGE_COMPLETED",
        message="5 variants parsed successfully",
        details={"variants_count": 5}
    )
    assert event1.id is not None

    events = analysis_repo.get_events(db_session, job.id)
    assert len(events) == 1
    assert events[0].stage == "PARSING"


def test_variant_repository_bulk_and_queries(db_session: Session):
    # 1. Create dataset and analysis
    dataset = dataset_repo.create(
        db_session,
        Dataset(
            original_filename="cohort.vcf",
            stored_filename="stored_cohort.vcf",
            stored_file_path="/data/uploads/cohort.vcf",
            file_checksum="chk_123",
            file_size_bytes=1000,
            assembly="GRCh38",
            validation_status="VALID"
        )
    )
    job = analysis_repo.create(
        db_session,
        AnalysisJob(dataset_id=dataset.id, status="RUNNING", current_stage="PARSING")
    )

    # 2. Bulk insert variants
    var1 = Variant(
        analysis_id=job.id,
        chromosome="chr7",
        position=117559590,
        reference_allele="ATCT",
        alternate_allele="A",
        variant_identifier="rs113993960",
        variant_type="DELETION",
        quality=999.0
    )
    var2 = Variant(
        analysis_id=job.id,
        chromosome="chr13",
        position=32338763,
        reference_allele="G",
        alternate_allele="A",
        variant_identifier="rs80359550",
        variant_type="SNV",
        quality=999.0
    )

    count = variant_repo.bulk_create(db_session, [var1, var2])
    assert count == 2

    # 3. Add Annotation to var1
    db_session.add(
        Annotation(
            variant_id=var1.id,
            gene_symbol="CFTR",
            consequence="inframe_deletion",
            impact="MODERATE",
            annotation_source="Ensembl VEP"
        )
    )
    db_session.commit()

    # 4. Query variants by analysis with eager load
    variants, total = variant_repo.get_by_analysis(db_session, job.id)
    assert total == 2
    assert len(variants) == 2

    # Verify eager loaded annotations
    v1_loaded = next(v for v in variants if v.chromosome == "chr7")
    assert len(v1_loaded.annotations) == 1
    assert v1_loaded.annotations[0].gene_symbol == "CFTR"

    # Query with chromosome filter
    chr7_variants, chr7_total = variant_repo.get_by_analysis(db_session, job.id, chromosome="chr7")
    assert chr7_total == 1
    assert chr7_variants[0].chromosome == "chr7"
