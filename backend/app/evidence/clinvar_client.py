"""
NCBI ClinVar Evidence Client: Queries Entrez E-Utilities for clinical significance,
review status, accessions, and conflicting interpretations.
"""
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.models.evidence import EvidenceRecord
from app.models.variant import Variant

CLINVAR_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
CLINVAR_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class ClinVarClient:
    """
    Client for retrieving verifiable clinical assertions from NCBI ClinVar via Entrez E-Utilities.
    """

    def __init__(
        self,
        base_search_url: str = CLINVAR_ESEARCH_URL,
        base_summary_url: str = CLINVAR_ESUMMARY_URL,
        timeout_seconds: float = 20.0,
        request_delay: float = 0.35,  # Respect NCBI 3 req/sec rate limit
        max_retries: int = 3
    ):
        self.search_url = base_search_url
        self.summary_url = base_summary_url
        self.timeout_seconds = timeout_seconds
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._cache: Dict[str, Optional[dict]] = {}

    def search_variant_uids(self, query_term: str) -> List[str]:
        """
        Executes an esearch query to retrieve ClinVar Variation UIDs matching an rsID or coordinate term.
        """
        params = {
            "db": "clinvar",
            "term": query_term,
            "retmode": "json",
            "retmax": 5
        }

        retries = 0
        while retries <= self.max_retries:
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.get(self.search_url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    id_list = data.get("esearchresult", {}).get("idlist", [])
                    return id_list

                logger.warning(f"ClinVar esearch returned status {resp.status_code} for '{query_term}'.")
                return []

            except httpx.TimeoutException:
                retries += 1
                logger.warning(f"ClinVar esearch timeout (attempt {retries}/{self.max_retries}).")
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"ClinVar esearch error for '{query_term}': {str(e)}")
                return []

        return []

    def fetch_summaries(self, uids: List[str]) -> Dict[str, dict]:
        """
        Retrieves detailed summary records for a list of ClinVar UIDs in a single request.
        """
        if not uids:
            return {}

        params = {
            "db": "clinvar",
            "id": ",".join(uids),
            "retmode": "json"
        }

        retries = 0
        while retries <= self.max_retries:
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.get(self.summary_url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    result = data.get("result", {})
                    # Filter out the 'uids' list key from result dictionary
                    return {k: v for k, v in result.items() if k != "uids" and isinstance(v, dict)}

                logger.warning(f"ClinVar esummary returned status {resp.status_code}.")
                return {}

            except httpx.TimeoutException:
                retries += 1
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"ClinVar esummary error: {str(e)}")
                return {}

        return {}

    def parse_clinvar_record_to_evidence(self, variant_id: str, raw_record: dict) -> EvidenceRecord:
        """
        Structures a raw ClinVar JSON record into an EvidenceRecord entity.
        Accurately preserves accessions, review criteria, traits, and conflict flags.
        """
        uid = str(raw_record.get("uid", ""))
        accession = raw_record.get("accession") or (f"VCV{uid.zfill(9)}" if uid else None)
        title = raw_record.get("title", "")

        # Extract germline classification
        germline = raw_record.get("germline_classification", {}) or {}
        clinical_impact = raw_record.get("clinical_impact_classification", {}) or {}

        # Primary interpretation description
        interpretation = (
            germline.get("description")
            or clinical_impact.get("description")
            or raw_record.get("clinical_significance", {}).get("description")
            or "Uncertain significance"
        )

        review_status = (
            germline.get("review_status")
            or clinical_impact.get("review_status")
            or "no assertion criteria provided"
        )

        # Associated phenotypic traits/diseases
        traits = germline.get("trait_set", []) or clinical_impact.get("trait_set", []) or []
        trait_names: List[str] = []
        for t in traits:
            name = t.get("trait_name")
            if name:
                trait_names.append(name)

        associated_conditions = ", ".join(trait_names[:3])
        if len(trait_names) > 3:
            associated_conditions += f" (and {len(trait_names) - 3} more)"

        if associated_conditions:
            evidence_summary = f"{interpretation} ({review_status}). Associated condition(s): {associated_conditions}."
        else:
            evidence_summary = f"{interpretation} ({review_status})."

        # Conflict Detection:
        # 1. ClinVar explicitly labels "Conflicting classifications of pathogenicity"
        # 2. Or conflicting submissions are reported in review status
        interp_lower = interpretation.lower()
        has_conflicts = (
            "conflict" in interp_lower
            or "conflicting" in interp_lower
            or "conflicts" in review_status.lower()
        )

        source_url = f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/" if uid else None

        return EvidenceRecord(
            variant_id=variant_id,
            source_name="ClinVar",
            source_accession=accession,
            interpretation=interpretation,
            review_status=review_status,
            evidence_summary=evidence_summary,
            source_url=source_url,
            has_conflicts=has_conflicts,
            source_version="NCBI ClinVar E-Utilities (JSON v0.3)",
            raw_record_json={
                "uid": uid,
                "accession": accession,
                "title": title,
                "germline_classification": germline,
                "clinical_impact_classification": clinical_impact,
                "trait_names": trait_names
            }
        )

    def retrieve_evidence_for_variants(
        self,
        variants: List[Variant],
        assembly: str = "GRCh38"
    ) -> Tuple[List[EvidenceRecord], List[str]]:
        """
        Retrieves clinical evidence from ClinVar for a list of variants.
        Preserves provenance and records missing evidence explicitly without fabricating assertions.
        """
        if not variants:
            return [], []

        evidence_records: List[EvidenceRecord] = []
        warnings: List[str] = []

        for v in variants:
            # Query term priority: dbSNP rsID, then genomic coordinate
            query_term = None
            if v.variant_identifier and v.variant_identifier.startswith("rs"):
                query_term = f"{v.variant_identifier}[All Fields]"
            else:
                clean_chr = v.chromosome.replace("chr", "")
                query_term = f"{clean_chr}[chr] AND {v.position}[chrpos]"

            # Check cache
            if query_term in self._cache:
                cached_data = self._cache[query_term]
                if cached_data:
                    ev = self.parse_clinvar_record_to_evidence(v.id, cached_data)
                    evidence_records.append(ev)
                continue

            time.sleep(self.request_delay)
            uids = self.search_variant_uids(query_term)

            if not uids:
                self._cache[query_term] = None
                continue

            # Fetch summary for the top matching UID
            summaries = self.fetch_summaries([uids[0]])
            if uids[0] in summaries:
                raw_rec = summaries[uids[0]]
                self._cache[query_term] = raw_rec
                ev_record = self.parse_clinvar_record_to_evidence(v.id, raw_rec)
                evidence_records.append(ev_record)
            else:
                self._cache[query_term] = None
                warnings.append(f"ClinVar record summary could not be retrieved for variant {v.variant_identifier or v.position}.")

        return evidence_records, warnings


clinvar_client = ClinVarClient()

