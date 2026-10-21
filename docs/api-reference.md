# API Reference Manual

Autonomous AI Genomic Analysis Platform REST API specifications and OpenAPI schema documentation.

**Base URL:** `/api/v1`  
**Interactive Docs:** `http://localhost:8000/docs` (Swagger UI) & `http://localhost:8000/redoc` (ReDoc)

---

## 1. Datasets Management

### `POST /api/v1/datasets/upload`
Uploads and validates a genomic VCF or bgzipped VCF file (`.vcf`, `.vcf.gz`).
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  - `file`: Binary file content.
  - `assembly` *(optional)*: Target reference assembly (`GRCh38` or `GRCh37`).
- **Response (201 Created):**
```json
{
  "dataset_id": "800b69a0-8fa1-4472-a066-413b9945dc1d",
  "original_filename": "sample.vcf",
  "stored_filename": "800b69a0-8fa1-4472-a066-413b9945dc1d_sample.vcf",
  "file_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "file_size_bytes": 1133,
  "assembly": "GRCh38",
  "validation_summary": {
    "is_valid": true,
    "total_records_read": 6,
    "accepted_variants_count": 6,
    "sample_names": ["SAMPLE01"]
  },
  "uploaded_at": "2026-10-21T10:00:00Z"
}
```

### `POST /api/v1/datasets/validate-only`
Inspects VCF structure and header specifications without saving the file to persistent storage.

### `GET /api/v1/datasets`
Lists all uploaded datasets with metadata, assembly declarations, and variant counts.

---

## 2. Genomic Analysis Orchestration

### `POST /api/v1/analyses`
Creates and queues an asynchronous multi-stage genomic analysis pipeline job.
- **Request Body (JSON):**
```json
{
  "dataset_id": "800b69a0-8fa1-4472-a066-413b9945dc1d",
  "genome_assembly": "GRCh38",
  "options": {
    "annotate_with_vep": true,
    "retrieve_clinvar_evidence": true,
    "generate_ai_explanations": true
  }
}
```
- **Response (202 Accepted):** Returns initialized `AnalysisJob` entity in `QUEUED` status.

### `GET /api/v1/analyses/{analysis_id}`
Retrieves execution status, current stage, variant count, timing, and error metadata.

### `POST /api/v1/analyses/{analysis_id}/cancel`
Cooperatively halts an active or queued pipeline job.

### `POST /api/v1/analyses/{analysis_id}/resume`
Resumes an interrupted or failed analysis from its last recorded stage checkpoint, skipping verified stages.

### `GET /api/v1/analyses/{analysis_id}/checkpoints`
Returns stage checkpoint map, status (`COMPLETED`, `SKIPPED`, `FAILED`), metrics, and bounded retry counters.

### `GET /api/v1/analyses/{analysis_id}/events`
Returns chronological workflow stage transitions and audit log records.

### `GET /api/v1/analyses/{analysis_id}/statistics`
Aggregates variant distributions across consequence terms, impact levels, ClinVar interpretations, and heuristic priority tiers.

### `GET /api/v1/analyses/dashboard/summary`
System-wide metrics: total datasets, analyses, processed variants, and priority tier distribution.

---

## 3. Variant Exploration

### `GET /api/v1/analyses/{analysis_id}/variants`
Paginated, filtered list of variants with relational eager loading.
- **Query Parameters:**
  - `chromosome`: Filter by chromosome (e.g. `chr17`, `17`).
  - `gene`: Filter by gene symbol (e.g. `TP53`, `CFTR`).
  - `consequence`: Filter by VEP consequence (e.g. `missense_variant`).
  - `priority_category`: Filter by tier (`TIER_1_CRITICAL`, `TIER_2_HIGH`, `TIER_3_MODERATE`, `TIER_4_LOW`, `UNCERTAIN`).
  - `has_conflicts`: Filter variants with submitter disagreements (`true`/`false`).
  - `search`: Substring search over dbSNP rsID, gene symbol, or coordinate.
  - `page`: Page index (default: `1`).
  - `page_size`: Items per page (default: `25`, max: `200`).

### `GET /api/v1/analyses/{analysis_id}/variants/{variant_id}`
Returns complete variant detail including all transcript consequences, ClinVar records, and heuristic scoring rationale.

---

## 4. Evidence-Grounded AI Explanations

### `POST /api/v1/analyses/{analysis_id}/variants/{variant_id}/explain`
Generates an on-demand, evidence-grounded scientific explanation for a candidate variant.
- Strict Pydantic guardrails reject clinical diagnoses or unsubstantiated claims.
- Returns structured JSON: summary, biological mechanisms, evidence references, and clinical uncertainties.

### `GET /api/v1/analyses/{analysis_id}/variants/{variant_id}/explanation`
Retrieves stored AI explanation and provenance metadata for a variant.

---

## 5. Audit-Ready PDF Reporting

### `POST /api/v1/analyses/{analysis_id}/reports`
Synthesizes completed analysis outputs into a publication-quality ReportLab PDF document with running headers/footers, metadata tables, tier breakdowns, and research disclaimers.

### `GET /api/v1/analyses/{analysis_id}/reports`
Lists all generated PDF report records for an analysis.

### `GET /api/v1/analyses/{analysis_id}/report/download`
Streams the latest PDF report document as a binary attachment (`application/pdf`).

### `GET /api/v1/reports/{report_id}/download`
Streams a specific PDF report by its report ID.
