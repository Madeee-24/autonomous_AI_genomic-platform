"""
Command-line interface to inspect, validate, and parse a VCF file.
Usage:
    python -m app.bioinformatics.cli_summary <path_to_vcf_file>
"""
import sys
from pathlib import Path
from app.bioinformatics.vcf_parser import VCFParser


def print_cli_summary(vcf_path_str: str) -> None:
    path = Path(vcf_path_str)
    if not path.exists():
        print(f"[ERROR] File not found: {vcf_path_str}", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print(f"GENOMIC VCF ANALYSIS & VALIDATION REPORT: {path.name}")
    print("=" * 80)

    parser = VCFParser()
    variants, summary = parser.parse(path, filename=path.name)

    print("\n--- 1. FILE & ASSEMBLY VALIDATION ---")
    print(f"File Status:             {'VALID' if summary.is_valid else 'INVALID'}")
    print(f"File Checksum (SHA256):  {summary.file_checksum}")
    print(f"File Size:               {summary.file_size_bytes} bytes")
    print(f"Detected Assembly:       {summary.detected_assembly or 'Unspecified (GRCh38 assumed)'}")
    print(f"VCF Specification:       {summary.file_format or 'Unknown'}")
    print(f"Declared Contigs:        {', '.join(summary.contigs_declared) if summary.contigs_declared else 'None'}")
    print(f"Samples Detected:        {', '.join(summary.sample_names) if summary.sample_names else 'None'}")

    print("\n--- 2. PARSING METRICS ---")
    print(f"Total Lines Read:        {summary.total_lines_read}")
    print(f"Total Raw Records:       {summary.total_records_read}")
    print(f"Accepted Variants:       {summary.accepted_variants_count}")
    print(f"Expanded Variants:       {len(variants)} (includes multiallelic splits)")
    print(f"Rejected Records:        {summary.rejected_records_count}")

    if summary.warnings:
        print("\n--- WARNINGS ---")
        for w in summary.warnings:
            print(f" [!] {w}")

    if summary.rejections:
        print("\n--- REJECTED RECORDS ---")
        for r in summary.rejections:
            print(f" [x] Line {r.line_number}: {r.rejection_reason}")

    print("\n--- 3. PARSED VARIANTS TABLE ---")
    header_fmt = "{:<8} {:<12} {:<14} {:<6} {:<6} {:<11} {:<8} {:<10} {:<6}"
    row_fmt    = "{:<8} {:<12} {:<14} {:<6} {:<6} {:<11} {:<8} {:<10} {:<6}"

    print(header_fmt.format("CHROM", "POSITION", "ID", "REF", "ALT", "TYPE", "QUAL", "FILTER", "MULTI"))
    print("-" * 84)

    for v in variants:
        print(row_fmt.format(
            v.chromosome,
            str(v.position),
            v.variant_id or ".",
            v.reference_allele[:5] + (".." if len(v.reference_allele) > 5 else ""),
            v.alternate_allele[:5] + (".." if len(v.alternate_allele) > 5 else ""),
            v.variant_type.value,
            f"{v.quality:.1f}" if v.quality else ".",
            v.filter_status,
            "YES" if v.is_multiallelic else "NO"
        ))

    print("-" * 84)
    print("\nVEP Input Strings Prepared for Annotation API:")
    for v in variants[:3]:
        print(f"  -> {v.to_vep_format()}")
    if len(variants) > 3:
        print(f"  ... ({len(variants) - 3} more variant coordinates)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.bioinformatics.cli_summary <path_to_vcf>")
        sys.exit(1)
    print_cli_summary(sys.argv[1])
