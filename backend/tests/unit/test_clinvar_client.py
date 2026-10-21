"""
Unit tests for NCBI ClinVar evidence client, record parsing, conflict detection, and caching.
"""
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.evidence.clinvar_client import ClinVarClient
from app.models.variant import Variant

# Sample synthetic ClinVar esummary JSON responses
MOCK_CLINVAR_RECORD_TP53 = {
    "uid": "12374",
    "accession": "VCV000012374",
    "title": "NM_000546.6(TP53):c.524G>A (p.Arg175His)",
    "germline_classification": {
        "description": "Pathogenic",
        "review_status": "reviewed by expert panel",
        "trait_set": [{"trait_name": "Li-Fraumeni syndrome"}]
    }
}

MOCK_CLINVAR_RECORD_CONFLICTING = {
    "uid": "99999",
    "accession": "VCV000099999",
    "title": "NM_000059.4(BRCA2):c.100A>G",
    "germline_classification": {
        "description": "Conflicting classifications of pathogenicity",
        "review_status": "criteria provided, conflicting classifications",
        "trait_set": [{"trait_name": "Hereditary breast and ovarian cancer syndrome"}]
    }
}

MOCK_CLINVAR_RECORD_BENIGN = {
    "uid": "88888",
    "accession": "VCV000088888",
    "title": "NM_001.1(GENE):c.50C>T",
    "germline_classification": {
        "description": "Benign",
        "review_status": "criteria provided, multiple submitters, no conflicts",
        "trait_set": []
    }
}


def test_parse_clinvar_pathogenic():
    client = ClinVarClient()
    evidence = client.parse_clinvar_record_to_evidence("var-123", MOCK_CLINVAR_RECORD_TP53)

    assert evidence.variant_id == "var-123"
    assert evidence.source_name == "ClinVar"
    assert evidence.source_accession == "VCV000012374"
    assert evidence.interpretation == "Pathogenic"
    assert evidence.review_status == "reviewed by expert panel"
    assert evidence.has_conflicts is False
    assert "Li-Fraumeni syndrome" in evidence.evidence_summary
    assert "https://www.ncbi.nlm.nih.gov/clinvar/variation/12374/" == evidence.source_url


def test_parse_clinvar_conflicting_assertions():
    client = ClinVarClient()
    evidence = client.parse_clinvar_record_to_evidence("var-456", MOCK_CLINVAR_RECORD_CONFLICTING)

    assert evidence.variant_id == "var-456"
    assert evidence.interpretation == "Conflicting classifications of pathogenicity"
    assert evidence.has_conflicts is True


@patch("httpx.Client.get")
def test_search_variant_uids_mock(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "esearchresult": {"idlist": ["12374", "182963"]}
    }
    mock_get.return_value = mock_resp

    client = ClinVarClient()
    uids = client.search_variant_uids("rs28934578[All Fields]")

    assert uids == ["12374", "182963"]
    assert mock_get.call_count == 1


@patch("httpx.Client.get")
def test_fetch_summaries_mock(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": {
            "uids": ["12374"],
            "12374": MOCK_CLINVAR_RECORD_TP53
        }
    }
    mock_get.return_value = mock_resp

    client = ClinVarClient()
    summaries = client.fetch_summaries(["12374"])

    assert "12374" in summaries
    assert summaries["12374"]["accession"] == "VCV000012374"


def test_retrieve_evidence_for_variants_with_cache():
    v1 = Variant(
        analysis_id="job-1",
        chromosome="chr17",
        position=7675088,
        reference_allele="C",
        alternate_allele="T",
        variant_identifier="rs28934578"
    )

    client = ClinVarClient(request_delay=0.0)

    # Mock search and fetch
    with patch.object(client, "search_variant_uids", return_value=["12374"]) as mock_search:
        with patch.object(client, "fetch_summaries", return_value={"12374": MOCK_CLINVAR_RECORD_TP53}) as mock_fetch:
            # First call -> hits search and fetch
            records, warnings = client.retrieve_evidence_for_variants([v1])
            assert len(records) == 1
            assert records[0].interpretation == "Pathogenic"
            assert mock_search.call_count == 1
            assert mock_fetch.call_count == 1

            # Second call for identical variant -> hits cache
            records_cached, _ = client.retrieve_evidence_for_variants([v1])
            assert len(records_cached) == 1
            # Call counts should remain 1 because of cache hit
            assert mock_search.call_count == 1
            assert mock_fetch.call_count == 1
