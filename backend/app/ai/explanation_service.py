"""
AI Explanation Service: Orchestrates evidence-grounded synthesis, structured validation,
and database persistence into AIExplanation entities.
"""
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.llm_client import BaseLLMClient, extract_json_from_llm_text, get_llm_client
from app.ai.output_validation import ExplanationGenerationResult, VariantExplanationOutput
from app.ai.prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_variant_explanation_prompt
from app.core.logging import logger
from app.models.ai import AIExplanation
from app.models.variant import Variant


class ExplanationService:
    """
    Manages the lifecycle of AI-assisted variant explanations.
    """

    def __init__(self, client: Optional[BaseLLMClient] = None):
        self._client = client

    @property
    def client(self) -> BaseLLMClient:
        if self._client is None:
            self._client = get_llm_client()
        return self._client

    async def generate_variant_explanation(
        self,
        db: Session,
        variant: Variant,
        genome_assembly: str = "GRCh38",
        persist: bool = True
    ) -> ExplanationGenerationResult:
        """
        Generates an evidence-grounded scientific explanation for a single genomic variant.
        Validates against Pydantic schema and optionally saves to the database.
        """
        # 1. Prepare de-identified evidence references
        annotations_data = [
            {
                "id": a.id,
                "gene_symbol": a.gene_symbol,
                "gene_id": a.gene_id,
                "transcript_id": a.transcript_id,
                "consequence": a.consequence,
                "impact": a.impact,
                "annotation_source": a.annotation_source,
            }
            for a in (variant.annotations or [])
        ]

        evidence_data = [
            {
                "id": e.id,
                "source_name": e.source_name,
                "source_accession": e.source_accession,
                "interpretation": e.interpretation,
                "review_status": e.review_status,
                "has_conflicts": e.has_conflicts,
                "evidence_summary": e.evidence_summary,
                "source_url": e.source_url,
            }
            for e in (variant.evidence_records or [])
        ]

        prio_data = None
        if variant.prioritization:
            prio = variant.prioritization
            prio_data = {
                "id": prio.id,
                "priority_category": prio.priority_category,
                "score": prio.score,
                "rule_version": prio.rule_version,
                "reasons": prio.reasons_json,
                "limitations": prio.limitations_json,
            }

        input_evidence_ids = {
            "annotation_ids": [a["id"] for a in annotations_data],
            "evidence_ids": [e["id"] for e in evidence_data],
            "prioritization_id": prio_data["id"] if prio_data else None,
        }

        # 2. Build constrained prompt
        user_prompt = build_variant_explanation_prompt(
            chromosome=variant.chromosome,
            position=variant.position,
            reference_allele=variant.reference_allele,
            alternate_allele=variant.alternate_allele,
            genome_assembly=genome_assembly,
            variant_type=variant.variant_type,
            variant_identifier=variant.variant_identifier,
            annotations=annotations_data,
            evidence_records=evidence_data,
            prioritization=prio_data,
        )

        client = self.client
        raw_output = ""
        parsed_output: Optional[VariantExplanationOutput] = None
        validation_errors: List[str] = []
        is_valid = False

        # 3. Call LLM with bounded retry policy (max 2 attempts)
        for attempt in range(1, 3):
            try:
                raw_output = await client.generate_raw(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_prompt
                )
                clean_json_str = extract_json_from_llm_text(raw_output)
                raw_dict = json.loads(clean_json_str)

                # Validate strictly with Pydantic
                parsed_output = VariantExplanationOutput(**raw_dict)
                is_valid = True
                validation_errors.clear()
                break
            except Exception as e:
                err_msg = f"Attempt {attempt} failed: {type(e).__name__}: {str(e)}"
                logger.warning(f"AI explanation generation error for variant {variant.id}: {err_msg}")
                validation_errors.append(err_msg)

        # 4. Construct result
        result = ExplanationGenerationResult(
            model_provider=client.provider_name,
            model_name=client.model_name,
            prompt_version=PROMPT_VERSION,
            is_valid=is_valid,
            parsed_output=parsed_output,
            raw_response=raw_output,
            validation_errors=validation_errors if not is_valid else None,
            input_evidence_ids=input_evidence_ids,
        )

        # 5. Persist to database if requested
        if persist and variant.id:
            try:
                # Check if explanation already exists for this variant
                existing = db.scalar(select(AIExplanation).where(AIExplanation.variant_id == variant.id))
                if existing:
                    existing.model_provider = result.model_provider
                    existing.model_name = result.model_name
                    existing.prompt_version = result.prompt_version
                    existing.input_evidence_ids = result.input_evidence_ids
                    existing.explanation_text = (
                        parsed_output.summary if parsed_output else "Explanation generation failed."
                    )
                    existing.structured_output_json = (
                        parsed_output.model_dump() if parsed_output else None
                    )
                    existing.validation_status = "VALID" if is_valid else "FAILED"
                    db.commit()
                    db.refresh(existing)
                else:
                    db_record = AIExplanation(
                        variant_id=variant.id,
                        model_provider=result.model_provider,
                        model_name=result.model_name,
                        prompt_version=result.prompt_version,
                        input_evidence_ids=result.input_evidence_ids,
                        explanation_text=(
                            parsed_output.summary if parsed_output else "Explanation generation failed."
                        ),
                        structured_output_json=(
                            parsed_output.model_dump() if parsed_output else None
                        ),
                        validation_status="VALID" if is_valid else "FAILED",
                    )
                    db.add(db_record)
                    db.commit()
            except Exception as db_err:
                db.rollback()
                logger.error(f"Failed to persist AI explanation for variant {variant.id}: {db_err}")

        return result

    async def explain_analysis_candidates(
        self,
        db: Session,
        analysis_id: str,
        limit: int = 10,
        genome_assembly: str = "GRCh38"
    ) -> List[AIExplanation]:
        """
        Batch generates evidence-grounded explanations for top prioritized candidates in an analysis.
        """
        # Query top variants eager-loading annotations, evidence, and prioritization
        stmt = (
            select(Variant)
            .where(Variant.analysis_id == analysis_id)
            .options(
                joinedload(Variant.annotations),
                joinedload(Variant.evidence_records),
                joinedload(Variant.prioritization),
                joinedload(Variant.ai_explanation),
            )
            .limit(limit)
        )
        variants = list(db.scalars(stmt).unique().all())

        explanations = []
        for v in variants:
            res = await self.generate_variant_explanation(
                db=db,
                variant=v,
                genome_assembly=genome_assembly,
                persist=True
            )
            # Re-fetch or link
            if v.ai_explanation:
                explanations.append(v.ai_explanation)

        return explanations


explanation_service = ExplanationService()

