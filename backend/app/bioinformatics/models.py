"""
Data models and schemas for parsed genomic variants and validation summaries.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VariantType(str, Enum):
    SNV = "SNV"
    INSERTION = "INSERTION"
    DELETION = "DELETION"
    INDEL = "INDEL"
    MNV = "MNV"
    UNKNOWN = "UNKNOWN"


class ParsedVariant(BaseModel):
    """
    Standardized, validated representation of a single genomic variant.
    Multiallelic sites are expanded into distinct ParsedVariant records,
    preserving reference to the parent site and allele index.
    """
    chromosome: str = Field(..., description="Chromosome identifier, e.g. 'chr7' or '7'")
    position: int = Field(..., description="1-based genomic start position", ge=1)
    reference_allele: str = Field(..., description="Reference allele nucleotide sequence")
    alternate_allele: str = Field(..., description="Alternate allele nucleotide sequence")
    variant_id: Optional[str] = Field(None, description="dbSNP ID or variant identifier, e.g. 'rs113993960'")
    quality: Optional[float] = Field(None, description="Phred-scaled quality score")
    filter_status: str = Field("PASS", description="Filter status, e.g. 'PASS', 'LowQual'")
    info_fields: Dict[str, Any] = Field(default_factory=dict, description="Parsed INFO key-value annotations")
    genotype: Optional[str] = Field(None, description="Sample genotype if available, e.g. '0/1'")
    allele_index: int = Field(1, description="1-based index among alternate alleles in original record")
    is_multiallelic: bool = Field(False, description="Whether the original record contained multiple alternate alleles")
    original_line_number: Optional[int] = Field(None, description="Line number in the source VCF file")
    variant_type: VariantType = Field(VariantType.UNKNOWN, description="Classified variant type")

    def to_vep_format(self) -> str:
        """
        Converts variant to standard Ensembl VEP default input format:
        `chr start end ref/alt strand [identifier]`
        Coordinates are 1-based.
        """
        chrom = self.chromosome.replace("chr", "")
        start = self.position
        ref = self.reference_allele
        alt = self.alternate_allele

        if len(ref) == 1 and len(alt) == 1:
            # SNV: start == end
            end = start
        elif len(ref) > len(alt):
            # Deletion
            end = start + len(ref) - 1
        else:
            # Insertion
            end = start + max(1, len(ref)) - 1

        identifier = self.variant_id if self.variant_id and self.variant_id != "." else f"{chrom}_{start}_{ref}_{alt}"
        return f"{chrom} {start} {end} {ref}/{alt} + {identifier}"


class RejectedRecord(BaseModel):
    """
    Record of a line or variant that failed validation criteria.
    """
    line_number: int
    raw_content: str
    rejection_reason: str


class ValidationSummary(BaseModel):
    """
    Comprehensive summary of VCF file structure and content validation.
    """
    is_valid: bool = Field(..., description="True if file complies with VCF specification and contains valid variants")
    file_checksum: str = Field(..., description="SHA-256 hash of the input file")
    file_size_bytes: int = Field(..., description="File size in bytes")
    detected_assembly: Optional[str] = Field(None, description="Assembly identified in headers, e.g. GRCh38")
    file_format: Optional[str] = Field(None, description="VCF version format string, e.g. VCFv4.2")
    total_lines_read: int = 0
    total_records_read: int = 0
    accepted_variants_count: int = 0
    rejected_records_count: int = 0
    rejections: List[RejectedRecord] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    contigs_declared: List[str] = Field(default_factory=list)
    sample_names: List[str] = Field(default_factory=list)
    contains_sample_genotypes: bool = False

