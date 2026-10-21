"""
Audit-Ready Publication-Quality PDF Report Generator.
Uses ReportLab to produce formatted genomic variant prioritization reports,
including public evidence citations, transparent heuristic rationale, AI synthesis,
and prominent academic research disclaimers.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.analysis import AnalysisJob
from app.models.dataset import Dataset
from app.models.variant import Variant


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to calculate total page count and render professional
    running headers and footers ("Page X of Y").
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(
                40,
                11 * 72 - 30,
                "Autonomous AI Genomic Analysis Platform — Candidate Prioritization & Evidence Report",
            )
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(40, 11 * 72 - 34, 8.5 * 72 - 40, 11 * 72 - 34)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(40, 42, 8.5 * 72 - 40, 42)

        footer_text = "CONFIDENTIAL RESEARCH DOCUMENT — FOR INVESTIGATIONAL & RESEARCH PURPOSES ONLY"
        page_str = f"Page {self._pageNumber} of {total_pages}"

        self.drawString(40, 30, footer_text)
        self.drawRightString(8.5 * 72 - 40, 30, page_str)
        self.restoreState()


class GenomicReportGenerator:
    """
    Builds structured, audit-ready clinical research reports from analysis results.
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        # Color definitions
        self.c_primary = colors.HexColor("#0f172a")  # Slate-900
        self.c_brand = colors.HexColor("#1d4ed8")    # Blue-700
        self.c_slate = colors.HexColor("#475569")    # Slate-600
        self.c_border = colors.HexColor("#cbd5e1")   # Slate-300
        self.c_card_bg = colors.HexColor("#f8fafc")  # Slate-50
        self.c_amber_border = colors.HexColor("#f59e0b")
        self.c_amber_bg = colors.HexColor("#fffbeb")

        # Headings & Typography
        self.styles.add(
            ParagraphStyle(
                "DocTitle",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=self.c_primary,
                spaceAfter=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "DocSubtitle",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=11,
                leading=15,
                textColor=self.c_brand,
                spaceAfter=14,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "SectionHeader",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=17,
                textColor=self.c_primary,
                spaceBefore=14,
                spaceAfter=6,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "SubSectionHeader",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=14,
                textColor=self.c_primary,
                spaceBefore=8,
                spaceAfter=4,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "BodyDark",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=self.c_primary,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "BodyMuted",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=self.c_slate,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "TableHead",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=colors.white,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "TableCell",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=10.5,
                textColor=self.c_primary,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "TableCellBold",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10.5,
                textColor=self.c_primary,
            )
        )
        self.styles.add(
            ParagraphStyle(
                "DisclaimerText",
                parent=self.styles["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11.5,
                textColor=colors.HexColor("#92400e"),  # Amber-800
            )
        )
        self.styles.add(
            ParagraphStyle(
                "DisclaimerBold",
                parent=self.styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#78350f"),  # Amber-900
                spaceAfter=2,
            )
        )

    def generate_report(
        self,
        output_path: str,
        job: AnalysisJob,
        dataset: Dataset,
        variants: List[Variant],
    ) -> str:
        """
        Renders the complete genomic audit report to the specified file path.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=46,
            bottomMargin=46,
        )

        story = []

        # 1. Document Title & Header
        story.append(Paragraph("Autonomous AI Genomic Analysis Platform", self.styles["DocTitle"]))
        story.append(
            Paragraph(
                "Clinical Bioinformatics Variant Prioritization & Evidence Audit",
                self.styles["DocSubtitle"],
            )
        )

        # 2. Mandatory Research Disclaimer Box
        story.append(self._build_disclaimer_box())
        story.append(Spacer(1, 10))

        # 3. Metadata & Provenance Summary Table
        story.append(self._build_metadata_section(job, dataset))
        story.append(Spacer(1, 12))

        # 4. Executive Summary & Tier Metrics
        story.append(self._build_metrics_section(job, variants))
        story.append(Spacer(1, 12))

        # 5. Top Prioritized Candidates Summary Table
        story.append(Paragraph("1. Candidate Variant Prioritization Summary", self.styles["SectionHeader"]))
        story.append(
            Paragraph(
                "Variants evaluated using transparent rule matrix v1.0 combining Ensembl VEP transcript consequence annotations, "
                "ClinVar germline assertions, and review status confidence.",
                self.styles["BodyMuted"],
            )
        )
        story.append(Spacer(1, 6))
        story.append(self._build_candidates_table(variants))
        story.append(Spacer(1, 14))

        # 6. Detailed Candidate Profiles (Top 5 variants)
        story.append(Paragraph("2. Detailed Evidence & AI Scientific Synthesis", self.styles["SectionHeader"]))
        story.append(
            Paragraph(
                "Individual profiles showing functional consequences, NCBI ClinVar submissions, conflicting interpretations, "
                "and zero-hallucination evidence-grounded AI explanations.",
                self.styles["BodyMuted"],
            )
        )
        story.append(Spacer(1, 8))

        top_candidates = [v for v in variants if v.prioritization][:5]
        if not top_candidates:
            top_candidates = variants[:5]

        for idx, variant in enumerate(top_candidates, 1):
            story.append(self._build_variant_detail_card(idx, variant))
            story.append(Spacer(1, 10))

        # 7. Audit Trail & Tooling Environment
        story.append(Spacer(1, 6))
        story.append(Paragraph("3. Technical Provenance & System Audit Trail", self.styles["SectionHeader"]))
        story.append(self._build_audit_table(job))

        # Build document
        doc.build(story, canvasmaker=NumberedCanvas)
        return output_path

    def _build_disclaimer_box(self) -> Table:
        content = [
            Paragraph(
                "RESEARCH-SUPPORT ONLY — NOT FOR CLINICAL DIAGNOSTIC USE",
                self.styles["DisclaimerBold"],
            ),
            Paragraph(
                "This report is generated by an automated computational pipeline designed strictly for academic, educational, and investigational research support. "
                "The findings, heuristic priority tiers, and AI-synthesized summaries do NOT constitute medical advice, clinical diagnoses, or therapeutic recommendations. "
                "Negative or absent annotations do not imply evidence of absence. Any potential clinical actionable variants must be orthogonally verified by an accredited molecular diagnostics laboratory.",
                self.styles["DisclaimerText"],
            ),
        ]
        box_table = Table([[content]], colWidths=[532])
        box_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), self.c_amber_bg),
                ("BOX", (0, 0), (-1, -1), 1, self.c_amber_border),
                ("PADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        return box_table

    def _build_metadata_section(self, job: AnalysisJob, dataset: Dataset) -> Table:
        cfg = job.configuration_json or {}
        assembly = cfg.get("genome_assembly", dataset.assembly or "GRCh38")
        opts = cfg.get("options", {})

        data = [
            [
                Paragraph("<b>Analysis Job ID:</b>", self.styles["TableCellBold"]),
                Paragraph(job.id, self.styles["TableCell"]),
                Paragraph("<b>Execution Status:</b>", self.styles["TableCellBold"]),
                Paragraph(f"<b>{job.status}</b>", self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Source Dataset:</b>", self.styles["TableCellBold"]),
                Paragraph(dataset.original_filename or "N/A", self.styles["TableCell"]),
                Paragraph("<b>Reference Assembly:</b>", self.styles["TableCellBold"]),
                Paragraph(assembly, self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>SHA-256 Provenance:</b>", self.styles["TableCellBold"]),
                Paragraph(f"<font size=7>{dataset.file_checksum[:32]}...</font>", self.styles["TableCell"]),
                Paragraph("<b>Date Generated:</b>", self.styles["TableCellBold"]),
                Paragraph(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>Pipeline Features:</b>", self.styles["TableCellBold"]),
                Paragraph(
                    f"VEP: {'Enabled' if opts.get('annotate_with_vep') else 'Disabled'} | "
                    f"ClinVar: {'Enabled' if opts.get('retrieve_clinvar_evidence') else 'Disabled'} | "
                    f"AI: {'Enabled' if opts.get('generate_ai_explanations') else 'Disabled'}",
                    self.styles["TableCell"],
                ),
                Paragraph("<b>Orchestrator:</b>", self.styles["TableCellBold"]),
                Paragraph("v1.0 Resilient Graph", self.styles["TableCell"]),
            ],
        ]

        table = Table(data, colWidths=[110, 166, 110, 146])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), self.c_card_bg),
                ("BOX", (0, 0), (-1, -1), 0.5, self.c_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 4.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        return table

    def _build_metrics_section(self, job: AnalysisJob, variants: List[Variant]) -> Table:
        tier_counts = {"TIER_1_CRITICAL": 0, "TIER_2_HIGH": 0, "TIER_3_MODERATE": 0, "TIER_4_LOW": 0, "UNCERTAIN": 0}
        total_annotations = 0
        total_evidence = 0
        conflict_count = 0

        for v in variants:
            if v.prioritization:
                cat = v.prioritization.priority_category
                tier_counts[cat] = tier_counts.get(cat, 0) + 1
            if v.annotations:
                total_annotations += len(v.annotations)
            if v.evidence_records:
                total_evidence += len(v.evidence_records)
                if any(e.has_conflicts for e in v.evidence_records):
                    conflict_count += 1

        data = [
            [
                Paragraph("<b>Total Variants Evaluated</b>", self.styles["TableHead"]),
                Paragraph("<b>Annotations (VEP)</b>", self.styles["TableHead"]),
                Paragraph("<b>ClinVar Records</b>", self.styles["TableHead"]),
                Paragraph("<b>Conflicting Assertions</b>", self.styles["TableHead"]),
                Paragraph("<b>Tier 1 Critical</b>", self.styles["TableHead"]),
                Paragraph("<b>Tier 2 High</b>", self.styles["TableHead"]),
            ],
            [
                Paragraph(f"<font size=11><b>{len(variants)}</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<font size=11><b>{total_annotations}</b></font>", self.styles["TableCell"]),
                Paragraph(f"<font size=11><b>{total_evidence}</b></font>", self.styles["TableCell"]),
                Paragraph(
                    f"<font size=11 color={'#b91c1c' if conflict_count else '#334155'}><b>{conflict_count}</b></font>",
                    self.styles["TableCell"],
                ),
                Paragraph(f"<font size=11 color='#dc2626'><b>{tier_counts['TIER_1_CRITICAL']}</b></font>", self.styles["TableCellBold"]),
                Paragraph(f"<font size=11 color='#ea580c'><b>{tier_counts['TIER_2_HIGH']}</b></font>", self.styles["TableCellBold"]),
            ],
        ]

        table = Table(data, colWidths=[90, 88, 88, 92, 87, 87])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), self.c_brand),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, self.c_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ])
        )
        return table

    def _build_candidates_table(self, variants: List[Variant]) -> Table:
        # Sort variants by prioritization score descending
        sorted_variants = sorted(
            variants,
            key=lambda v: (v.prioritization.score if v.prioritization and v.prioritization.score is not None else -1),
            reverse=True,
        )

        headers = [
            Paragraph("<b>Rank</b>", self.styles["TableHead"]),
            Paragraph("<b>Coordinate</b>", self.styles["TableHead"]),
            Paragraph("<b>Identifier</b>", self.styles["TableHead"]),
            Paragraph("<b>Gene</b>", self.styles["TableHead"]),
            Paragraph("<b>Consequence / Impact</b>", self.styles["TableHead"]),
            Paragraph("<b>ClinVar Assertion</b>", self.styles["TableHead"]),
            Paragraph("<b>Priority Tier</b>", self.styles["TableHead"]),
            Paragraph("<b>Score</b>", self.styles["TableHead"]),
        ]
        rows = [headers]

        for rank, v in enumerate(sorted_variants[:12], 1):
            coord = f"{v.chromosome}:{v.position} {v.reference_allele}&gt;{v.alternate_allele}"
            ident = v.variant_identifier if v.variant_identifier and v.variant_identifier != "." else "-"

            # Gene & consequence
            gene = "-"
            csq = "-"
            if v.annotations:
                primary_anno = v.annotations[0]
                gene = primary_anno.gene_symbol or primary_anno.gene_id or "-"
                csq = f"{primary_anno.consequence.replace('_', ' ')} ({primary_anno.impact})"

            # ClinVar
            cv_text = "No submission"
            if v.evidence_records:
                ev = v.evidence_records[0]
                cv_text = ev.interpretation or "Recorded"
                if ev.has_conflicts:
                    cv_text += " [CONFLICT]"

            # Priority
            p_cat = v.prioritization.priority_category.replace("TIER_", "T") if v.prioritization else "N/A"
            p_score = f"{v.prioritization.score:.1f}" if v.prioritization and v.prioritization.score is not None else "-"

            rows.append([
                Paragraph(str(rank), self.styles["TableCellBold"]),
                Paragraph(f"<font size=7.5>{coord}</font>", self.styles["TableCell"]),
                Paragraph(ident, self.styles["TableCell"]),
                Paragraph(f"<b>{gene}</b>", self.styles["TableCell"]),
                Paragraph(csq, self.styles["TableCell"]),
                Paragraph(cv_text, self.styles["TableCell"]),
                Paragraph(f"<b>{p_cat}</b>", self.styles["TableCellBold"]),
                Paragraph(p_score, self.styles["TableCellBold"]),
            ])

        table = Table(rows, colWidths=[32, 105, 55, 48, 115, 95, 46, 36])
        t_style = [
            ("BACKGROUND", (0, 0), (-1, 0), self.c_primary),
            ("BOX", (0, 0), (-1, -1), 0.5, self.c_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 3.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]

        # Alternating row colors
        for r in range(1, len(rows)):
            bg = colors.HexColor("#f8fafc") if r % 2 == 0 else colors.white
            t_style.append(("BACKGROUND", (0, r), (-1, r), bg))

        table.setStyle(TableStyle(t_style))
        return table

    def _build_variant_detail_card(self, index: int, variant: Variant) -> KeepTogether:
        coord = f"{variant.chromosome}:{variant.position} {variant.reference_allele}&gt;{variant.alternate_allele}"
        ident = f" ({variant.variant_identifier})" if variant.variant_identifier and variant.variant_identifier != "." else ""
        tier = variant.prioritization.priority_category if variant.prioritization else "UNCERTAIN"
        score = f"{variant.prioritization.score:.1f}" if variant.prioritization and variant.prioritization.score is not None else "N/A"

        header_p = Paragraph(
            f"<b>Candidate {index}: {coord}{ident}</b> — Tier: <b>{tier}</b> (Score: {score}/100)",
            self.styles["SubSectionHeader"],
        )

        card_elements = [header_p]

        # Prioritization Rationale
        if variant.prioritization and variant.prioritization.reasons_json:
            reasons = variant.prioritization.reasons_json.get("reasons", [])
            if reasons:
                reasons_str = "; ".join(reasons)
                card_elements.append(
                    Paragraph(f"<b>Prioritization Rationale:</b> {reasons_str}", self.styles["TableCell"])
                )

        # Annotations (VEP)
        if variant.annotations:
            anno_strs = [
                f"{a.gene_symbol or a.gene_id or 'Gene'}: {a.consequence} [Impact: {a.impact}]"
                for a in variant.annotations[:3]
            ]
            card_elements.append(
                Paragraph(f"<b>Functional Impact:</b> {' | '.join(anno_strs)}", self.styles["TableCell"])
            )

        # ClinVar Evidence
        if variant.evidence_records:
            ev_strs = []
            for e in variant.evidence_records[:2]:
                ev_str = f"Accession: {e.source_accession or 'N/A'}, Significance: {e.interpretation}, Review: {e.review_status or 'Not specified'}"
                if e.has_conflicts:
                    ev_str += " <font color='#b91c1c'><b>(Conflicting Interpretations)</b></font>"
                if e.evidence_summary:
                    ev_str += f" | {e.evidence_summary}"
                ev_strs.append(ev_str)
            card_elements.append(
                Paragraph(f"<b>Public Clinical Evidence:</b> {'<br/>'.join(ev_strs)}", self.styles["TableCell"])
            )
        else:
            card_elements.append(
                Paragraph(
                    "<b>Public Clinical Evidence:</b> <font color='#64748b'>No ClinVar assertions identified (Absence is not proof of benignity).</font>",
                    self.styles["TableCell"],
                )
            )

        # AI Grounded Explanation
        if variant.ai_explanation:
            exp = variant.ai_explanation
            ai_text = exp.explanation_text
            card_elements.append(Spacer(1, 3))
            ai_box = [
                Paragraph(
                    f"<b>Evidence-Grounded AI Explanation ({exp.model_provider} / {exp.model_name}):</b>",
                    self.styles["TableCellBold"],
                ),
                Paragraph(ai_text, self.styles["TableCell"]),
            ]
            if exp.structured_output_json and exp.structured_output_json.get("uncertainties"):
                unc = "; ".join(exp.structured_output_json.get("uncertainties", []))
                ai_box.append(
                    Paragraph(f"<i>Scientific Limitations & Uncertainties:</i> {unc}", self.styles["BodyMuted"])
                )
            ai_table = Table([[ai_box]], colWidths=[518])
            ai_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ])
            )
            card_elements.append(ai_table)

        wrapper_table = Table([[card_elements]], colWidths=[532])
        wrapper_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), self.c_card_bg),
                ("BOX", (0, 0), (-1, -1), 0.5, self.c_border),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )

        return KeepTogether(wrapper_table)

    def _build_audit_table(self, job: AnalysisJob) -> Table:
        data = [
            [
                Paragraph("<b>Component / Service</b>", self.styles["TableHead"]),
                Paragraph("<b>Version / Endpoint</b>", self.styles["TableHead"]),
                Paragraph("<b>Designation & Integrity Policy</b>", self.styles["TableHead"]),
            ],
            [
                Paragraph("Workflow Graph Orchestrator", self.styles["TableCellBold"]),
                Paragraph("v1.0 Resilient Checkpointing", self.styles["TableCell"]),
                Paragraph("Idempotent stage graph with bounded retry policy & cooperative cancellation", self.styles["TableCell"]),
            ],
            [
                Paragraph("Ensembl VEP REST Service", self.styles["TableCellBold"]),
                Paragraph("https://rest.ensembl.org", self.styles["TableCell"]),
                Paragraph("Deterministic transcript consequences, 1-based coordinates, rate-limited backoff", self.styles["TableCell"]),
            ],
            [
                Paragraph("NCBI Entrez ClinVar", self.styles["TableCellBold"]),
                Paragraph("esearch & esummary E-Utilities", self.styles["TableCell"]),
                Paragraph("Direct genomic coordinates lookup; submitter disagreement conflict detection", self.styles["TableCell"]),
            ],
            [
                Paragraph("Prioritization Engine", self.styles["TableCellBold"]),
                Paragraph("Matrix v1.0 (Heuristic)", self.styles["TableCell"]),
                Paragraph("Scores 0-100, Tier 1-4 stratification, transparent audit reasoning", self.styles["TableCell"]),
            ],
            [
                Paragraph("Evidence-Grounded AI Engine", self.styles["TableCellBold"]),
                Paragraph("Prompt v1.0 Guardrails", self.styles["TableCell"]),
                Paragraph("Zero-hallucination synthesis grounded strictly on retrieved records; no medical claims", self.styles["TableCell"]),
            ],
        ]

        table = Table(data, colWidths=[150, 160, 222])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), self.c_primary),
                ("BOX", (0, 0), (-1, -1), 0.5, self.c_border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
        )
        return table


pdf_generator = GenomicReportGenerator()
