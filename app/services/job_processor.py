"""Runs a job: generates every certificate, isolating failures per recipient."""

import logging
from pathlib import Path

from app.config import CERT_DIR
from app.database import SessionLocal
from app.models import Certificate, CertStatus, GenerationJob, JobStatus, utcnow
from app.services import certificate_generator

logger = logging.getLogger(__name__)


def process_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        job.status = JobStatus.PROCESSING
        db.commit()

        certs = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id)
            .order_by(Certificate.position)
            .all()
        )
        for cert in certs:
            path: Path | None = None
            try:
                # Looked up via the module so tests can patch it.
                path = certificate_generator.generate_certificate(cert, CERT_DIR)
                cert.status = CertStatus.SUCCESS
                cert.file_path = str(path)
                job.successful_count += 1
            except Exception as exc:  # one bad recipient must not stop the rest
                logger.exception("Certificate %s failed", cert.id)
                cert.status = CertStatus.FAILED
                cert.error_message = f"{type(exc).__name__}: {exc}"
                job.failed_count += 1
            try:
                db.commit()  # commit per certificate -> live progress
            except Exception:
                if path is not None:
                    path.unlink(missing_ok=True)  # don't leave an orphan PDF
                raise

        if job.failed_count == 0:
            job.status = JobStatus.COMPLETED
        elif job.successful_count == 0:
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.PARTIAL_SUCCESS
        job.completed_at = utcnow()
        db.commit()
    except Exception:
        logger.exception("Job %s crashed", job_id)
        db.rollback()
        job = db.get(GenerationJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.completed_at = utcnow()
            db.commit()
    finally:
        db.close()
