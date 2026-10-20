from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.analyses import router as analyses_router
from app.api.datasets import router as datasets_router
from app.core.config import settings
from app.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown event lifecycle handler.
    Ensures secure data directories exist on startup.
    """
    logger.info("Initializing Autonomous AI Genomic Analysis Platform...")
    
    # Ensure local storage directories exist safely
    upload_path = Path(settings.UPLOAD_DIRECTORY).resolve()
    report_path = Path(settings.REPORT_DIRECTORY).resolve()
    os.makedirs(upload_path, exist_ok=True)
    os.makedirs(report_path, exist_ok=True)
    logger.info(f"Storage directories initialized: {upload_path}, {report_path}")
    
    yield
    
    logger.info("Shutting down Genomic Analysis Platform.")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Automated research-support platform for genomic variant validation, annotation, evidence retrieval, prioritization, and AI explanations.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Standardized Exception Handler
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": f"HTTP_{exc.status_code}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(
    datasets_router,
    prefix=f"{settings.API_V1_STR}/datasets",
    tags=["Datasets"]
)
app.include_router(
    analyses_router,
    prefix=f"{settings.API_V1_STR}/analyses",
    tags=["Analyses"]
)


@app.get("/", tags=["General"])
async def root_endpoint():
    """
    Root status endpoint providing API metadata and documentation link.
    """
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
        "api_v1_prefix": settings.API_V1_STR
    }


@app.get(f"{settings.API_V1_STR}/health", tags=["System Health"])
async def health_check():
    """
    System health check endpoint verifying service availability.
    """
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "default_assembly": settings.DEFAULT_GENOME_ASSEMBLY,
        "supported_assemblies": settings.SUPPORTED_ASSEMBLIES,
        "database_configured": bool(settings.DATABASE_URL),
        "vep_endpoint": settings.VEP_BASE_URL
    }
