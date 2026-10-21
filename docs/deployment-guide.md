# Production Deployment Guide

Comprehensive instructions for deploying the **Autonomous AI Genomic Analysis Platform** across local servers, Docker container stacks, and cloud infrastructure.

---

## 1. Deployment Architecture Overview

The platform uses a decoupled three-tier architecture:

```mermaid
flowchart TD
    Client([User Browser]) -->|HTTPS: 443 / HTTP: 80| Nginx[Nginx Reverse Proxy\nFrontend Container]
    Nginx -->|Static Assets| SPA[React 19 Single Page App]
    Nginx -->|Reverse Proxy /api/*| Backend[FastAPI Backend Container\nUvicorn ASGI Engine]
    Backend -->|PostgreSQL Wire Protocol| Postgres[(PostgreSQL 16 Database\nPersistent Volume)]
    Backend -->|Persistent Storage| Storage[(Uploads & Reports Storage\nDocker Volumes / EBS / S3)]
    Backend -->|HTTPS REST| VEP[Ensembl VEP REST API]
    Backend -->|HTTPS E-Utilities| ClinVar[NCBI ClinVar]
    Backend -->|HTTPS LLM API| AI[Gemini / OpenAI / Mock]
```

---

## 2. Option A: One-Command Docker Compose Deployment (Recommended)

The easiest and most reliable method to deploy the complete platform locally or on any Linux / Windows / macOS virtual machine.

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) or Docker Engine + Docker Compose plugin (Linux).

### Deployment Steps
```bash
# 1. Clone or navigate to the project directory
cd "Major project"

# 2. Build images and start all three containers in detached mode
docker compose up --build -d

# 3. Verify container statuses
docker compose ps
```

### Accessing Services
- **Web Application:** `http://localhost` (or `http://localhost:5173`)
- **API Documentation (Swagger UI):** `http://localhost:8000/docs`
- **Backend Health Check:** `http://localhost:8000/api/v1/health`

### Managing Containers
```bash
# View real-time logs
docker compose logs -f backend

# Stop services safely
docker compose down

# Stop and wipe database data (clean slate)
docker compose down -v
```

---

## 3. Option B: Cloud Platform Deployments

### 1. Render.com
1. **Web Service (Backend):**
   - Environment: `Python` (or `Docker`)
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
2. **Managed Database:**
   - Create a **PostgreSQL** instance on Render.
   - Copy the internal Database URL and add it as `DATABASE_URL` in the backend environment variables.
3. **Static Site (Frontend):**
   - Root Directory: `frontend`
   - Build Command: `npm install && npm run build`
   - Publish Directory: `dist`
   - Rewrite rule: `/*` $\rightarrow$ `/index.html` (200 Rewrite).

### 2. Railway.app
- Connect your GitHub repository.
- Railway detects `docker-compose.yml` automatically and deploys `postgres`, `backend`, and `frontend` in a private virtual network.

### 3. AWS (EC2 / Lightsail / ECS Fargate)
1. Launch an Ubuntu 24.04 LTS EC2 instance (recommended: `t3.medium`, 2 vCPU, 4GB RAM).
2. Install Docker and Docker Compose:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
   sudo systemctl enable --now docker
   ```
3. Clone repository, configure `.env`, and run `docker compose up --build -d`.
4. Configure Security Group allowing inbound traffic on ports `80` (HTTP) and `443` (HTTPS).

---

## 4. Production Environment Variables Checklist

For production, ensure the following environment settings are configured in `backend/.env` or container environment variables:

| Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | Enables production security policies |
| `DEBUG` | `False` | Disables debug logs and traceback exposure |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/dbname` | Production PostgreSQL connection with SSL |
| `BACKEND_CORS_ORIGINS` | `["https://your-domain.com"]` | Restricts API access to authorized frontend domains |
| `UPLOAD_DIRECTORY` | `/app/data/uploads` | Persistent directory for private VCF storage |
| `REPORT_DIRECTORY` | `/app/data/generated_reports` | Persistent directory for generated PDF reports |
| `MAX_UPLOAD_SIZE_MB` | `100` | Maximum VCF upload size cap |
| `DEFAULT_GENOME_ASSEMBLY` | `GRCh38` | Default human genome build |
| `LLM_PROVIDER` | `mock` / `gemini` / `openai` | AI provider for scientific explanations |
| `LLM_API_KEY` | *(Secret Key)* | API key if using Gemini or OpenAI |

---

## 5. Security & Academic Data Privacy Hardening

1. **Genomic Privacy & Upload Isolation:**
   - Raw VCF files and ReportLab PDF documents are stored outside the web root in private directories (`data/uploads` and `data/generated_reports`).
   - Files are served strictly through authenticated/authorized FastAPI streaming endpoints with file existence validation.
2. **Reverse Proxy SSL/TLS:**
   - In production, place Nginx behind Let's Encrypt (Certbot) or Cloudflare SSL to enforce HTTPS encryption for all VCF uploads in transit.
3. **Database Security:**
   - Database credentials should never use default passwords.
   - Use non-root PostgreSQL service accounts with least privilege.
4. **Research Boundaries:**
   - All PDF reports and dashboard screens prominently embed mandatory academic disclaimers reminding researchers that findings are for investigational research support and not medical diagnosis.

---

## 6. Health Checks & Disaster Recovery

- **Liveness & Readiness Probe:**  
  `GET http://localhost:8000/api/v1/health` returns `{"status": "healthy"}` and confirms database and external API reachability.
- **Database Backup:**
  ```bash
  docker exec -t genomics_postgres pg_dump -U postgres genomics_db > backup_$(date +%Y%m%d).sql
  ```
- **Database Restore:**
  ```bash
  cat backup_file.sql | docker exec -i genomics_postgres psql -U postgres -d genomics_db
  ```

