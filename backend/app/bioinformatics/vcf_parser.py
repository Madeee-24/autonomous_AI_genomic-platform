"""
VCF Parsing Engine: Extracts, normalizes, and structures genomic variants.
Supports multiallelic splitting, variant type classification, and tabular export.
"""
import gzip
import io
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union
import pandas as pd

from app.bioinformatics.models import (
    ParsedVariant,
    ValidationSummary,
    VariantType
)
from app.bioinformatics.validator import VCFValidator, is_gzip_file


def classify_variant_type(ref: str, alt: str) -> VariantType:
    """
    Classifies a variant into SNV, Insertion, Deletion, MNV, or Indel based on allele sequences.
    """
    ref_len = len(ref)
    alt_len = len(alt)

    if ref_len == 1 and alt_len == 1:
        return VariantType.SNV
    elif ref_len < alt_len:
        if alt.startswith(ref):
            return VariantType.INSERTION
        return VariantType.INDEL
    elif ref_len > alt_len:
        if ref.startswith(alt):
            return VariantType.DELETION
        return VariantType.INDEL
    elif ref_len == alt_len and ref_len > 1:
        return VariantType.MNV
    else:
        return VariantType.INDEL


def parse_info_string(info_str: str) -> Dict[str, Any]:
    """
    Parses a VCF INFO string (e.g. 'DP=45;AF=0.50;FLAG') into a Python dictionary.
    """
    if not info_str or info_str == ".":
        return {}

    parsed_info: Dict[str, Any] = {}
    items = info_str.split(";")

    for item in items:
        if not item:
            continue
        if "=" in item:
            key, val = item.split("=", 1)
            # Type inference for numeric types
            if val.isdigit():
                parsed_info[key] = int(val)
            else:
                try:
                    parsed_info[key] = float(val)
                except ValueError:
                    # Comma-separated floats or strings
                    if "," in val:
                        parts = val.split(",")
                        parsed_info[key] = parts
                    else:
                        parsed_info[key] = val
        else:
            # Boolean flag
            parsed_info[item] = True

    return parsed_info


class VCFParser:
    """
    Standard VCF parser extracting structured variants and multiallelic sites.
    """

    def __init__(self, validator: Optional[VCFValidator] = None):
        self.validator = validator or VCFValidator()

    def parse(
        self,
        filepath_or_stream: Union[str, Path, BinaryIO],
        filename: str = "input.vcf"
    ) -> Tuple[List[ParsedVariant], ValidationSummary]:
        """
        Validates and parses a VCF file, returning structured variants and a validation summary.
        Multiallelic variants are expanded into separate ParsedVariant objects.
        """
        # 1. Run validator
        summary = self.validator.validate(filepath_or_stream, filename=filename)

        if not summary.is_valid and summary.accepted_variants_count == 0:
            return [], summary

        # 2. Re-open stream for structured extraction
        is_gzip = is_gzip_file(filepath_or_stream)

        if isinstance(filepath_or_stream, (str, Path)):
            stream = gzip.open(filepath_or_stream, "rt", encoding="utf-8", errors="replace") if is_gzip else open(filepath_or_stream, "r", encoding="utf-8", errors="replace")
        else:
            if hasattr(filepath_or_stream, "seek"):
                filepath_or_stream.seek(0)
            stream = gzip.open(filepath_or_stream, "rt", encoding="utf-8", errors="replace") if is_gzip else io.TextIOWrapper(filepath_or_stream, encoding="utf-8", errors="replace")

        variants: List[ParsedVariant] = []
        line_number = 0
        has_column_header = False
        format_col_idx: Optional[int] = None
        first_sample_col_idx: Optional[int] = None

        try:
            for raw_line in stream:
                line_number += 1
                line = raw_line.strip()

                if not line or line.startswith("##"):
                    continue

                if line.startswith("#CHROM"):
                    has_column_header = True
                    headers = line.split("\t")
                    if "FORMAT" in headers:
                        format_col_idx = headers.index("FORMAT")
                        if len(headers) > format_col_idx + 1:
                            first_sample_col_idx = format_col_idx + 1
                    continue

                if not has_column_header:
                    continue

                cols = line.split("\t")
                if len(cols) < 8:
                    continue

                chrom = cols[0]
                try:
                    pos = int(cols[1])
                except ValueError:
                    continue

                var_id = cols[2] if cols[2] != "." else None
                ref = cols[3].upper()
                alt_str = cols[4].upper()
                qual_str = cols[5]
                filter_status = cols[6]
                info_str = cols[7]

                quality: Optional[float] = None
                if qual_str != ".":
                    try:
                        quality = float(qual_str)
                    except ValueError:
                        quality = None

                info_fields = parse_info_string(info_str)

                # Extract genotype if present
                genotype: Optional[str] = None
                if format_col_idx is not None and first_sample_col_idx is not None and len(cols) > first_sample_col_idx:
                    format_keys = cols[format_col_idx].split(":")
                    sample_vals = cols[first_sample_col_idx].split(":")
                    if "GT" in format_keys:
                        gt_idx = format_keys.index("GT")
                        if gt_idx < len(sample_vals):
                            genotype = sample_vals[gt_idx]

                # Multiallelic handling: split ALT alleles
                alt_alleles = [a.strip() for a in alt_str.split(",") if a.strip()]
                is_multiallelic = len(alt_alleles) > 1

                for idx, alt in enumerate(alt_alleles, start=1):
                    variant_type = classify_variant_type(ref, alt)

                    # For multiallelic sites, adjust AF if present as a list
                    variant_info = dict(info_fields)
                    if "AF" in variant_info and isinstance(variant_info["AF"], list):
                        if idx - 1 < len(variant_info["AF"]):
                            try:
                                variant_info["AF"] = float(variant_info["AF"][idx - 1])
                            except (ValueError, TypeError):
                                pass

                    parsed_variant = ParsedVariant(
                        chromosome=chrom,
                        position=pos,
                        reference_allele=ref,
                        alternate_allele=alt,
                        variant_id=var_id,
                        quality=quality,
                        filter_status=filter_status,
                        info_fields=variant_info,
                        genotype=genotype,
                        allele_index=idx,
                        is_multiallelic=is_multiallelic,
                        original_line_number=line_number,
                        variant_type=variant_type
                    )
                    variants.append(parsed_variant)

        finally:
            if not isinstance(filepath_or_stream, (str, Path)) and hasattr(filepath_or_stream, "seek"):
                filepath_or_stream.seek(0)
            else:
                stream.close()

        return variants, summary

    def parse_to_dataframe(
        self,
        filepath_or_stream: Union[str, Path, BinaryIO],
        filename: str = "input.vcf"
    ) -> Tuple[pd.DataFrame, ValidationSummary]:
        """
        Parses variants directly into a Pandas DataFrame for downstream tabular analyses.
        """
        variants, summary = self.parse(filepath_or_stream, filename=filename)

        if not variants:
            return pd.DataFrame(), summary

        records = [
            {
                "chromosome": v.chromosome,
                "position": v.position,
                "reference_allele": v.reference_allele,
                "alternate_allele": v.alternate_allele,
                "variant_id": v.variant_id or ".",
                "variant_type": v.variant_type.value,
                "quality": v.quality,
                "filter_status": v.filter_status,
                "is_multiallelic": v.is_multiallelic,
                "allele_index": v.allele_index,
                "genotype": v.genotype or ".",
                "vep_format": v.to_vep_format()
            }
            for v in variants
        ]

        df = pd.DataFrame.from_records(records)
        return df, summary

