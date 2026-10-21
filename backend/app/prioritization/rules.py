"""
Prioritization Rules and Heuristic Weight Matrix Specification.
Version: v1.0

Design Philosophy:
- Fully deterministic and reproducible.
- Transparent: every point assigned is traced to an explicit biological or clinical justification.
- Honest about missing data: missing VEP or ClinVar records contribute 0 points (neutral)
  and are explicitly recorded in limitations_json rather than fabricated as negative findings.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

RULE_VERSION = "v1.0"


class PriorityCategory(str, Enum):
    TIER_1_CRITICAL = "TIER_1_CRITICAL"
    TIER_2_HIGH = "TIER_2_HIGH"
    TIER_3_MODERATE = "TIER_3_MODERATE"
    TIER_4_LOW = "TIER_4_LOW"
    UNCERTAIN = "UNCERTAIN"


# 1. Clinical Evidence Scoring Matrix (max 50 points)
CLINVAR_INTERPRETATION_WEIGHTS = {
    "pathogenic": 45.0,
    "likely pathogenic": 35.0,
    "pathogenic/likely pathogenic": 40.0,
    "uncertain significance": 15.0,
    "likely benign": -20.0,
    "benign": -30.0,
    "benign/likely benign": -25.0,
}

CLINVAR_REVIEW_STATUS_BONUS = {
    "practice guideline": 5.0,
    "reviewed by expert panel": 5.0,
    "criteria provided, multiple submitters, no conflicts": 3.0,
    "criteria provided, single submitter": 1.0,
    "criteria provided, conflicting classifications": -5.0,
    "no assertion criteria provided": 0.0,
}

# 2. Functional Consequence Impact Weights (max 40 points)
VEP_IMPACT_WEIGHTS = {
    "HIGH": 40.0,        # Frameshift, stop gained, splice acceptor/donor
    "MODERATE": 25.0,    # Missense, inframe deletion/insertion
    "LOW": 10.0,         # Synonymous, stop retained
    "MODIFIER": 2.0,     # Intronic, intergenic, UTR
}

# 3. Sequencing Quality Weights (max 10 points)
QUALITY_FILTER_WEIGHTS = {
    "PASS": 10.0,
}
FAILED_FILTER_PENALTY = -15.0


class ScoringFactor(BaseModel):
    """
    Individual evidence factor contributing to the prioritization score.
    """
    name: str
    contribution: float
    reason: str
    source: str


class PrioritizationEvaluation(BaseModel):
    """
    Structured outcome of the prioritization engine for a single variant.
    """
    variant_id: str
    rule_version: str = RULE_VERSION
    score: float = Field(..., ge=0.0, le=100.0, description="Normalized priority index between 0.0 and 100.0")
    priority_category: PriorityCategory
    triggered_rules: List[ScoringFactor] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    has_conflicting_evidence: bool = False

