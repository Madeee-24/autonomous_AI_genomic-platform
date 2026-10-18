# Windows Development & Setup Guide

This guide describes how to configure and run the **Autonomous AI Genomic Analysis Platform** on Windows 10/11 using PowerShell.

---

## 1. Prerequisites Checklist

Ensure the following tools are installed on your machine:
- **Python:** Python 3.12 or 3.13 (64-bit) — verify with `py -0p` or `python --version`.
- **Node.js:** Node v18+ (tested with Node v24) and npm — verify with `node -v` and `npm -v`.
- **Git:** Git for Windows — verify with `git --version`.
- **PostgreSQL:** Local PostgreSQL server or Docker container (optional for Phase 0/1 testing; required for Phase 3 onwards).

---

## 2. Windows-Specific Bioinformatics Considerations

### 1. VCF Parsing: `cyvcf2` vs. `vcfpy`
- `cyvcf2` requires compilation of `htslib` (a C library used for high-throughput sequencing).
- On native Windows, building `htslib` from source requires Visual Studio C++ Build Tools and POSIX C headers (`unistd.h`, `sys/resource.h`), which causes build failures on standard Windows environments.
- **Solution:** This platform provides a clean, abstract interface (`VCFParserInterface`). In cross-platform environments (like Windows PowerShell), it uses `vcfpy`, which handles standard VCFv4.2/4.3 parsing natively without requiring C compilers. If deployed in Linux, WSL2, or Docker, `cyvcf2` can be activated transparently.

### 2. Ensembl VEP (Variant Effect Predictor)
- A full local VEP installation requires Perl, BioPerl, and 20–30 GB of downloaded transcript caches.
- **Solution:** The platform connects to the official Ensembl VEP REST API (`https://rest.ensembl.org`), with automated batching and rate-limit backoff. This allows full consequence annotations without demanding excessive disk space.

---

## 3. Step-by-Step PowerShell Setup Commands

### Step A: Clone or Navigate to the Project
```powershell
cd "E:\Major project"
```

### Step B: Configure the Python Backend Virtual Environment
```powershell
# Navigate to backend
cd backend

# Create virtual environment with Python 3.13 (or 3.12)
py -3.13 -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Run backend unit tests to verify installation
pytest
```

### Step C: Verify the Backend API
Start the FastAPI server:
```powershell
uvicorn app.main:app --reload --port 8000
```
Open your browser and navigate to:
- Health check: `http://localhost:8000/api/v1/health`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

### Step D: Configure the React Frontend
In a **new PowerShell window**:
```powershell
cd "E:\Major project\frontend"

# Install dependencies (already prepared)
npm install

# Start the Vite development server
npm run dev
```
Open your browser and navigate to: `http://localhost:5173`
