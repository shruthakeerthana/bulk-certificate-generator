from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models import Certificate, CertStatus, GenerationJob
from app.services.job_processor import process_job

router = APIRouter(prefix="/api")


def _get_job_or_404(db: Session, job_id: str) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post(
    "/certificates/generate",
    response_model=schemas.GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_generation_job(
    payload: schemas.GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Validate, store the job + one row per recipient, then process in background."""
    job = GenerationJob(total_recipients=len(payload.recipients))
    db.add(job)
    db.flush()  # assigns job.id
    for i, r in enumerate(payload.recipients):
        db.add(
            Certificate(
                job_id=job.id,
                position=i,
                recipient_name=r.name,
                recipient_email=str(r.email),
                course=r.course,
                completion_date=r.completion_date,
            )
        )
    db.commit()
    background_tasks.add_task(process_job, job.id)
    return schemas.GenerateResponse(
        job_id=job.id, status=job.status, total_recipients=job.total_recipients
    )


@router.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    failures = [
        schemas.FailureOut(
            certificate_id=c.id,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            error=c.error_message,
        )
        for c in job.certificates
        if c.status == CertStatus.FAILED
    ]
    return schemas.JobOut(
        job_id=job.id,
        status=job.status,
        total_recipients=job.total_recipients,
        successful_count=job.successful_count,
        failed_count=job.failed_count,
        processed_count=job.successful_count + job.failed_count,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        failures=failures,
    )


@router.get("/jobs/{job_id}/certificates", response_model=list[schemas.CertificateOut])
def list_job_certificates(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(db, job_id)
    return [
        schemas.CertificateOut(
            certificate_id=c.id,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            course=c.course,
            status=c.status,
            error=c.error_message,
            download_url=(f"/api/certificates/{c.id}" if c.status == CertStatus.SUCCESS else None),
        )
        for c in job.certificates
    ]


@router.get("/certificates/{certificate_id}")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    cert = db.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.status != CertStatus.SUCCESS or not cert.file_path:
        raise HTTPException(
            status_code=409,
            detail=f"Certificate is not available (status: {cert.status})",
        )
    path = Path(cert.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Certificate file missing on disk")
    return FileResponse(path, media_type="application/pdf", filename=f"certificate_{cert.id}.pdf")
