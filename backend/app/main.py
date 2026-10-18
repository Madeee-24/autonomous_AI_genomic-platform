from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    os.makedirs(settings.UPLOAD_DIRECTORY, exist_ok=True)
    os.makedirs(settings.REPORT_DIRECTORY, exist_ok=True)
    logger.info(f"Storage directories initialized: {settings.UPLOAD_DIRECTORY}, {settings.REPORT_DIRECTORY}")
    
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

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
