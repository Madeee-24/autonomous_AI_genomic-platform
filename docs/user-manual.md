# User & Examiner Manual

Step-by-step walkthrough for evaluating and running the Autonomous AI Genomic Analysis Platform.

---

## 1. Prerequisites & System Requirements

- **Operating System:** Windows 10/11 x64, macOS, or Linux.
- **Python:** Python 3.12 or 3.13 (`backend/.venv`).
- **Node.js:** Node.js v18+ and npm (`frontend`).
- **Database (Optional for production):** PostgreSQL 16 (or Docker Compose). *Note: The automated test suite runs out-of-the-box using in-memory SQLite with zero external dependencies.*

---

## 2. Launching the Platform

### Terminal 1: Backend API Service
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```
- API Documentation (Swagger UI): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`

### Terminal 2: Frontend User Interface
```powershell
cd frontend
npm run dev
```
- Web Application: `http://localhost:5173`

---

## 3. End-to-End Walkthrough

### Step 1: Upload a Genomic VCF Dataset
1. Open `http://localhost:5173` and click **Upload Dataset** in the navigation bar.
2. Drag and drop or browse for `data/test_fixtures/sample.vcf`.
3. Choose the reference genome assembly (`GRCh38` default).
4. Click **Upload & Validate VCF**. The preflight validator checks header declarations and variant syntax, displaying a green validation banner.

### Step 2: Configure & Launch an Analysis
1. Select the uploaded dataset from the table and click **Start Analysis**.
2. Configure pipeline options:
   - **Ensembl VEP Annotation:** Maps functional consequence terms and transcript IDs.
   - **ClinVar Evidence Retrieval:** Queries public clinical submissions and checks for conflicts.
   - **Evidence-Grounded AI Explanations:** Synthesizes candidate variants into research summaries.
3. Click **Launch Analysis Pipeline**.

### Step 3: Real-Time Execution Monitoring
1. You are automatically navigated to the **Analysis Details** page.
2. The interactive stage timeline displays real-time progression through:
   - `VALIDATING` $\rightarrow$ `PARSING` $\rightarrow$ `ANNOTATING` $\rightarrow$ `RETRIEVING_EVIDENCE` $\rightarrow$ `PRIORITIZING` $\rightarrow$ `GENERATING_EXPLANATIONS` $\rightarrow$ `FINISHED`.
3. The **Audit Event Stream** logs all stage transitions, retry counters, and warnings with ISO timestamps.

### Step 4: Variant Explorer & Candidate Prioritization
1. Click **Open Variant Explorer** or select **Variant Explorer** in the sidebar.
2. Filter candidates by:
   - **Priority Tier:** `Tier 1 Critical`, `Tier 2 High`, `Tier 3 Moderate`, `Tier 4 Low`, `Uncertain`.
   - **ClinVar Evidence:** Filter variants with submitter disagreements (`Conflicting Assertions`).
   - **Gene Symbol:** e.g., `TP53`, `CFTR`.
   - **Consequence Term:** e.g., `missense_variant`, `frameshift_variant`.
3. Click any variant row to open the **Variant Details Modal**, displaying:
   - Priority score and heuristic rule rationale.
   - All transcript consequences and impact levels from Ensembl VEP.
   - NCBI ClinVar review stars, accessions, and phenotype associations.
   - Live button to generate on-demand evidence-grounded AI explanations.

### Step 5: Exporting Audit-Ready PDF Reports
1. In the **Analysis Details** header, click **Download PDF Report**, or navigate to **Reports** in the sidebar.
2. The platform instantly renders a publication-quality ReportLab PDF document containing:
   - Formal institutional header and file SHA-256 provenance.
   - Prominent academic research disclaimer.
   - Priority tier breakdown and executive metrics.
   - Top candidate variants table with score and consequence mappings.
   - Detailed candidate evidence cards and AI explanations.
   - Technical provenance and pipeline audit trail.

### Step 6: Cooperative Cancellation & Checkpoint Recovery
1. While an analysis is running, click **Cancel Job** to halt execution gracefully.
2. The job transitions to `CANCELLED` status and records partial checkpoints.
3. Click **Resume from Checkpoint** to restart the pipeline; verified stages are skipped and processing resumes at the interrupted stage.

---

## 4. Running the Automated Test Suite

To verify all 80 unit, integration, and security guardrail tests:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```
All tests execute in ~10 seconds with 100% pass rate.
