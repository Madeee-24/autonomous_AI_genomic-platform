"""
REST API Router for genomic dataset upload, validation, and metadata management.
"""
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.dataset import (
    DatasetListResponse,
    DatasetUploadResponse,
    ErrorResponse,
    ValidationOnlyResponse,
)
from app.services.dataset_service import dataset_service

router = APIRouter()


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and validate a VCF file",
    description="Accepts a multipart genomic .vcf or .vcf.gz file, performs integrity and specification validation, and stores the file safely.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid VCF file or unsupported assembly"},
        413: {"model": ErrorResponse, "description": "File exceeds size limit"},
    }
)
async def upload_dataset(
    file: UploadFile = File(..., description="VCF or gzipped VCF file"),
    assembly: Optional[str] = Form(None, description="Target reference genome assembly (GRCh38 or GRCh37)")
):
    return await dataset_service.upload_dataset(file, requested_assembly=assembly)


@router.post(
    "/validate-only",
    response_model=ValidationOnlyResponse,
    summary="Validate VCF file without saving",
    description="Inspects VCF structure, header declarations, and records in-memory without persistent disk storage.",
    responses={
        400: {"model": ErrorResponse, "description": "Validation failed"},
    }
)
async def validate_dataset_preflight(
    file: UploadFile = File(..., description="VCF file to validate"),
    assembly: Optional[str] = Form(None, description="Optional expected genome assembly")
):
    return await dataset_service.validate_only(file, requested_assembly=assembly)


@router.get(
    "",
    response_model=DatasetListResponse,
    summary="List all uploaded datasets",
    description="Returns metadata, validation summaries, and variant counts for all registered datasets."
)
async def list_datasets():
    return dataset_service.list_datasets()


@router.get(
    "/{dataset_id}",
    summary="Get dataset details",
    description="Retrieves metadata, file checksum, and validation summary for a specific dataset."
)
async def get_dataset(dataset_id: str):
    return dataset_service.get_dataset(dataset_id)


@router.delete(
    "/{dataset_id}",
    summary="Delete a dataset",
    description="Removes the stored file and unregisters dataset metadata."
)
async def delete_dataset(dataset_id: str):
    return dataset_service.delete_dataset(dataset_id)
