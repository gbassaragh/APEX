"""
Health check endpoints for monitoring and readiness probes.
"""
from fastapi import APIRouter, Depends, status as http_status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from apex.dependencies import get_db
from apex.azure.blob_storage import BlobStorageClient
from apex.config import config
from apex.utils.retry import azure_retry

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


@router.get("/health/ready", status_code=http_status.HTTP_200_OK)
@azure_retry
async def readiness_check(response: Response, db: Session = Depends(get_db)):
    """
    Readiness probe for Kubernetes/Container Apps.

    Checks:
    - Database connectivity
    - Blob storage authentication (client initialization only for MVP)

    Returns:
        200 if all checks pass
        503 if any check fails

    Note:
        Kubernetes readiness probes expect:
        - HTTP 200-399: Ready to accept traffic
        - HTTP 400+: Not ready (container removed from load balancer)
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

    # Blob storage check (MVP: verify client initialization only)
    # Full container checks would require async operations and increase probe latency
    try:
        blob_client = BlobStorageClient()
        # Verify client can be initialized with correct account URL
        if blob_client.account_url:
            checks["blob_storage"] = "healthy"
        else:
            checks["blob_storage"] = "unhealthy"
            issues.append("Blob Storage: Invalid account URL configuration")
            all_healthy = False
    except Exception as exc:
        checks["blob_storage"] = "unhealthy"
        issues.append(f"Blob Storage: {str(exc)}")
        all_healthy = False

    # Set response status code based on health status
    if not all_healthy:
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
        "issues": issues if issues else None,
        "timestamp": datetime.utcnow(),
        "application": config.APP_NAME,
        "version": config.APP_VERSION,
    }
