"""
VCF Validation Engine: Validates VCF file integrity, headers, contigs, and records.
"""
import gzip
import hashlib
import io
import os
import re
from pathlib import Path
from typing import BinaryIO, List, Optional, Set, Tuple, Union

from app.bioinformatics.models import RejectedRecord, ValidationSummary
from app.core.config import settings

# Recognized human chromosomes
VALID_CHROMOSOMES: Set[str] = {
    str(i) for i in range(1, 23)
} | {f"chr{i}" for i in range(1, 23)} | {
    "X", "Y", "M", "MT", "chrX", "chrY", "chrM", "chrMT"
}

# IUPAC DNA pattern
DNA_PATTERN = re.compile(r"^[ACGTNacgtn]+$")
FILEFORMAT_PATTERN = re.compile(r"^##fileformat=VCFv4\.[0-3]", re.IGNORECASE)


def calculate_sha256(filepath_or_stream: Union[str, Path, BinaryIO]) -> Tuple[str, int]:
    """
    Computes SHA-256 checksum and total byte size of a file or binary stream.
    """
    hasher = hashlib.sha256()
    size = 0

    if isinstance(filepath_or_stream, (str, Path)):
        with open(filepath_or_stream, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
                size += len(chunk)
    else:
        # Seekable stream
        pos = filepath_or_stream.tell() if hasattr(filepath_or_stream, "tell") else 0
        for chunk in iter(lambda: filepath_or_stream.read(65536), b""):
            hasher.update(chunk)
            size += len(chunk)
        if hasattr(filepath_or_stream, "seek"):
            filepath_or_stream.seek(pos)

    return hasher.hexdigest(), size


def is_gzip_file(filepath_or_stream: Union[str, Path, BinaryIO]) -> bool:
    """
    Checks if a file or stream is gzip-compressed by inspecting the first two magic bytes (0x1f, 0x8b).
    """
    if isinstance(filepath_or_stream, (str, Path)):
        with open(filepath_or_stream, "rb") as f:
            magic = f.read(2)
            return magic == b"\x1f\x8b"
    else:
        pos = filepath_or_stream.tell() if hasattr(filepath_or_stream, "tell") else 0
        magic = filepath_or_stream.read(2)
        if hasattr(filepath_or_stream, "seek"):
            filepath_or_stream.seek(pos)
        return magic == b"\x1f\x8b"


def detect_assembly_from_header(header_lines: List[str]) -> Optional[str]:
    """
    Infers the reference genome assembly (GRCh38 or GRCh37) from VCF header declarations.
    """
    grch38_identifiers = ["GRCh38", "hg38", "GCA_000001405.15"]
    grch37_identifiers = ["GRCh37", "hg19", "b37", "GCA_000001405.1"]

    combined_headers = "\n".join(header_lines)

    for identifier in grch38_identifiers:
        if identifier in combined_headers:
            return "GRCh38"

    for identifier in grch37_identifiers:
        if identifier in combined_headers:
            return "GRCh37"

    return None


class VCFValidator:
    """
    Validates VCF files according to the VCFv4.2/4.3 standard specifications.
    """

    def __init__(self, max_file_size_mb: int = settings.MAX_UPLOAD_SIZE_MB):
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    def validate(self, filepath_or_stream: Union[str, Path, BinaryIO], filename: str = "input.vcf") -> ValidationSummary:
        """
        Executes full validation of a VCF file, checking extension, size, headers, and records.
        """
        warnings: List[str] = []
        rejections: List[RejectedRecord] = []
        contigs_declared: List[str] = []
        sample_names: List[str] = []
        header_lines: List[str] = []
        detected_assembly: Optional[str] = None
        file_format_str: Optional[str] = None
        has_column_header = False

        # 1. Extension Check
        clean_filename = filename.lower()
        if not (clean_filename.endswith(".vcf") or clean_filename.endswith(".vcf.gz")):
            return ValidationSummary(
                is_valid=False,
                file_checksum="",
                file_size_bytes=0,
                warnings=[f"Invalid file extension: '{filename}'. Expected '.vcf' or '.vcf.gz'."],
                rejected_records_count=1,
                rejections=[RejectedRecord(line_number=0, raw_content="", rejection_reason="Unsupported file format")]
            )

        # 2. Checksum and File Size
        file_checksum, file_size_bytes = calculate_sha256(filepath_or_stream)

        if file_size_bytes == 0:
            return ValidationSummary(
                is_valid=False,
                file_checksum=file_checksum,
                file_size_bytes=0,
                warnings=["Uploaded file is empty (0 bytes)."],
                rejected_records_count=1,
                rejections=[RejectedRecord(line_number=0, raw_content="", rejection_reason="Empty file")]
            )

        if file_size_bytes > self.max_file_size_bytes:
            return ValidationSummary(
                is_valid=False,
                file_checksum=file_checksum,
                file_size_bytes=file_size_bytes,
                warnings=[f"File size exceeds maximum permitted limit of {self.max_file_size_bytes // (1024*1024)} MB."],
                rejected_records_count=1,
                rejections=[RejectedRecord(line_number=0, raw_content="", rejection_reason="Exceeded file size limit")]
            )

        # 3. Read Stream transparently (plain or gzip)
        is_gzip = is_gzip_file(filepath_or_stream)

        if isinstance(filepath_or_stream, (str, Path)):
            stream = gzip.open(filepath_or_stream, "rt", encoding="utf-8", errors="replace") if is_gzip else open(filepath_or_stream, "r", encoding="utf-8", errors="replace")
        else:
            if hasattr(filepath_or_stream, "seek"):
                filepath_or_stream.seek(0)
            stream = gzip.open(filepath_or_stream, "rt", encoding="utf-8", errors="replace") if is_gzip else io.TextIOWrapper(filepath_or_stream, encoding="utf-8", errors="replace")

        line_number = 0
        total_records = 0
        accepted_records = 0
        contains_sample_genotypes = False

        try:
            for raw_line in stream:
                line_number += 1
                line = raw_line.strip()

                if not line:
                    continue

                # Header Lines (##)
                if line.startswith("##"):
                    header_lines.append(line)
                    if line_number == 1 or file_format_str is None:
                        if FILEFORMAT_PATTERN.match(line):
                            file_format_str = line.split("=", 1)[1]
                        elif line_number == 1:
                            warnings.append(f"Line 1 missing standard format header (e.g. '##fileformat=VCFv4.2'). Found: '{line[:50]}'")

                    if line.startswith("##contig="):
                        match = re.search(r"ID=([^,>]+)", line)
                        if match:
                            contigs_declared.append(match.group(1))
                    continue

                # Column Header Line (#CHROM ...)
                if line.startswith("#CHROM"):
                    has_column_header = True
                    columns = line.split("\t")
                    required_columns = ["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO"]
                    if columns[:8] != required_columns:
                        rejections.append(
                            RejectedRecord(
                                line_number=line_number,
                                raw_content=line,
                                rejection_reason=f"Column header does not match required fixed columns. Found: {columns[:8]}"
                            )
                        )
                        break

                    # Check for FORMAT and Sample columns
                    if len(columns) > 8:
                        if columns[8] == "FORMAT":
                            sample_names = columns[9:]
                            if sample_names:
                                contains_sample_genotypes = True
                                # Privacy check on sample names
                                for name in sample_names:
                                    if any(p in name.lower() for p in ["patient", "mrn", "ssn", "name"]):
                                        warnings.append(f"Sample name '{name}' may indicate sensitive personal information.")
                    continue

                # Data Line
                if not has_column_header:
                    rejections.append(
                        RejectedRecord(
                            line_number=line_number,
                            raw_content=line,
                            rejection_reason="Variant record encountered before #CHROM column header line."
                        )
                    )
                    break

                total_records += 1
                columns = line.split("\t")
                if len(columns) < 8:
                    rejections.append(
                        RejectedRecord(
                            line_number=line_number,
                            raw_content=line,
                            rejection_reason=f"Record has only {len(columns)} columns; expected at least 8."
                        )
                    )
                    continue

                chrom, pos_str, var_id, ref, alt_str, qual_str, filt, info = columns[:8]

                # Chromosome validation
                if chrom not in VALID_CHROMOSOMES:
                    rejections.append(
                        RejectedRecord(
                            line_number=line_number,
                            raw_content=line,
                            rejection_reason=f"Unrecognized human chromosome identifier: '{chrom}'."
                        )
                    )
                    continue

                # Position validation
                try:
                    pos = int(pos_str)
                    if pos < 1:
                        raise ValueError()
                except ValueError:
                    rejections.append(
                        RejectedRecord(
                            line_number=line_number,
                            raw_content=line,
                            rejection_reason=f"Position '{pos_str}' must be a 1-based positive integer."
                        )
                    )
                    continue

                # Reference allele validation
                if not DNA_PATTERN.match(ref):
                    rejections.append(
                        RejectedRecord(
                            line_number=line_number,
                            raw_content=line,
                            rejection_reason=f"Reference allele '{ref}' contains non-IUPAC DNA characters."
                        )
                    )
                    continue

                # Alternate allele validation (can be comma-separated)
                alts = alt_str.split(",")
                invalid_alt = False
                for alt in alts:
                    alt_clean = alt.strip()
                    # Standard DNA or symbolic/deletion allele
                    if not (DNA_PATTERN.match(alt_clean) or alt_clean in ["*", "."] or (alt_clean.startswith("<") and alt_clean.endswith(">"))):
                        rejections.append(
                            RejectedRecord(
                                line_number=line_number,
                                raw_content=line,
                                rejection_reason=f"Alternate allele '{alt_clean}' is not a valid nucleotide sequence or symbolic allele."
                            )
                        )
                        invalid_alt = True
                        break

                if invalid_alt:
                    continue

                accepted_records += 1

        finally:
            if not isinstance(filepath_or_stream, (str, Path)) and hasattr(filepath_or_stream, "seek"):
                filepath_or_stream.seek(0)
            else:
                stream.close()

        # Assembly Detection
        detected_assembly = detect_assembly_from_header(header_lines)
        if not detected_assembly:
            warnings.append("Reference genome assembly was not explicitly declared in VCF headers. Defaulting to GRCh38.")

        # Determine overall validity
        is_valid = has_column_header and accepted_records > 0 and len(rejections) == 0

        # If some records are accepted and some rejected, mark as valid with warnings or partial
        if has_column_header and accepted_records > 0 and len(rejections) > 0:
            is_valid = True
            warnings.append(f"{len(rejections)} record(s) failed validation and were excluded.")

        if total_records == 0 and has_column_header:
            warnings.append("VCF file contains valid headers but zero variant records.")

        return ValidationSummary(
            is_valid=is_valid,
            file_checksum=file_checksum,
            file_size_bytes=file_size_bytes,
            detected_assembly=detected_assembly,
            file_format=file_format_str,
            total_lines_read=line_number,
            total_records_read=total_records,
            accepted_variants_count=accepted_records,
            rejected_records_count=len(rejections),
            rejections=rejections,
            warnings=warnings,
            contigs_declared=contigs_declared,
            sample_names=sample_names,
            contains_sample_genotypes=contains_sample_genotypes
        )
