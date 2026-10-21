"""
Unit tests for Ensembl VEP client, coordinate formatting, response parsing, and rate limiting.
"""
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.bioinformatics.vep_client import (
    EnsemblVEPClient,
    format_variant_for_vep
)
from app.models.variant import Variant

# Sample synthetic Ensembl VEP JSON response
MOCK_VEP_RESPONSE = [
    {
        "input": "17 7675088 7675088 C/T + rs28934578",
        "id": "rs28934578",
        "seq_region_name": "17",
        "start": 7675088,
        "end": 7675088,
        "allele_string": "C/T",
        "most_severe_consequence": "missense_variant",
        "transcript_consequences": [
            {
                "canonical": 1,
                "gene_id": "ENSG00000141510",
                "gene_symbol": "TP53",
                "transcript_id": "ENST00000269305",
                "impact": "MODERATE",
                "consequence_terms": ["missense_variant"],
                "sift_prediction": "deleterious",
                "sift_score": 0.01,
                "polyphen_prediction": "probably_damaging",
                "polyphen_score": 0.98
            }
        ]
    },
    {
        "input": "7 117559590 117559593 ATCT/A + rs113993960",
        "id": "rs113993960",
        "seq_region_name": "7",
        "start": 117559590,
        "end": 117559593,
        "allele_string": "ATCT/A",
        "most_severe_consequence": "frameshift_variant",
        "transcript_consequences": [
            {
                "canonical": 1,
                "gene_id": "ENSG00000001626",
                "gene_symbol": "CFTR",
                "transcript_id": "ENST00000003084",
                "impact": "HIGH",
                "consequence_terms": ["frameshift_variant"]
            }
        ]
    }
]


def test_format_variant_for_vep_snv():
    vep_str, lookup_id = format_variant_for_vep("chr17", 7675088, "C", "T", "rs28934578")
    assert vep_str == "17 7675088 7675088 C/T + rs28934578"
    assert lookup_id == "rs28934578"


def test_format_variant_for_vep_deletion():
    vep_str, lookup_id = format_variant_for_vep("chr7", 117559590, "ATCT", "A", "rs113993960")
    assert vep_str == "7 117559590 117559593 ATCT/A + rs113993960"
    assert lookup_id == "rs113993960"


def test_parse_vep_record_to_annotation():
    client = EnsemblVEPClient()
    raw_record = MOCK_VEP_RESPONSE[0]
    annotation = client.parse_vep_record_to_annotation("test-var-id-1", raw_record)

    assert annotation.variant_id == "test-var-id-1"
    assert annotation.gene_symbol == "TP53"
    assert annotation.gene_id == "ENSG00000141510"
    assert annotation.transcript_id == "ENST00000269305"
    assert annotation.consequence == "missense_variant"
    assert annotation.impact == "MODERATE"
    assert annotation.annotation_source == "Ensembl VEP"


@patch("httpx.Client.post")
def test_annotate_batch_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_VEP_RESPONSE
    mock_post.return_value = mock_resp

    client = EnsemblVEPClient()
    results, error = client.annotate_batch(["17 7675088 7675088 C/T + rs28934578"])

    assert error is None
    assert len(results) == 2
    assert results[0]["gene_symbol_hint"] if "gene_symbol_hint" in results[0] else results[0]["most_severe_consequence"] == "missense_variant"


@patch("httpx.Client.post")
def test_annotate_batch_rate_limit_recovery(mock_post):
    rate_limited_resp = MagicMock()
    rate_limited_resp.status_code = 429
    rate_limited_resp.headers = {"Retry-After": "0.01"}

    success_resp = MagicMock()
    success_resp.status_code = 200
    success_resp.json.return_value = [MOCK_VEP_RESPONSE[0]]

    # First call returns 429, second returns 200
    mock_post.side_effect = [rate_limited_resp, success_resp]

    client = EnsemblVEPClient()
    results, error = client.annotate_batch(["17 7675088 7675088 C/T + rs28934578"])

    assert error is None
    assert len(results) == 1
    assert mock_post.call_count == 2


@patch("httpx.Client.post")
def test_annotate_batch_timeout_graceful_failure(mock_post):
    mock_post.side_effect = httpx.TimeoutException("Connection timed out")

    client = EnsemblVEPClient(max_retries=1)
    results, error = client.annotate_batch(["17 7675088 7675088 C/T + rs28934578"])

    assert results == []
    assert error is not None
    assert "failed after 1 attempts" in error


def test_annotate_variants_mapping():
    v1 = Variant(
        analysis_id="job-1",
        chromosome="chr17",
        position=7675088,
        reference_allele="C",
        alternate_allele="T",
        variant_identifier="rs28934578"
    )
    v2 = Variant(
        analysis_id="job-1",
        chromosome="chr7",
        position=117559590,
        reference_allele="ATCT",
        alternate_allele="A",
        variant_identifier="rs113993960"
    )

    client = EnsemblVEPClient()
    # Mock annotate_batch to return predefined annotations
    with patch.object(client, "annotate_batch", return_value=(MOCK_VEP_RESPONSE, None)):
        annotations, warnings = client.annotate_variants([v1, v2], assembly="GRCh38")

    assert len(warnings) == 0
    assert len(annotations) == 2

    a_tp53 = next(a for a in annotations if a.variant_id == v1.id)
    assert a_tp53.gene_symbol == "TP53"
    assert a_tp53.consequence == "missense_variant"
    assert a_tp53.impact == "MODERATE"

    a_cftr = next(a for a in annotations if a.variant_id == v2.id)
    assert a_cftr.gene_symbol == "CFTR"
    assert a_cftr.consequence == "frameshift_variant"
    assert a_cftr.impact == "HIGH"

