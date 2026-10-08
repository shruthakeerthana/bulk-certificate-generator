from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.config import MAX_RECIPIENTS
from app.models import CertStatus, JobStatus


class RecipientIn(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="Name printed on the certificate")
    email: EmailStr = Field(description="Recipient email address")
    course: str = Field(min_length=1, max_length=150, description="Course or event completed")
    completion_date: date = Field(
        default_factory=date.today, description="ISO date; defaults to today"
    )

    @field_validator("name", "course")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class GenerateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipients": [
                    {
                        "name": "Alice Johnson",
                        "email": "alice@example.com",
                        "course": "Cybersecurity 101",
                        "completion_date": "2026-10-01",
                    }
                ]
            }
        }
    )

    recipients: list[RecipientIn] = Field(
        min_length=1, max_length=MAX_RECIPIENTS, description=f"1 to {MAX_RECIPIENTS} recipients"
    )


class GenerateResponse(BaseModel):
    job_id: str
    status: JobStatus
    total_recipients: int


class FailureOut(BaseModel):
    certificate_id: str
    recipient_name: str
    recipient_email: str
    error: str | None


class JobOut(BaseModel):
    job_id: str
    status: JobStatus
    total_recipients: int
    successful_count: int
    failed_count: int
    processed_count: int = Field(description="successful_count + failed_count (progress)")
    created_at: str
    completed_at: str | None
    failures: list[FailureOut]


class CertificateOut(BaseModel):
    certificate_id: str
    recipient_name: str
    recipient_email: str
    course: str
    status: CertStatus
    error: str | None
    download_url: str | None
