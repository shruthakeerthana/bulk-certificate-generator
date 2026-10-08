from datetime import date

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.models import Certificate, new_id
from app.services.certificate_generator import generate_certificate


def _cert(name="Alice", course="Cybersecurity 101"):
    return Certificate(
        id=new_id(),
        job_id="j",
        position=0,
        recipient_name=name,
        recipient_email="a@example.com",
        course=course,
        completion_date=date(2026, 10, 1),
    )


def test_generates_valid_pdf_named_by_certificate_id(tmp_path):
    cert = _cert()
    path = generate_certificate(cert, tmp_path)
    assert path == tmp_path / f"{cert.id}.pdf"
    assert path.read_bytes().startswith(b"%PDF")


def test_failed_generation_leaves_no_partial_file(tmp_path, monkeypatch):
    def boom(self):
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(canvas.Canvas, "save", boom)
    try:
        generate_certificate(_cert(), tmp_path)
    except RuntimeError:
        pass
    assert list(tmp_path.iterdir()) == []


def test_very_long_name_and_course_do_not_crash(tmp_path):
    path = generate_certificate(_cert("W" * 100, "C" * 150), tmp_path)
    assert path.exists()


def test_generated_pdf_contains_recipient_and_course(tmp_path):
    cert = _cert(name="Alice Smith", course="Cybersecurity 101")
    path = generate_certificate(cert, tmp_path)
    reader = PdfReader(path)
    text = reader.pages[0].extract_text()
    assert "Alice Smith" in text
    assert "Cybersecurity 101" in text
