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


def test_create_and_run_analysis_with_prioritization(sample_vcf_path):
    from unittest.mock import patch
    from tests.unit.test_vep_client import MOCK_VEP_RESPONSE
    from tests.unit.test_clinvar_client import MOCK_CLINVAR_RECORD_TP53
    from app.db.session import get_db
    from app.models.prioritization import PrioritizationResult
    from sqlalchemy import select

    # 1. Upload dataset
    with open(sample_vcf_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample_for_prio.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )
    dataset_id = upload_res.json()["dataset_id"]

    # 2. Run analysis with both VEP and ClinVar enabled
    with patch("app.bioinformatics.vep_client.EnsemblVEPClient.annotate_batch", return_value=(MOCK_VEP_RESPONSE, None)):
        with patch("app.evidence.clinvar_client.ClinVarClient.search_variant_uids", return_value=["12374"]):
            with patch("app.evidence.clinvar_client.ClinVarClient.fetch_summaries", return_value={"12374": MOCK_CLINVAR_RECORD_TP53}):
                analysis_res = client.post(
                    "/api/v1/analyses",
                    json={
                        "dataset_id": dataset_id,
                        "genome_assembly": "GRCh38",
                        "options": {
                            "annotate_with_vep": True,
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
    assert get_res.json()["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]

    # 4. Check events for PRIORITIZING stage
    events_res = client.get(f"/api/v1/analyses/{analysis_id}/events")
    stages = [e["stage"] for e in events_res.json()]
    assert "PRIORITIZING" in stages

    # 5. Check database for persisted PrioritizationResult records
    db = next(app.dependency_overrides[get_db]())
    prio_results = list(db.scalars(select(PrioritizationResult)).all())
    assert len(prio_results) > 0

    # Ensure tier 1 critical variant is recognized
    categories = [p.priority_category for p in prio_results]
    assert "TIER_1_CRITICAL" in categories

    # 6. Test Dashboard Summary Endpoint
    dash_res = client.get("/api/v1/analyses/dashboard/summary")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["total_datasets"] >= 1
    assert dash_data["total_analyses"] >= 1
    assert dash_data["completed_analyses"] >= 1
    assert "TIER_1_CRITICAL" in dash_data["tier_distribution"]

    # 7. Test Analysis Statistics Endpoint
    stats_res = client.get(f"/api/v1/analyses/{analysis_id}/statistics")
    assert stats_res.status_code == 200
    stats_data = stats_res.json()
    assert stats_data["total_variants"] > 0
    assert stats_data["annotated_variants"] > 0
    assert stats_data["prioritized_variants"] > 0
    assert "TIER_1_CRITICAL" in stats_data["tier_counts"]

    # 8. Test Analysis Variants List with Filtering & Pagination
    variants_res = client.get(f"/api/v1/analyses/{analysis_id}/variants?page=1&page_size=10")
    assert variants_res.status_code == 200
    var_data = variants_res.json()
    assert var_data["total"] > 0
    assert len(var_data["items"]) > 0

    first_variant = var_data["items"][0]
    variant_id = first_variant["id"]
    assert "chromosome" in first_variant
    assert "priority_category" in first_variant

    # Test filter by chromosome
    chr_res = client.get(f"/api/v1/analyses/{analysis_id}/variants?chromosome={first_variant['chromosome']}")
    assert chr_res.status_code == 200
    assert all(item["chromosome"] == first_variant["chromosome"] for item in chr_res.json()["items"])

    # Test single variant detail endpoint
    detail_res = client.get(f"/api/v1/analyses/{analysis_id}/variants/{variant_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == variant_id
    assert "annotations" in detail_data
    assert "evidence_records" in detail_data
    assert "prioritization" in detail_data

    # 9. Test On-Demand Explain Variant Endpoint
    explain_res = client.post(f"/api/v1/analyses/{analysis_id}/variants/{variant_id}/explain")
    assert explain_res.status_code == 200
    exp_data = explain_res.json()
    assert exp_data["validation_status"] == "VALID"
    assert "explanation_text" in exp_data
    assert exp_data["structured_output"] is not None
    assert "confidence_assessment" in exp_data["structured_output"]

    # 10. Test Get Stored AI Explanation
    get_exp_res = client.get(f"/api/v1/analyses/{analysis_id}/variants/{variant_id}/explanation")
    assert get_exp_res.status_code == 200
    assert get_exp_res.json()["id"] == exp_data["id"]


def test_create_and_run_analysis_with_ai_explanations(sample_vcf_path):
    from unittest.mock import patch
    from tests.unit.test_vep_client import MOCK_VEP_RESPONSE
    from tests.unit.test_clinvar_client import MOCK_CLINVAR_RECORD_TP53
    from app.db.session import get_db
    from app.models.ai import AIExplanation
    from sqlalchemy import select

    with open(sample_vcf_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample_for_ai.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )
    dataset_id = upload_res.json()["dataset_id"]

    with patch("app.bioinformatics.vep_client.EnsemblVEPClient.annotate_batch", return_value=(MOCK_VEP_RESPONSE, None)):
        with patch("app.evidence.clinvar_client.ClinVarClient.search_variant_uids", return_value=["12374"]):
            with patch("app.evidence.clinvar_client.ClinVarClient.fetch_summaries", return_value={"12374": MOCK_CLINVAR_RECORD_TP53}):
                analysis_res = client.post(
                    "/api/v1/analyses",
                    json={
                        "dataset_id": dataset_id,
                        "genome_assembly": "GRCh38",
                        "options": {
                            "annotate_with_vep": True,
                            "retrieve_clinvar_evidence": True,
                            "generate_ai_explanations": True
                        }
                    }
                )

    assert analysis_res.status_code == 202
    analysis_id = analysis_res.json()["id"]

    get_res = client.get(f"/api/v1/analyses/{analysis_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]

    events_res = client.get(f"/api/v1/analyses/{analysis_id}/events")
    stages = [e["stage"] for e in events_res.json()]
    assert "GENERATING_EXPLANATIONS" in stages

    db = next(app.dependency_overrides[get_db]())
    ai_explanations = list(db.scalars(select(AIExplanation)).all())
    assert len(ai_explanations) > 0
    assert any(exp.validation_status == "VALID" for exp in ai_explanations)





