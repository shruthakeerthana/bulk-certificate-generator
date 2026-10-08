from app.database import SessionLocal
from app.models import CertStatus, GenerationJob, JobStatus
from app.services import job_processor
from tests.conftest import make_recipient


def _create(client, n=2):
    recipients = [make_recipient(f"User{i}", f"u{i}@example.com") for i in range(n)]
    return client.post("/api/certificates/generate", json={"recipients": recipients}).json()[
        "job_id"
    ]


def test_processing_unknown_job_is_a_noop(client):
    job_processor.process_job("does-not-exist")  # must not raise


def test_job_crash_marks_job_failed_and_sets_completed_at(client, monkeypatch):
    """If the processor itself breaks (not just one certificate), the job must not hang."""
    real_utcnow = job_processor.utcnow
    calls = {"n": 0}

    def flaky_utcnow():
        calls["n"] += 1
        if calls["n"] == 1:  # first call is in the normal finalisation path
            raise RuntimeError("clock exploded")
        return real_utcnow()

    monkeypatch.setattr(job_processor, "utcnow", flaky_utcnow)
    job_id = _create(client)

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert job["completed_at"] is not None
    # already-committed per-certificate results are preserved, counts stay consistent
    assert job["successful_count"] + job["failed_count"] == job["processed_count"] == 2


def test_status_transitions_end_in_terminal_state(client):
    job_id = _create(client)
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        assert job.status is JobStatus.COMPLETED
        assert all(c.status is CertStatus.SUCCESS for c in job.certificates)
    finally:
        db.close()
