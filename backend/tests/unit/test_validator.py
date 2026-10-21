"""
Unit tests for VCF file and assembly validation.
"""
import io
import gzip
from pathlib import Path
import pytest
from app.bioinformatics.validator import (
    VCFValidator,
    calculate_sha256,
    is_gzip_file,
    detect_assembly_from_header
)


@pytest.fixture
def sample_vcf_path():
    path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "test_fixtures" / "sample.vcf"
    assert path.exists(), f"Sample VCF fixture not found at {path}"
    return path


def test_validator_on_valid_sample_vcf(sample_vcf_path):
    validator = VCFValidator()
    summary = validator.validate(sample_vcf_path, filename=sample_vcf_path.name)

    assert summary.is_valid is True
    assert summary.detected_assembly == "GRCh38"
    assert summary.file_format == "VCFv4.2"
    assert summary.accepted_variants_count == 5
    assert summary.rejected_records_count == 0
    assert len(summary.file_checksum) == 64
    assert "SAMPLE1" in summary.sample_names
    assert summary.contains_sample_genotypes is True


def test_validator_on_empty_file():
    validator = VCFValidator()
    empty_stream = io.BytesIO(b"")
    summary = validator.validate(empty_stream, filename="empty.vcf")

    assert summary.is_valid is False
    assert "empty" in summary.warnings[0].lower()
    assert summary.rejected_records_count == 1


def test_validator_on_invalid_extension():
    validator = VCFValidator()
    data = io.BytesIO(b"Some text")
    summary = validator.validate(data, filename="genomic.txt")

    assert summary.is_valid is False
    assert "invalid file extension" in summary.warnings[0].lower()


def test_validator_on_missing_column_headers():
    vcf_content = b"##fileformat=VCFv4.2\nchr1\t100\trs1\tA\tT\t100\tPASS\t.\n"
    validator = VCFValidator()
    summary = validator.validate(io.BytesIO(vcf_content), filename="malformed.vcf")

    assert summary.is_valid is False
    assert summary.rejected_records_count > 0


def test_validator_on_malformed_records():
    # Record with invalid chromosome 'chr999', invalid POS 'not_a_num', and invalid REF 'ZZZ'
    vcf_content = (
        b"##fileformat=VCFv4.2\n"
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        b"chr1\t1000\trs1\tA\tG\t50\tPASS\t.\n"
        b"chr999\t2000\trs2\tC\tT\t50\tPASS\t.\n"
        b"chr1\tnot_a_num\trs3\tC\tT\t50\tPASS\t.\n"
        b"chr1\t3000\trs4\tZZZ\tT\t50\tPASS\t.\n"
    )
    validator = VCFValidator()
    summary = validator.validate(io.BytesIO(vcf_content), filename="records_with_errors.vcf")

    assert summary.accepted_variants_count == 1
    assert summary.rejected_records_count == 3
    assert len(summary.rejections) == 3


def test_validator_on_gzipped_vcf():
    vcf_content = (
        b"##fileformat=VCFv4.2\n"
        b"##reference=GRCh38\n"
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        b"chr17\t7675088\trs28934578\tC\tT\t999\tPASS\tDP=60\n"
    )
    gz_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buffer, mode="wb") as gz:
        gz.write(vcf_content)
    gz_buffer.seek(0)

    assert is_gzip_file(gz_buffer) is True

    validator = VCFValidator()
    summary = validator.validate(gz_buffer, filename="compressed.vcf.gz")

    assert summary.is_valid is True
    assert summary.accepted_variants_count == 1
    assert summary.detected_assembly == "GRCh38"


def test_detect_assembly_from_header():
    assert detect_assembly_from_header(["##reference=GRCh38"]) == "GRCh38"
    assert detect_assembly_from_header(["##assembly=hg38"]) == "GRCh38"
    assert detect_assembly_from_header(["##reference=GRCh37"]) == "GRCh37"
    assert detect_assembly_from_header(["##reference=hg19"]) == "GRCh37"
    assert detect_assembly_from_header(["##source=Custom"]) is None

