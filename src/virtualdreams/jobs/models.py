from dataclasses import dataclass, field
from enum import StrEnum
import time
import uuid


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    error: str | None = None
    audio_path: str | None = None
    fetched: bool = False
    created_at: float = field(default_factory=time.time)
