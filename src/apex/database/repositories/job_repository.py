"""
Repository for background job operations.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.database.repositories.base import BaseRepository
from apex.models.database import BackgroundJob


class JobRepository(BaseRepository[BackgroundJob]):
    """CRUD helpers for BackgroundJob records."""

    def __init__(self) -> None:
        super().__init__(BackgroundJob)

    def create_job(
        self,
        db: Session,
        *,
        job_type: str,
        user_id: UUID,
        document_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
    ) -> BackgroundJob:
        """Create a new background job in pending state."""
        job = BackgroundJob(
            job_type=job_type,
            status="pending",
            created_by_id=user_id,
            document_id=document_id,
            project_id=project_id,
        )
        db.add(job)
        db.flush()
        return job

    def update_progress(
        self,
        db: Session,
        job_id: UUID,
        *,
        progress_percent: int,
        current_step: str,
    ) -> Optional[BackgroundJob]:
        """Update progress and optionally flip status to running."""
        job = self.get(db, job_id)
        if not job:
            return None

        job.progress_percent = progress_percent
        job.current_step = current_step
        if job.status == "pending":
            job.status = "running"
            job.started_at = datetime.utcnow()

        db.flush()
        return job

    def mark_completed(
        self,
        db: Session,
        job_id: UUID,
        *,
        result_data: dict,
        estimate_id: Optional[UUID] = None,
    ) -> Optional[BackgroundJob]:
        """Mark job completed and store result payload."""
        job = self.get(db, job_id)
        if not job:
            return None

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.result_data = result_data
        if estimate_id:
            job.estimate_id = estimate_id

        db.flush()
        return job

    def mark_failed(self, db: Session, job_id: UUID, error_message: str) -> Optional[BackgroundJob]:
        """Mark job failed with error context."""
        job = self.get(db, job_id)
        if not job:
            return None

        job.status = "failed"
        job.error_message = error_message
        job.completed_at = datetime.utcnow()

        db.flush()
        return job

    def cleanup_old_jobs(self, db: Session, *, older_than_days: int = 30) -> int:
        """Delete completed/failed jobs older than the cutoff; returns count."""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        query = select(BackgroundJob).where(
            BackgroundJob.status.in_(["completed", "failed"]),
            BackgroundJob.created_at < cutoff,
        )
        jobs = db.execute(query).scalars().all()
        deleted = 0
        for job in jobs:
            db.delete(job)
            deleted += 1
        return deleted
