"""
Dataset Service: Orchestrates secure file ingestion, validation, and storage.
"""
import io
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.bioinformatics.validator import VCFValidator
from app.core.config import settings
from app.core.logging import logger
from app.models.dataset import Dataset
from app.repositories.dataset_repository import dataset_repo
from app.schemas.dataset import (
    DatasetListItem,
    DatasetListResponse,
    DatasetUploadResponse,
    ValidationOnlyResponse,
)


def sanitize_filename(filename: str) -> str:
    """
    Strips directory traversal sequences, path separators, and unsafe characters.
    """
    base = os.path.basename(filename)
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    if not clean:
        clean = "unnamed.vcf"
    return clean


class DatasetService:
    """
    Manages VCF dataset uploads, validation, storage, and metadata retrieval.
    """

    def __init__(self, validator: Optional[VCFValidator] = None):
        self.validator = validator or VCFValidator()
        self.upload_dir = Path(settings.UPLOAD_DIRECTORY).resolve()
        os.makedirs(self.upload_dir, exist_ok=True)
        # In-memory registry for Phase 2 (seamlessly transitions to PostgreSQL in Phase 3)
        self._registry: Dict[str, dict] = {}

    def _resolve_assembly(self, detected_assembly: Optional[str], requested_assembly: Optional[str]) -> str:
        """
        Determines the effective reference genome assembly, verifying user selection against header data.
        """
        assembly = requested_assembly or detected_assembly or settings.DEFAULT_GENOME_ASSEMBLY

        if assembly not in settings.SUPPORTED_ASSEMBLIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported genome assembly '{assembly}'. Supported assemblies: {', '.join(settings.SUPPORTED_ASSEMBLIES)}"
            )

        if detected_assembly and requested_assembly and detected_assembly != requested_assembly:
            logger.warning(
                f"Assembly mismatch: VCF header declares '{detected_assembly}', but user requested '{requested_assembly}'."
            )

        return assembly

    async def validate_only(
        self,
        file: UploadFile,
        requested_assembly: Optional[str] = None
    ) -> ValidationOnlyResponse:
        """
        Executes pre-flight validation on an uploaded VCF stream without persisting it to storage.
        """
        content = await file.read()
        stream = io.BytesIO(content)

        summary = self.validator.validate(stream, filename=file.filename or "input.vcf")
        assembly = self._resolve_assembly(summary.detected_assembly, requested_assembly)

        return ValidationOnlyResponse(
            filename=file.filename or "input.vcf",
            assembly=assembly,
            validation_summary=summary,
            can_proceed_to_analysis=summary.is_valid and summary.accepted_variants_count > 0
        )

    async def upload_dataset(
        self,
        file: UploadFile,
        requested_assembly: Optional[str] = None
    ) -> DatasetUploadResponse:
        """
        Validates, securely stores, and registers a genomic VCF dataset.
        """
        original_filename = file.filename or "unnamed.vcf"
        clean_name = sanitize_filename(original_filename)

        # 1. Quick extension check
        lower_name = clean_name.lower()
        if not (lower_name.endswith(".vcf") or lower_name.endswith(".vcf.gz")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension for '{original_filename}'. Only '.vcf' and '.vcf.gz' files are accepted."
            )

        # 2. Read bytes into memory/spool for validation and checksum
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)."
            )

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed upload limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
            )

        # 3. Perform bioinformatics validation
        stream = io.BytesIO(content)
        summary = self.validator.validate(stream, filename=clean_name)

        if not summary.is_valid and summary.accepted_variants_count == 0:
            reasons = "; ".join([r.rejection_reason for r in summary.rejections[:3]]) or "File structure is invalid."
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"VCF validation failed: {reasons}"
            )

        assembly = self._resolve_assembly(summary.detected_assembly, requested_assembly)

        # 4. Generate collision-free storage filename and write to disk
        dataset_id = str(uuid.uuid4())
        stored_filename = f"{dataset_id}_{clean_name}"
        stored_path = self.upload_dir / stored_filename

        try:
            with open(stored_path, "wb") as f:
                f.write(content)
            logger.info(f"Dataset securely stored: id={dataset_id}, path={stored_path}")
        except Exception as e:
            logger.error(f"Failed to write uploaded file to disk: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal storage error while saving the uploaded file."
            )

        uploaded_at = datetime.now(timezone.utc).isoformat()

        # 5. Register dataset metadata in memory and database if active
        record = {
            "dataset_id": dataset_id,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "stored_path": str(stored_path),
            "file_checksum": summary.file_checksum,
            "file_size_bytes": summary.file_size_bytes,
            "assembly": assembly,
            "validation_summary": summary,
            "uploaded_at": uploaded_at
        }
        self._registry[dataset_id] = record

        return DatasetUploadResponse(
            dataset_id=dataset_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_checksum=summary.file_checksum,
            file_size_bytes=summary.file_size_bytes,
            assembly=assembly,
            validation_summary=summary,
            uploaded_at=uploaded_at,
            message="Dataset uploaded and validated successfully."
        )

    def get_dataset(self, dataset_id: str) -> dict:
        """
        Retrieves a dataset record by ID.
        """
        if dataset_id not in self._registry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset with ID '{dataset_id}' not found."
            )
        return self._registry[dataset_id]

    def list_datasets(self) -> DatasetListResponse:
        """
        Returns all registered datasets.
        """
        items: List[DatasetListItem] = []
        for d in self._registry.values():
            summary = d["validation_summary"]
            items.append(
                DatasetListItem(
                    dataset_id=d["dataset_id"],
                    original_filename=d["original_filename"],
                    file_size_bytes=d["file_size_bytes"],
                    assembly=d["assembly"],
                    is_valid=summary.is_valid,
                    variant_count=summary.accepted_variants_count,
                    uploaded_at=d["uploaded_at"]
                )
            )
        return DatasetListResponse(total=len(items), items=items)

    def delete_dataset(self, dataset_id: str) -> dict:
        """
        Removes stored dataset file and unregisters metadata.
        """
        record = self.get_dataset(dataset_id)
        stored_path = Path(record["stored_path"])
        if stored_path.exists():
            stored_path.unlink()
        del self._registry[dataset_id]
        logger.info(f"Dataset deleted: {dataset_id}")
        return {"status": "success", "message": f"Dataset '{dataset_id}' deleted successfully."}


dataset_service = DatasetService()

