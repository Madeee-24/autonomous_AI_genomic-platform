"""
Integration tests for Dataset Upload and Validation REST APIs.
"""
import io
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


def test_upload_valid_vcf(sample_vcf_path):
    with open(sample_vcf_path, "rb") as f:
        response = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("sample.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )

    assert response.status_code == 201
    data = response.json()
    assert "dataset_id" in data
    assert data["original_filename"] == "sample.vcf"
    assert data["assembly"] == "GRCh38"
    assert data["validation_summary"]["is_valid"] is True
    assert data["validation_summary"]["accepted_variants_count"] == 5

    dataset_id = data["dataset_id"]

    # Test GET dataset by ID
    get_res = client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["dataset_id"] == dataset_id
    assert get_data["file_size_bytes"] > 0

    # Test GET datasets list
    list_res = client.get("/api/v1/datasets")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(item["dataset_id"] == dataset_id for item in list_data["items"])

    # Test DELETE dataset
    del_res = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert del_res.status_code == 200

    # Ensure 404 after deletion
    after_del_res = client.get(f"/api/v1/datasets/{dataset_id}")
    assert after_del_res.status_code == 404


def test_validate_only_endpoint(sample_vcf_path):
    with open(sample_vcf_path, "rb") as f:
        response = client.post(
            "/api/v1/datasets/validate-only",
            files={"file": ("sample.vcf", f, "text/plain")},
            data={"assembly": "GRCh38"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["can_proceed_to_analysis"] is True
    assert data["validation_summary"]["is_valid"] is True
    assert data["assembly"] == "GRCh38"


def test_upload_invalid_extension():
    content = io.BytesIO(b"Not a real VCF")
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("sample.txt", content, "text/plain")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "Invalid file extension" in data["detail"]
    assert data["error_code"] == "HTTP_400"


def test_upload_empty_file():
    empty_content = io.BytesIO(b"")
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("empty.vcf", empty_content, "text/plain")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "empty" in data["detail"].lower()


def test_upload_malformed_vcf():
    malformed_content = io.BytesIO(b"This is just raw text without headers\n")
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("malformed.vcf", malformed_content, "text/plain")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "validation failed" in data["detail"].lower()

