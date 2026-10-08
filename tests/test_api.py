import pytest

from app.services import certificate_generator
from tests.conftest import make_recipient


def _create(client, recipients):
    return client.post("/api/certificates/generate", json={"recipients": recipients})


def test_create_generation_job(client):
    res = _create(client, [make_recipient(), make_recipient("Bob", "bob@example.com")])
    assert res.status_code == 202
    body = res.json()
    assert body["total_recipients"] == 2
    assert body["job_id"]


@pytest.mark.parametrize(
    "recipient",
    [
        {"email": "a@example.com", "course": "X"},  # missing name
        make_recipient(name=""),  # empty name
        make_recipient(name="   "),  # blank name
        make_recipient(email="not-an-email"),
        make_recipient(course=""),
    ],
)
def test_invalid_recipient_rejected(client, recipient):
    assert _create(client, [recipient]).status_code == 422


def test_empty_recipient_list_rejected(client):
    assert _create(client, []).status_code == 422


def test_missing_body_rejected(client):
    assert client.post("/api/certificates/generate", json={}).status_code == 422


def test_invalid_recipient_creates_no_job(client):
    # One bad recipient rejects the whole request (documented design decision).
    res = _create(client, [make_recipient(), make_recipient(email="bad")])
    assert res.status_code == 422


def test_certificate_generation_produces_pdf(client):
    job_id = _create(client, [make_recipient()]).json()["job_id"]
    certs = client.get(f"/api/jobs/{job_id}/certificates").json()
    assert certs[0]["status"] == "SUCCESS"
    pdf = client.get(certs[0]["download_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_job_status_completed(client):
    job_id = _create(client, [make_recipient(), make_recipient("Bob", "bob@example.com")]).json()[
        "job_id"
    ]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert job["successful_count"] == 2
    assert job["failed_count"] == 0
    assert job["processed_count"] == 2
    assert job["failures"] == []
    assert job["completed_at"] is not None


def test_partial_failure_does_not_stop_batch(client, monkeypatch):
    real = certificate_generator.generate_certificate

    def flaky(cert, out_dir):
        if cert.recipient_name == "Chris":
            raise RuntimeError("boom")
        return real(cert, out_dir)

    monkeypatch.setattr(certificate_generator, "generate_certificate", flaky)
    names = ["Alice", "Bob", "Chris", "David", "Emma"]
    recipients = [make_recipient(n, f"{n.lower()}@example.com") for n in names]
    job_id = _create(client, recipients).json()["job_id"]

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "PARTIAL_SUCCESS"
    assert job["successful_count"] == 4
    assert job["failed_count"] == 1
    assert job["failures"][0]["recipient_email"] == "chris@example.com"
    assert "boom" in job["failures"][0]["error"]

    certs = client.get(f"/api/jobs/{job_id}/certificates").json()
    assert [c["status"] for c in certs] == [
        "SUCCESS",
        "SUCCESS",
        "FAILED",
        "SUCCESS",
        "SUCCESS",
    ]
    assert certs[2]["download_url"] is None
    # failed certificate cannot be downloaded
    failed_id = certs[2]["certificate_id"]
    assert client.get(f"/api/certificates/{failed_id}").status_code == 409


def test_all_failures_marks_job_failed(client, monkeypatch):
    def always_fail(cert, out_dir):
        raise RuntimeError("nope")

    monkeypatch.setattr(certificate_generator, "generate_certificate", always_fail)
    job_id = _create(client, [make_recipient()]).json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "FAILED"


def test_special_characters_and_long_name(client):
    recipients = [
        make_recipient("José O'Brien-Smith", "jose@example.com"),
        make_recipient("A" * 100, "long@example.com"),
    ]
    job_id = _create(client, recipients).json()["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "COMPLETED"


def test_duplicate_recipients_get_separate_certificates(client):
    job_id = _create(client, [make_recipient(), make_recipient()]).json()["job_id"]
    certs = client.get(f"/api/jobs/{job_id}/certificates").json()
    assert len({c["certificate_id"] for c in certs}) == 2


def test_unknown_job(client):
    assert client.get("/api/jobs/does-not-exist").status_code == 404
    assert client.get("/api/jobs/does-not-exist/certificates").status_code == 404


def test_unknown_certificate(client):
    assert client.get("/api/certificates/does-not-exist").status_code == 404


def test_name_and_course_whitespace_is_trimmed(client):
    job_id = _create(client, [make_recipient("  Alice  ", course="  Cyber  ")]).json()["job_id"]
    cert = client.get(f"/api/jobs/{job_id}/certificates").json()[0]
    assert cert["recipient_name"] == "Alice"
    assert cert["course"] == "Cyber"


def test_invalid_date_rejected(client):
    r = {**make_recipient(), "completion_date": "not-a-date"}
    assert _create(client, [r]).status_code == 422


def test_name_too_long_rejected(client):
    assert _create(client, [make_recipient(name="A" * 101)]).status_code == 422


def test_too_many_recipients_rejected(client):
    from app.config import MAX_RECIPIENTS

    recipients = [make_recipient(email=f"u{i}@example.com") for i in range(MAX_RECIPIENTS + 1)]
    assert _create(client, recipients).status_code == 422


def test_download_when_file_missing_on_disk(client):
    import os

    job_id = _create(client, [make_recipient()]).json()["job_id"]
    cert = client.get(f"/api/jobs/{job_id}/certificates").json()[0]
    from app.database import SessionLocal
    from app.models import Certificate

    db = SessionLocal()
    try:
        os.remove(db.get(Certificate, cert["certificate_id"]).file_path)
    finally:
        db.close()
    assert client.get(cert["download_url"]).status_code == 404


def test_each_certificate_has_unique_pdf(client):
    recipients = [make_recipient(f"U{i}", f"u{i}@example.com") for i in range(5)]
    job_id = _create(client, recipients).json()["job_id"]
    certs = client.get(f"/api/jobs/{job_id}/certificates").json()
    bodies = {client.get(c["download_url"]).content for c in certs}
    assert len(certs) == 5 and len(bodies) == 5
