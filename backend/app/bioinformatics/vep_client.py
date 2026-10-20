"""
Ensembl Variant Effect Predictor (VEP) Client.
Connects to the official Ensembl VEP REST API with coordinate batching,
rate-limiting backoff, consequence extraction, and annotation mapping.
"""
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.models.annotation import Annotation
from app.models.variant import Variant

# Rate limit defaults and endpoints
GRCH38_VEP_URL = "https://rest.ensembl.org"
GRCH37_VEP_URL = "https://grch37.rest.ensembl.org"
MAX_BATCH_SIZE = 200  # Ensembl REST API limit per POST


def format_variant_for_vep(
    chromosome: str,
    position: int,
    reference_allele: str,
    alternate_allele: str,
    variant_identifier: Optional[str] = None
) -> Tuple[str, str]:
    """
    Formats variant coordinates into Ensembl VEP standard input format:
    `chr start end ref/alt strand identifier`
    Returns (vep_string, lookup_key).
    """
    clean_chrom = chromosome.replace("chr", "")
    start = position
    ref = reference_allele
    alt = alternate_allele

    if len(ref) == 1 and len(alt) == 1:
        end = start
    elif len(ref) > len(alt):
        # Deletion
        end = start + len(ref) - 1
    else:
        # Insertion
        end = start + max(1, len(ref)) - 1

    lookup_id = variant_identifier if variant_identifier and variant_identifier != "." else f"{clean_chrom}_{start}_{ref}_{alt}"
    vep_string = f"{clean_chrom} {start} {end} {ref}/{alt} + {lookup_id}"
    return vep_string, lookup_id


class EnsemblVEPClient:
    """
    Integration client for Ensembl Variant Effect Predictor (VEP) REST API.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3
    ):
        self.base_url = base_url or settings.VEP_BASE_URL
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._cache: Dict[str, dict] = {}

    def _get_api_endpoint(self, assembly: str = "GRCh38") -> str:
        if assembly.upper() in ["GRCH37", "HG19"]:
            return f"{GRCH37_VEP_URL}/vep/human/region"
        return f"{self.base_url}/vep/human/region"

    def annotate_batch(
        self,
        vep_input_strings: List[str],
        assembly: str = "GRCh38"
    ) -> Tuple[List[dict], Optional[str]]:
        """
        Sends a batch of variant strings to Ensembl VEP POST endpoint with exponential backoff on HTTP 429.
        Returns (results_list, error_message).
        """
        if not vep_input_strings:
            return [], None

        endpoint = self._get_api_endpoint(assembly)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"variants": vep_input_strings}

        retries = 0
        backoff_delay = 1.0

        while retries <= self.max_retries:
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(endpoint, json=payload, headers=headers)

                # Rate-limit check (HTTP 429)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", backoff_delay))
                    logger.warning(f"Ensembl VEP rate-limited (HTTP 429). Retrying after {retry_after:.1f}s...")
                    time.sleep(retry_after)
                    retries += 1
                    backoff_delay *= 2
                    continue

                if response.status_code == 200:
                    data = response.json()
                    return data, None

                # Other HTTP errors
                error_msg = f"Ensembl VEP API returned HTTP {response.status_code}: {response.text[:200]}"
                logger.error(error_msg)
                return [], error_msg

            except httpx.TimeoutException:
                retries += 1
                logger.warning(f"Ensembl VEP request timed out (attempt {retries}/{self.max_retries}).")
                time.sleep(backoff_delay)
                backoff_delay *= 2

            except Exception as ex:
                error_msg = f"Network or connection error during Ensembl VEP call: {str(ex)}"
                logger.error(error_msg)
                return [], error_msg

        return [], f"Ensembl VEP query failed after {self.max_retries} attempts."

    def parse_vep_record_to_annotation(self, variant_id: str, raw_vep_record: dict) -> Annotation:
        """
        Extracts primary consequence, affected gene, transcript, and impact from a raw VEP record.
        """
        most_severe = raw_vep_record.get("most_severe_consequence", "unknown_consequence")
        transcript_consequences = raw_vep_record.get("transcript_consequences", [])

        # Find canonical or most impactful transcript
        selected_tx = None
        for tx in transcript_consequences:
            if tx.get("canonical") == 1:
                selected_tx = tx
                break
        if not selected_tx and transcript_consequences:
            selected_tx = transcript_consequences[0]

        gene_id = selected_tx.get("gene_id") if selected_tx else None
        gene_symbol = selected_tx.get("gene_symbol") if selected_tx else None
        transcript_id = selected_tx.get("transcript_id") if selected_tx else None
        impact = selected_tx.get("impact", "MODIFIER") if selected_tx else "MODIFIER"

        return Annotation(
            variant_id=variant_id,
            gene_id=gene_id,
            gene_symbol=gene_symbol,
            transcript_id=transcript_id,
            consequence=most_severe,
            impact=impact,
            annotation_source="Ensembl VEP",
            annotation_version="Ensembl REST API",
            raw_result_json={
                "most_severe_consequence": most_severe,
                "input": raw_vep_record.get("input"),
                "allele_string": raw_vep_record.get("allele_string"),
                "selected_transcript": selected_tx,
                "all_transcripts_count": len(transcript_consequences)
            }
        )

    def annotate_variants(
        self,
        variants: List[Variant],
        assembly: str = "GRCh38"
    ) -> Tuple[List[Annotation], List[str]]:
        """
        Batches a list of Variant models, queries Ensembl VEP, maps responses back to variants,
        and constructs database Annotation models. Returns (annotations, warnings).
        """
        if not variants:
            return [], []

        annotations: List[Annotation] = []
        warnings: List[str] = []

        # 1. Build coordinate strings and lookup map
        lookup_to_variant_id: Dict[str, str] = {}
        vep_input_list: List[str] = []

        for v in variants:
            vep_str, lookup_id = format_variant_for_vep(
                chromosome=v.chromosome,
                position=v.position,
                reference_allele=v.reference_allele,
                alternate_allele=v.alternate_allele,
                variant_identifier=v.variant_identifier
            )
            lookup_to_variant_id[lookup_id] = v.id
            vep_input_list.append(vep_str)

        # 2. Chunk variants into batches
        for i in range(0, len(vep_input_list), MAX_BATCH_SIZE):
            batch = vep_input_list[i : i + MAX_BATCH_SIZE]
            results, error = self.annotate_batch(batch, assembly=assembly)

            if error:
                warnings.append(f"VEP annotation batch {i // MAX_BATCH_SIZE + 1} issue: {error}")
                continue

            for rec in results:
                rec_id = rec.get("id")
                matched_variant_id = lookup_to_variant_id.get(rec_id)

                # Fallback matching by input string if ID mismatch
                if not matched_variant_id and "input" in rec:
                    input_parts = rec["input"].split()
                    if input_parts:
                        rec_input_id = input_parts[-1]
                        matched_variant_id = lookup_to_variant_id.get(rec_input_id)

                if matched_variant_id:
                    annotation = self.parse_vep_record_to_annotation(matched_variant_id, rec)
                    annotations.append(annotation)

        return annotations, warnings


vep_client = EnsemblVEPClient()
