"""Creates ONE PDF from ONE recipient, using ONE fixed template."""

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.models import Certificate

NAVY = colors.HexColor("#1f3a5f")
GOLD = colors.HexColor("#b08d57")


def _fit_font_size(text: str, font: str, start: int, max_width: float) -> int:
    """Shrink the font until the text fits, so long names don't overflow."""
    size = start
    while size > 10 and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _draw(c: canvas.Canvas, cert: Certificate, width: float, height: float) -> None:
    cx = width / 2
    c.setTitle(f"Certificate - {cert.recipient_name}")

    c.setStrokeColor(NAVY)
    c.setLineWidth(6)
    c.rect(25, 25, width - 50, height - 50)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.rect(38, 38, width - 76, height - 76)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(cx, height - 120, "CERTIFICATE OF COMPLETION")
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(cx - 120, height - 138, cx + 120, height - 138)

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, height - 180, "This certificate is proudly presented to")

    name_size = _fit_font_size(cert.recipient_name, "Helvetica-Bold", 34, width - 140)
    c.setFont("Helvetica-Bold", name_size)
    c.setFillColor(NAVY)
    c.drawCentredString(cx, height - 235, cert.recipient_name)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.line(cx - 230, height - 247, cx + 230, height - 247)

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(cx, height - 290, "for successfully completing")
    course_size = _fit_font_size(cert.course, "Helvetica-Bold", 24, width - 140)
    c.setFont("Helvetica-Bold", course_size)
    c.drawCentredString(cx, height - 328, cert.course)

    c.setFont("Helvetica", 13)
    c.drawCentredString(
        cx, height - 370, f"Completed on {cert.completion_date.strftime('%d %B %Y')}"
    )

    # Signature area
    c.setLineWidth(0.8)
    c.line(width - 260, 110, width - 90, 110)
    c.setFont("Helvetica", 10)
    c.drawCentredString(width - 175, 95, "Authorized Signature")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.grey)
    c.drawString(90, 60, f"Certificate ID: {cert.id}")


def generate_certificate(cert: Certificate, out_dir: Path) -> Path:
    """Render the certificate PDF and return its path. Raises on any failure.

    The PDF is written to a temporary file and renamed only when complete, so a
    crash can never leave a half-written certificate under its final name.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / f"{cert.id}.pdf"
    tmp_path = out_dir / f"{cert.id}.pdf.tmp"
    width, height = landscape(A4)
    try:
        c = canvas.Canvas(str(tmp_path), pagesize=(width, height))
        _draw(c, cert, width, height)
        c.showPage()
        c.save()
        os.replace(tmp_path, final_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return final_path
