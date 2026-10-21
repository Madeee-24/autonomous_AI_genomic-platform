import os
from pathlib import Path
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    APP_NAME: str = "Autonomous AI Genomic Analysis Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # CORS configuration
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database connection string (PostgreSQL via psycopg3)
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/genomics_db"

    # File Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIRECTORY: str = str(Path(__file__).resolve().parent.parent.parent / "data" / "uploads")
    REPORT_DIRECTORY: str = str(Path(__file__).resolve().parent.parent.parent / "data" / "generated_reports")
    MAX_UPLOAD_SIZE_MB: int = 100

    # Genomics defaults
    DEFAULT_GENOME_ASSEMBLY: str = "GRCh38"
    SUPPORTED_ASSEMBLIES: List[str] = ["GRCh38", "GRCh37"]

    # External Bioinformatics APIs
    VEP_BASE_URL: str = "https://rest.ensembl.org"
    CLINVAR_BASE_URL: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # AI Configuration (Optional, non-blocking)
    LLM_PROVIDER: str = "none"  # e.g., "gemini", "openai", "none"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini-1.5-flash"


settings = Settings()

