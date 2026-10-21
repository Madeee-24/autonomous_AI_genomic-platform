"""
Unit tests for SQLAlchemy entity models and relationships.
"""
from datetime import datetime
import pytest

from app.models.ai import AIExplanation
from app.models.analysis import AnalysisJob, WorkflowEvent
from app.models.annotation import Annotation
from app.models.dataset import Dataset
from app.models.evidence import EvidenceRecord
from app.models.prioritization import PrioritizationResult
from app.models.report import Report
from app.models.user import User
from app.models.variant import Variant


def test_user_model_initialization():
    user = User(
        email="researcher@genomics.org",
        password_hash="argon2_hashed_secret",
        full_name="Dr. Jane Doe"
    )
    assert user.email == "researcher@genomics.org"
    assert user.is_active is True
    assert len(user.id) == 36


def test_dataset_model_initialization():
    dataset = Dataset(
        original_filename="sample.vcf",
        stored_filename="uuid_sample.vcf",
        stored_file_path="/data/uploads/uuid_sample.vcf",
        file_checksum="a2b797122657aaafa4346cffa55b5d6adc59c844c5fca03ac5b7c03c288827b6",
        file_size_bytes=1133,
        assembly="GRCh38",
        validation_status="VALID"
    )
    assert dataset.assembly == "GRCh38"
    assert dataset.file_size_bytes == 1133
    assert len(dataset.file_checksum) == 64


def test_analysis_job_initialization():
    job = AnalysisJob(
        dataset_id="test-dataset-id",
        status="QUEUED",
        current_stage="VALIDATION"
    )
    assert job.status == "QUEUED"
    assert job.current_stage == "VALIDATION"


def test_variant_and_annotation_model():
    variant = Variant(
        analysis_id="test-analysis-id",
        chromosome="chr7",
        position=117559590,
        reference_allele="ATCT",
        alternate_allele="A",
        variant_identifier="rs113993960",
        variant_type="DELETION",
        quality=999.0
    )
    assert variant.chromosome == "chr7"
    assert variant.position == 117559590

    annotation = Annotation(
        variant_id=variant.id,
        gene_symbol="CFTR",
        consequence="frameshift_variant",
        impact="HIGH",
        annotation_source="Ensembl VEP"
    )
    assert annotation.gene_symbol == "CFTR"
    assert annotation.impact == "HIGH"

