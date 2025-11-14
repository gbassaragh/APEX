"""
Health check endpoints for monitoring and readiness probes.
"""
from fastapi import APIRouter, Depends, status as http_status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from apex.dependencies import get_db
from apex.azure.blob_storage import BlobStorageClient
from apex.config import config

router = APIRouter()


@router.get("/health/live")
async def liveness_check():
    """
    Liveness probe for Kubernetes/Container Apps.

    Returns 200 if application is running.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow(),
        "application": config.APP_NAME,
        "version": config.APP_VERSION,
    }


@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe for Kubernetes/Container Apps.

    Checks:
    - Database connectivity
    - Blob storage accessibility

    Returns:
        200 if all checks pass
        503 if any check fails
    """
    checks = {"database": "unknown", "blob_storage": "unknown"}
    issues = []
    all_healthy = True

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = "unhealthy"
        issues.append(f"Database: {str(exc)}")
        all_healthy = False

    # Blob storage check
    try:
        blob_client = BlobStorageClient()
        uploads_ok = blob_client.check_container(config.AZURE_STORAGE_CONTAINER_UPLOADS)
        processed_ok = blob_client.check_container(config.AZURE_STORAGE_CONTAINER_PROCESSED)

        if uploads_ok and processed_ok:
            checks["blob_storage"] = "healthy"
        else:
            checks["blob_storage"] = "unhealthy"
            issues.append("Blob Storage: One or more containers not accessible")
            all_healthy = False
    except Exception as exc:
        checks["blob_storage"] = "unhealthy"
        issues.append(f"Blob Storage: {str(exc)}")
        all_healthy = False

    status_code = http_status.HTTP_200_OK if all_healthy else http_status.HTTP_503_SERVICE_UNAVAILABLE

    response = {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "issues": issues if issues else None,
        "timestamp": datetime.utcnow(),
        "application": config.APP_NAME,
        "version": config.APP_VERSION,
    }

    return response, status_code
