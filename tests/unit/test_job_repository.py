from uuid import uuid4

from apex.database.repositories.job_repository import JobRepository


def test_update_progress_sets_fields_and_starts_job(db_session, test_user):
    repo = JobRepository()
    job = repo.create_job(
        db=db_session,
        job_type="estimate_generation",
        user_id=test_user.id,
        project_id=uuid4(),
    )

    updated = repo.update_progress(
        db=db_session,
        job_id=job.id,
        progress_percent=25,
        current_step="Loading inputs",
    )

    db_session.flush()

    assert updated is not None
    assert updated.progress_percent == 25
    assert updated.current_step == "Loading inputs"
    assert updated.status == "running"
    assert updated.started_at is not None
