"""
Unit tests for LLM client implementations, JSON extraction, and client factory.
"""
import pytest

from app.ai.llm_client import MockLLMClient, extract_json_from_llm_text, get_llm_client


def test_extract_json_from_markdown():
    markdown_wrapped = """Here is the structured JSON output:
```json
{
  "summary": "This is a valid test summary.",
  "confidence": "High"
}
```
Hope this helps!"""
    extracted = extract_json_from_llm_text(markdown_wrapped)
    assert extracted.startswith("{")
    assert extracted.endswith("}")
    assert '"confidence": "High"' in extracted


def test_extract_raw_json_without_markdown():
    raw_json = '{"key": "value"}'
    assert extract_json_from_llm_text(raw_json) == '{"key": "value"}'


@pytest.mark.asyncio
async def test_mock_llm_client_generation():
    client = MockLLMClient(model_name="test-mock")
    user_prompt = """GENOMIC VARIANT RECORD CONTEXT:
```json
{
  "variant": {
    "coordinate": "chr17:7674220",
    "alleles": "C>T",
    "genome_assembly": "GRCh38"
  },
  "annotations": [
    {
      "gene_symbol": "TP53",
      "consequence": "missense_variant",
      "impact": "HIGH"
    }
  ],
  "clinical_evidence": [
    {
      "interpretation": "Pathogenic",
      "review_status": "criteria provided, multiple submitters, no conflicts",
      "accession": "VCV000012374.5",
      "has_conflicts": false
    }
  ],
  "prioritization_matrix": {
    "priority_category": "TIER_1_CRITICAL",
    "score": 85.0
  }
}
```"""

    raw_response = await client.generate_raw(system_prompt="Test system", user_prompt=user_prompt)
    assert raw_response is not None
    import json
    data = json.loads(raw_response)
    assert "TP53" in data["summary"]
    assert "Pathogenic" in data["summary"]
    assert "TIER_1_CRITICAL" in data["summary"]
    assert data["confidence_assessment"] == "High"
    assert len(data["limitations"]) > 0


def test_get_llm_client_factory():
    client = get_llm_client("mock")
    assert client.provider_name == "mock"

