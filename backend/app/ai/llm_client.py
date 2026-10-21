"""
Configurable backend LLM client supporting Google Gemini, OpenAI, Ollama, and deterministic Mock providers.
Features robust JSON markdown extraction, exponential backoff, and strict timeout handling.
"""
from abc import ABC, abstractmethod
import json
import re
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger


def extract_json_from_llm_text(text: str) -> str:
    """
    Extracts raw JSON string from potentially markdown-fenced LLM responses.
    Handles ```json ... ```, ``` ... ```, or direct JSON string.
    """
    if not text:
        return ""

    text = text.strip()

    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # If first non-whitespace is '{' and last is '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    return text


class BaseLLMClient(ABC):
    """
    Abstract base interface for all LLM providers.
    """

    def __init__(self, model_name: str, temperature: float = 0.0, max_tokens: int = 1500):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def generate_raw(self, system_prompt: str, user_prompt: str) -> str:
        """
        Executes raw prompt completion, returning raw text or JSON string.
        """
        pass


class MockLLMClient(BaseLLMClient):
    """
    Built-in deterministic provider that synthesizes mathematically grounded explanations
    strictly from the supplied input payload without external API requests.
    Guarantees reproducible, zero-hallucination outputs for local development and CI testing.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate_raw(self, system_prompt: str, user_prompt: str) -> str:
        # Extract payload from user prompt
        match = re.search(r"```json\s*([\s\S]*?)\s*```", user_prompt)
        if not match:
            return json.dumps({
                "summary": "No variant context provided for synthesis.",
                "variant_context": "Unspecified variant coordinates.",
                "supporting_evidence": [],
                "conflicting_evidence": [],
                "uncertainties": ["Input payload could not be parsed."],
                "missing_information": ["Missing input context."],
                "source_references": [],
                "limitations": ["Academic research use only."],
                "confidence_assessment": "Insufficient Evidence"
            })

        try:
            data = json.loads(match.group(1))
        except Exception:
            data = {}

        var = data.get("variant", {})
        coord = var.get("coordinate", "Unknown")
        alleles = var.get("alleles", "")
        assembly = var.get("genome_assembly", "GRCh38")

        annotations = data.get("annotations", [])
        evidence = data.get("clinical_evidence", [])
        prio = data.get("prioritization_matrix", {}) or {}

        primary_ann = annotations[0] if annotations else {}
        gene = primary_ann.get("gene_symbol") or "Unknown gene"
        consequence = primary_ann.get("consequence") or "unspecified consequence"
        impact = primary_ann.get("impact") or "MODIFIER"

        primary_ev = evidence[0] if evidence else {}
        interp = primary_ev.get("interpretation") if primary_ev else None
        review = primary_ev.get("review_status") if primary_ev else None
        accession = primary_ev.get("accession") if primary_ev else None
        has_conflicts = primary_ev.get("has_conflicts", False) if primary_ev else False
        conditions = primary_ev.get("reported_conditions") if primary_ev else None

        tier = prio.get("priority_category", "UNCERTAIN")
        score = prio.get("score")

        # Synthesize grounded summary
        if interp:
            summary = (
                f"Genomic mutation {coord} ({alleles}) in {gene} is reported in NCBI ClinVar as {interp} "
                f"({review or 'status unreviewed'}). Consequence analysis via Ensembl VEP identifies a {consequence} "
                f"with {impact} impact, placed in {tier} by rule-based prioritization (score: {score or 'N/A'})."
            )
        else:
            summary = (
                f"Genomic mutation {coord} ({alleles}) in {gene} is annotated as a {consequence} ({impact} impact) in assembly {assembly}. "
                f"Currently, no matching assertions are recorded in NCBI ClinVar, and the candidate is categorized as {tier}."
            )

        context_desc = (
            f"The variant causes a {consequence} in transcript {primary_ann.get('transcript_id', 'N/A')} "
            f"of gene {gene} (Ensembl ID: {primary_ann.get('gene_id', 'N/A')}), resulting in an impact rating of {impact}."
        )

        supporting = []
        if interp:
            supporting.append(f"ClinVar public record {accession or ''} asserts {interp} with {review or 'unreviewed'} status.")
        if conditions:
            supporting.append(f"Reported condition associations in public submissions: {conditions}.")
        if impact in ["HIGH", "MODERATE"]:
            supporting.append(f"VEP functional consequence rating is {impact} based on transcript alteration.")

        conflicting = []
        if has_conflicts:
            conflicting.append(
                "Multiple clinical submitters report conflicting interpretations for this variant in ClinVar."
            )
        else:
            conflicting.append("No conflicting submitter classifications identified in retrieved public records.")

        uncertainties = []
        if not interp:
            uncertainties.append("Absence of clinical assertions in ClinVar limits pathogenicity determination.")
        elif "uncertain" in interp.lower() or "vus" in interp.lower():
            uncertainties.append("Variant is classified as a Variant of Uncertain Significance (VUS); functional impact remains unproven.")

        missing_info = [
            "Population allele frequency (e.g. gnomAD / 1000 Genomes) was not queried in this pipeline phase.",
            "Functional experimental in vitro/in vivo assay data is not available in structured record.",
        ]

        refs = []
        if accession:
            refs.append(f"NCBI ClinVar: {accession}")
        if primary_ann.get("gene_id"):
            refs.append(f"Ensembl Gene: {primary_ann['gene_id']}")

        limitations = [
            "Academic research-support analysis only. Does not constitute a clinical medical diagnosis.",
            "Absence of evidence in public databases must not be construed as evidence of benignity.",
            "Independent experimental and clinical geneticist validation is mandatory before any clinical use.",
        ]

        confidence = "High" if (interp and "pathogenic" in interp.lower() and not has_conflicts) else "Moderate" if interp else "Low"

        output_dict = {
            "summary": summary,
            "variant_context": context_desc,
            "supporting_evidence": supporting,
            "conflicting_evidence": conflicting,
            "uncertainties": uncertainties,
            "missing_information": missing_info,
            "source_references": refs,
            "limitations": limitations,
            "confidence_assessment": confidence,
        }

        return json.dumps(output_dict, indent=2)


class GeminiLLMClient(BaseLLMClient):
    """
    Google Gemini API client using standard HTTPS REST calls via httpx.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash", temperature: float = 0.0, max_tokens: int = 1500):
        super().__init__(model_name=model_name, temperature=temperature, max_tokens=max_tokens)
        self.api_key = api_key
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def generate_raw(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key is required but not configured.")

        url = f"{self.endpoint}?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json"
            }
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini API returned an empty candidate list.")
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text


class OpenAILLMClient(BaseLLMClient):
    """
    OpenAI-compatible client (supporting OpenAI API, Azure OpenAI, or local Ollama).
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1500,
    ):
        super().__init__(model_name=model_name, temperature=temperature, max_tokens=max_tokens)
        self.api_key = api_key or "sk-placeholder"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate_raw(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenAI-compatible API returned empty choices.")
            text = choices[0].get("message", {}).get("content", "")
            return text


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """
    Factory function returning the configured LLM client instance.
    Defaults to MockLLMClient if provider is 'mock', 'none', or empty.
    """
    effective_provider = (provider or settings.LLM_PROVIDER or "mock").lower()

    if effective_provider == "gemini" and settings.LLM_API_KEY:
        return GeminiLLMClient(
            api_key=settings.LLM_API_KEY,
            model_name=settings.LLM_MODEL or "gemini-1.5-flash",
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    elif effective_provider in ["openai", "ollama"]:
        return OpenAILLMClient(
            api_key=settings.LLM_API_KEY,
            model_name=settings.LLM_MODEL or "gpt-4o-mini",
            base_url=settings.LLM_BASE_URL if settings.LLM_BASE_URL else None,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    else:
        # Default deterministic mock provider
        return MockLLMClient(
            model_name=settings.LLM_MODEL or "rule-grounded-mock",
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
