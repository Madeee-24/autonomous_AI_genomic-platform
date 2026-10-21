"""
Integration tests for Analysis Job Management, Background Processing, and Event Auditing.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def sample_vcf_path():
    path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test_fixtures" / "sample.vcf"
    assert path.exists(), f"Sample VCF fixture not found at {path}"
    return path


def test_create_and_run_analysis_pipeline(sample_vcf_path):
    # 1. Upload dataset first
    with open(sample_vcf_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 2. Start Analysis Job
    analysis_res = client.post(
        "/api/v1/analyses",
        json={
            "dataset_id": dataset_id,
            "genome_assembly": "GRCh38",
            "options": {
                "annotate_with_vep": False,
                "retrieve_clinvar_evidence": False,
                "generate_ai_explanations": False
            }
        }
    )
    assert analysis_res.status_code == 202
    data = analysis_res.json()
    assert "id" in data
    assert data["dataset_id"] == dataset_id
    analysis_id = data["id"]

    # 3. Poll analysis details
    get_res = client.get(f"/api/v1/analyses/{analysis_id}")
    assert get_res.status_code == 200
    job_data = get_res.json()
    # TestClient synchronously executes BackgroundTasks, so the pipeline finishes
    assert job_data["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]
    assert job_data["variants_count"] == 6

    # 4. Check audit events
    events_res = client.get(f"/api/v1/analyses/{analysis_id}/events")
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 4
    stages = [e["stage"] for e in events]
    assert "QUEUED" in stages
    assert "PARSING" in stages
    assert "FINISHED" in stages


def test_create_analysis_nonexistent_dataset():
    response = client.post(
        "/api/v1/analyses",
        json={
            "dataset_id": "nonexistent-0000-0000-0000-000000000000",
            "genome_assembly": "GRCh38"
        }
    )
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_list_analyses_endpoint():
    res = client.get("/api/v1/analyses")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert isinstance(data["items"], list)


def test_cancel_analysis_endpoint(sample_vcf_path):
    # 1. Upload dataset
    with open(sample_vcf_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample_for_cancel.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )
    dataset_id = upload_res.json()["dataset_id"]

    # 2. Inject a job in QUEUED status directly into the test database
    from app.db.session import get_db
    from app.models.analysis import AnalysisJob
    from app.repositories.analysis_repository import analysis_repo

    # Use the overridden test database session
    db = next(app.dependency_overrides[get_db]())
    queued_job = AnalysisJob(
        dataset_id=dataset_id,
        status="QUEUED",
        current_stage="QUEUED"
    )
    analysis_repo.create(db, queued_job)
    job_id = queued_job.id

    # 3. Call cancel endpoint
    cancel_res = client.post(f"/api/v1/analyses/{job_id}/cancel")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["status"] == "CANCELLED"
    assert cancel_data["current_stage"] == "CANCELLED"

    # 4. Attempting to cancel again should fail with 400
    repeat_cancel = client.post(f"/api/v1/analyses/{job_id}/cancel")
    assert repeat_cancel.status_code == 400


def test_create_and_run_analysis_with_vep_annotations(sample_vcf_path):
    from unittest.mock import patch
    from tests.unit.test_vep_client import MOCK_VEP_RESPONSE
    from app.db.session import get_db
    from app.models.annotation import Annotation
    from sqlalchemy import select

    # 1. Upload dataset
    with open(sample_vcf_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample_for_vep.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )
    dataset_id = upload_res.json()["dataset_id"]

    # 2. Start analysis with annotate_with_vep=True, mocking VEP API response
    with patch("app.bioinformatics.vep_client.EnsemblVEPClient.annotate_batch", return_value=(MOCK_VEP_RESPONSE, None)):
        analysis_res = client.post(
            "/api/v1/analyses",
            json={
                "dataset_id": dataset_id,
                "genome_assembly": "GRCh38",
                "options": {
                    "annotate_with_vep": True,
                    "retrieve_clinvar_evidence": False,
                    "generate_ai_explanations": False
                }
            }
        )

    assert analysis_res.status_code == 202
    analysis_id = analysis_res.json()["id"]

    # 3. Check status
    get_res = client.get(f"/api/v1/analyses/{analysis_id}")
    assert get_res.status_code == 200
    job_data = get_res.json()
    assert job_data["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]

    # 4. Check events for ANNOTATING stage
    events_res = client.get(f"/api/v1/analyses/{analysis_id}/events")
    events = events_res.json()
    stages = [e["stage"] for e in events]
    assert "ANNOTATING" in stages

    # 5. Check database for persisted annotations
    db = next(app.dependency_overrides[get_db]())
    annotations = list(db.scalars(select(Annotation)).all())
    assert len(annotations) > 0
    symbols = [a.gene_symbol for a in annotations if a.gene_symbol]
    assert any(s in ["TP53", "CFTR"] for s in symbols)


def test_create_and_run_analysis_with_clinvar_evidence(sample_vcf_path):
    from unittest.mock import patch
    from tests.unit.test_clinvar_client import MOCK_CLINVAR_RECORD_TP53
    from app.db.session import get_db
    from app.models.evidence import EvidenceRecord
    from sqlalchemy import select

    # 1. Upload dataset
    with open(sample_vcf_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample_for_clinvar.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )
    dataset_id = upload_res.json()["dataset_id"]

    # 2. Start analysis with retrieve_clinvar_evidence=True
    with patch("app.evidence.clinvar_client.ClinVarClient.search_variant_uids", return_value=["12374"]):
        with patch("app.evidence.clinvar_client.ClinVarClient.fetch_summaries", return_value={"12374": MOCK_CLINVAR_RECORD_TP53}):
            analysis_res = client.post(
                "/api/v1/analyses",
                json={
                    "dataset_id": dataset_id,
                    "genome_assembly": "GRCh38",
                    "options": {
                        "annotate_with_vep": False,
                        "retrieve_clinvar_evidence": True,
                        "generate_ai_explanations": False
                    }
                }
            )

    assert analysis_res.status_code == 202
    analysis_id = analysis_res.json()["id"]

    # 3. Check status
    get_res = client.get(f"/api/v1/analyses/{analysis_id}")
    assert get_res.status_code == 200
    job_data = get_res.json()
    assert job_data["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]

    # 4. Check events for RETRIEVING_EVIDENCE stage
    events_res = client.get(f"/api/v1/analyses/{analysis_id}/events")
    events = events_res.json()
    stages = [e["stage"] for e in events]
    assert "RETRIEVING_EVIDENCE" in stages

    # 5. Check database for persisted clinical evidence records
    db = next(app.dependency_overrides[get_db]())
    evidence_records = list(db.scalars(select(EvidenceRecord)).all())
    assert len(evidence_records) > 0
    assert any(e.interpretation == "Pathogenic" for e in evidence_records)
    assert any(e.source_accession == "VCV000012374" for e in evidence_records)




