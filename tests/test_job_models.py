import time
from virtualdreams.jobs.models import Job, JobStatus


def test_job_defaults():
    job = Job()
    assert job.job_id
    assert job.status == JobStatus.PENDING
    assert job.error is None
    assert job.audio_path is None
    assert job.fetched is False
    assert job.created_at <= time.time()


def test_job_id_unique():
    a = Job()
    b = Job()
    assert a.job_id != b.job_id


def test_job_status_values():
    assert JobStatus.PENDING == "pending"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"
