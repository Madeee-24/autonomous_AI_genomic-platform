"""
Integration tests for PDF Report Generation, Listing, and Streaming Download Endpoints.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.analysis import AnalysisJob
from app.models.dataset import Dataset
from app.repositories.analysis_repository import analysis_repo

client = TestClient(app)


@pytest.fixture
def sample_vcf_path():
    path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test_fixtures" / "sample.vcf"
    assert path.exists(), f"Sample VCF fixture not found at {path}"
    return path


@pytest.fixture
def completed_analysis(sample_vcf_path):
    # 1. Upload dataset
    with open(sample_vcf_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample_for_report.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"},
        )
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["dataset_id"]

    # 2. Run analysis
    analysis_res = client.post(
        "/api/v1/analyses",
        json={
            "dataset_id": dataset_id,
            "genome_assembly": "GRCh38",
            "options": {
                "annotate_with_vep": False,
                "retrieve_clinvar_evidence": False,
                "generate_ai_explanations": False,
            },
        },
    )
    assert analysis_res.status_code == 202
    analysis_id = analysis_res.json()["id"]

    # Verify completed
    get_res = client.get(f"/api/v1/analyses/{analysis_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] in ["COMPLETED", "COMPLETED_WITH_WARNINGS"]

    return analysis_id


def test_generate_report_endpoint(completed_analysis):
    res = client.post(f"/api/v1/analyses/{completed_analysis}/reports")
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["analysis_id"] == completed_analysis
    assert data["report_status"] == "GENERATED"
    assert data["file_size_bytes"] > 0
    assert "download_url" in data


def test_list_reports_endpoint(completed_analysis):
    # Ensure at least one report generated
    client.post(f"/api/v1/analyses/{completed_analysis}/reports")

    res = client.get(f"/api/v1/analyses/{completed_analysis}/reports")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_download_report_by_id(completed_analysis):
    gen_res = client.post(f"/api/v1/analyses/{completed_analysis}/reports")
    report_id = gen_res.json()["id"]

    download_res = client.get(f"/api/v1/reports/{report_id}/download")
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/pdf"
    assert "attachment" in download_res.headers["content-disposition"]
    assert download_res.content.startswith(b"%PDF-")


def test_download_latest_report(completed_analysis):
    download_res = client.get(f"/api/v1/analyses/{completed_analysis}/report/download")
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/pdf"
    assert download_res.content.startswith(b"%PDF-")


def test_generate_report_incomplete_analysis_fails():
    db = next(app.dependency_overrides[get_db]())
    job = AnalysisJob(
        dataset_id="dummy-ds",
        status="RUNNING",
        current_stage="PARSING",
    )
    analysis_repo.create(db, job)

    res = client.post(f"/api/v1/analyses/{job.id}/reports")
    assert res.status_code == 400
    assert "must be completed" in res.json()["detail"].lower()


def test_generate_report_nonexistent_job():
    res = client.post("/api/v1/analyses/00000000-0000-0000-0000-000000000000/reports")
    assert res.status_code == 404

