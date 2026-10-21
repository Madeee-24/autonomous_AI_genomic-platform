"""
Unit tests for VCF variant parsing, multiallelic expansion, and dataframe export.
"""
from pathlib import Path
import pytest
from app.bioinformatics.models import VariantType
from app.bioinformatics.vcf_parser import (
    VCFParser,
    classify_variant_type,
    parse_info_string
)


@pytest.fixture
def sample_vcf_path():
    path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test_fixtures" / "sample.vcf"
    assert path.exists(), f"Sample VCF fixture not found at {path}"
    return path


def test_classify_variant_type():
    assert classify_variant_type("A", "G") == VariantType.SNV
    assert classify_variant_type("C", "CAGT") == VariantType.INSERTION
    assert classify_variant_type("ATCT", "A") == VariantType.DELETION
    assert classify_variant_type("AC", "TG") == VariantType.MNV
    assert classify_variant_type("ACG", "TT") == VariantType.INDEL


def test_parse_info_string():
    info_str = "DP=45;AF=0.50;SOMATIC;TAG=val1,val2"
    parsed = parse_info_string(info_str)
    assert parsed["DP"] == 45
    assert parsed["AF"] == 0.50
    assert parsed["SOMATIC"] is True
    assert parsed["TAG"] == ["val1", "val2"]


def test_vcf_parser_on_sample_fixture(sample_vcf_path):
    parser = VCFParser()
    variants, summary = parser.parse(sample_vcf_path, filename=sample_vcf_path.name)

    assert summary.is_valid is True
    # 5 input records; 1 is multiallelic (2 alts), resulting in 6 total expanded variants
    assert summary.accepted_variants_count == 5
    assert len(variants) == 6

    # Variant 1: Deletion in CFTR region (rs113993960)
    v1 = variants[0]
    assert v1.chromosome == "chr7"
    assert v1.position == 117559590
    assert v1.variant_id == "rs113993960"
    assert v1.reference_allele == "ATCT"
    assert v1.alternate_allele == "A"
    assert v1.variant_type == VariantType.DELETION
    assert v1.is_multiallelic is False
    assert v1.genotype == "0/1"
    assert v1.info_fields["DP"] == 45
    assert "7 117559590 117559593 ATCT/A + rs113993960" == v1.to_vep_format()

    # Variant 2: SNV in BRCA2 (rs80359550)
    v2 = variants[1]
    assert v2.chromosome == "chr13"
    assert v2.position == 32338763
    assert v2.variant_id == "rs80359550"
    assert v2.reference_allele == "G"
    assert v2.alternate_allele == "A"
    assert v2.variant_type == VariantType.SNV
    assert v2.to_vep_format() == "13 32338763 32338763 G/A + rs80359550"

    # Multiallelic records (chr1:100000 C -> T,A)
    v5 = variants[4]
    v6 = variants[5]
    assert v5.chromosome == "chr1" and v5.position == 100000
    assert v6.chromosome == "chr1" and v6.position == 100000
    assert v5.is_multiallelic is True
    assert v6.is_multiallelic is True
    assert v5.alternate_allele == "T" and v5.allele_index == 1
    assert v6.alternate_allele == "A" and v6.allele_index == 2
    assert v5.info_fields["AF"] == 0.25
    assert v6.info_fields["AF"] == 0.25


def test_parse_to_dataframe(sample_vcf_path):
    parser = VCFParser()
    df, summary = parser.parse_to_dataframe(sample_vcf_path, filename=sample_vcf_path.name)

    assert summary.is_valid is True
    assert len(df) == 6
    assert list(df.columns) == [
        "chromosome", "position", "reference_allele", "alternate_allele",
        "variant_id", "variant_type", "quality", "filter_status",
        "is_multiallelic", "allele_index", "genotype", "vep_format"
    ]
    assert "SNV" in df["variant_type"].values
    assert "DELETION" in df["variant_type"].values

