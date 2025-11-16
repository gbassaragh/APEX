"""
Background job status endpoints.

Provides job tracking for long-running async operations.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apex.database.repositories.job_repository import JobRepository
from apex.dependencies import get_current_user, get_db, get_job_repo
from apex.models.database import User
from apex.models.schemas import JobStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_job_repo),
):
    """
    Get background job status.

    Returns current status, progress, and results (if completed).
    Users can only access their own jobs.
    """
    job = job_repo.get(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this job",
        )

    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
        result_data=job.result_data,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
