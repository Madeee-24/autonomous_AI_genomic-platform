"""
AI and LLM integration package for evidence-grounded genomic variant explanations.
"""
from app.ai.explanation_service import ExplanationService, explanation_service
from app.ai.llm_client import BaseLLMClient, GeminiLLMClient, MockLLMClient, OpenAILLMClient, get_llm_client
from app.ai.output_validation import ExplanationGenerationResult, VariantExplanationOutput
from app.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_variant_explanation_prompt

__all__ = [
    "BaseLLMClient",
    "ExplanationGenerationResult",
    "ExplanationService",
    "GeminiLLMClient",
    "MockLLMClient",
    "OpenAILLMClient",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "VariantExplanationOutput",
    "build_variant_explanation_prompt",
    "explanation_service",
    "get_llm_client",
]

