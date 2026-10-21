"""
Variant Prioritization Engine.
Calculates transparent priority scores, categorizes variants into research tiers,
and tracks detailed justification and limitation trails.
"""
from typing import List, Optional
from app.models.annotation import Annotation
from app.models.evidence import EvidenceRecord
from app.models.prioritization import PrioritizationResult
from app.models.variant import Variant
from app.prioritization.rules import (
    CLINVAR_INTERPRETATION_WEIGHTS,
    CLINVAR_REVIEW_STATUS_BONUS,
    FAILED_FILTER_PENALTY,
    QUALITY_FILTER_WEIGHTS,
    RULE_VERSION,
    VEP_IMPACT_WEIGHTS,
    PriorityCategory,
    PrioritizationEvaluation,
    ScoringFactor,
)


class VariantPrioritizer:
    """
    Evaluates individual variants using a transparent multi-factor scoring matrix.
    """

    def evaluate_variant(
        self,
        variant: Variant,
        annotations: Optional[List[Annotation]] = None,
        evidence_records: Optional[List[EvidenceRecord]] = None
    ) -> PrioritizationEvaluation:
        """
        Executes deterministic prioritization scoring on a single variant.
        """
        ann_list = annotations if annotations is not None else (variant.annotations or [])
        ev_list = evidence_records if evidence_records is not None else (variant.evidence_records or [])

        factors: List[ScoringFactor] = []
        limitations: List[str] = []
        raw_score = 0.0
        has_conflicts = False

        # ---------------------------------------------------------
        # 1. Quality & Filter Status (max 10 points)
        # ---------------------------------------------------------
        if variant.filter_status == "PASS":
            pts = QUALITY_FILTER_WEIGHTS["PASS"]
            raw_score += pts
            factors.append(
                ScoringFactor(
                    name="Filter PASS",
                    contribution=pts,
                    reason="Variant passed all sequencing quality filters in VCF",
                    source="VCF FILTER"
                )
            )
        else:
            raw_score += FAILED_FILTER_PENALTY
            factors.append(
                ScoringFactor(
                    name=f"Filter {variant.filter_status}",
                    contribution=FAILED_FILTER_PENALTY,
                    reason=f"Variant flagged with quality filter '{variant.filter_status}'",
                    source="VCF FILTER"
                )
            )

        # ---------------------------------------------------------
        # 2. Functional Consequence Impact from VEP (max 40 points)
        # ---------------------------------------------------------
        highest_impact_ann = None
        impact_rank = {"HIGH": 4, "MODERATE": 3, "LOW": 2, "MODIFIER": 1}

        for ann in ann_list:
            rank = impact_rank.get(ann.impact, 0)
            if not highest_impact_ann or rank > impact_rank.get(highest_impact_ann.impact, 0):
                highest_impact_ann = ann

        if highest_impact_ann:
            imp = highest_impact_ann.impact
            pts = VEP_IMPACT_WEIGHTS.get(imp, 0.0)
            raw_score += pts
            gene_info = f" in {highest_impact_ann.gene_symbol}" if highest_impact_ann.gene_symbol else ""
            factors.append(
                ScoringFactor(
                    name=f"VEP {imp} Impact",
                    contribution=pts,
                    reason=f"Predicted {highest_impact_ann.consequence}{gene_info} ({imp} impact)",
                    source="Ensembl VEP"
                )
            )
        else:
            limitations.append("Functional consequence annotation unavailable; impact scored as neutral (0 points).")

        # ---------------------------------------------------------
        # 3. Clinical Evidence from ClinVar (max 50 points)
        # ---------------------------------------------------------
        primary_evidence = ev_list[0] if ev_list else None

        if primary_evidence:
            has_conflicts = primary_evidence.has_conflicts
            interp_lower = primary_evidence.interpretation.lower()

            if has_conflicts:
                pts = 10.0
                raw_score += pts
                factors.append(
                    ScoringFactor(
                        name="Conflicting Clinical Assertions",
                        contribution=pts,
                        reason="Disagreement between clinical submitters reported in ClinVar",
                        source="ClinVar"
                    )
                )
                limitations.append("Conflicting clinical evidence across ClinVar submitters; requires expert manual review.")
            else:
                matched_interp_pts = None
                for key in sorted(CLINVAR_INTERPRETATION_WEIGHTS.keys(), key=len, reverse=True):
                    if key in interp_lower:
                        matched_interp_pts = CLINVAR_INTERPRETATION_WEIGHTS[key]
                        break

                if matched_interp_pts is not None:
                    raw_score += matched_interp_pts
                    factors.append(
                        ScoringFactor(
                            name=f"ClinVar {primary_evidence.interpretation}",
                            contribution=matched_interp_pts,
                            reason=f"Clinical assertion: {primary_evidence.interpretation}",
                            source="ClinVar"
                        )
                    )

                # Review Status Bonus
                rev_status = primary_evidence.review_status.lower() if primary_evidence.review_status else ""
                for key, bonus_pts in CLINVAR_REVIEW_STATUS_BONUS.items():
                    if key in rev_status:
                        if bonus_pts != 0.0:
                            raw_score += bonus_pts
                            factors.append(
                                ScoringFactor(
                                    name="ClinVar Review Status Bonus",
                                    contribution=bonus_pts,
                                    reason=f"Assertion supported by: '{primary_evidence.review_status}'",
                                    source="ClinVar"
                                )
                            )
                        break
        else:
            limitations.append("No record retrieved from NCBI ClinVar; treated as unasserted (0 points).")

        # ---------------------------------------------------------
        # 4. Score Normalization (Clamp to 0.0 - 100.0)
        # ---------------------------------------------------------
        normalized_score = round(max(0.0, min(100.0, raw_score)), 1)

        # ---------------------------------------------------------
        # 5. Categorical Tier Assignment
        # ---------------------------------------------------------
        interp = primary_evidence.interpretation.lower() if primary_evidence else ""
        impact = highest_impact_ann.impact if highest_impact_ann else ""

        if has_conflicts:
            category = PriorityCategory.UNCERTAIN
        elif "pathogenic" in interp and "likely" not in interp:
            # Confirmed Pathogenic
            category = PriorityCategory.TIER_1_CRITICAL
        elif "likely pathogenic" in interp or (impact == "HIGH" and "benign" not in interp):
            # Likely pathogenic or Loss-of-Function HIGH impact
            category = PriorityCategory.TIER_2_HIGH
        elif "uncertain significance" in interp or impact == "MODERATE":
            # VUS or Missense mutation
            category = PriorityCategory.TIER_3_MODERATE
        elif "benign" in interp:
            # Benign / Likely Benign
            category = PriorityCategory.TIER_4_LOW
        elif not primary_evidence and not highest_impact_ann:
            category = PriorityCategory.UNCERTAIN
        elif normalized_score >= 80.0:
            category = PriorityCategory.TIER_1_CRITICAL
        elif normalized_score >= 60.0:
            category = PriorityCategory.TIER_2_HIGH
        elif normalized_score >= 35.0:
            category = PriorityCategory.TIER_3_MODERATE
        else:
            category = PriorityCategory.TIER_4_LOW

        return PrioritizationEvaluation(
            variant_id=variant.id,
            rule_version=RULE_VERSION,
            score=normalized_score,
            priority_category=category,
            triggered_rules=factors,
            limitations=limitations,
            has_conflicting_evidence=has_conflicts
        )

    def prioritize_variant_to_model(
        self,
        variant: Variant,
        annotations: Optional[List[Annotation]] = None,
        evidence_records: Optional[List[EvidenceRecord]] = None
    ) -> PrioritizationResult:
        """
        Evaluates a variant and returns a SQLAlchemy PrioritizationResult entity.
        """
        eval_result = self.evaluate_variant(variant, annotations, evidence_records)

        reasons = [
            {"factor": f.name, "points": f.contribution, "justification": f.reason, "source": f.source}
            for f in eval_result.triggered_rules
        ]

        return PrioritizationResult(
            variant_id=variant.id,
            rule_version=eval_result.rule_version,
            score=eval_result.score,
            priority_category=eval_result.priority_category.value,
            reasons_json={"scoring_breakdown": reasons, "has_conflicts": eval_result.has_conflicting_evidence},
            limitations_json={"data_limitations": eval_result.limitations}
        )

    def prioritize_batch(self, variants: List[Variant]) -> List[PrioritizationResult]:
        """
        Prioritizes a collection of variants with eager loaded annotations and evidence.
        """
        results: List[PrioritizationResult] = []
        for v in variants:
            res = self.prioritize_variant_to_model(v)
            results.append(res)
        return results


prioritizer = VariantPrioritizer()

