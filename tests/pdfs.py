import io
import os
import textwrap
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

TAMIL_FONT = Path(os.environ.get("TAMIL_FONT_PATH", Path(__file__).parent / "fixtures" / "NotoSansTamil-Regular.ttf"))


def _write(text, font=None):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    if font:
        pdf.setFont(font, 12)
    y = 800
    for line in textwrap.wrap(text, 80):
        if y < 50:
            pdf.showPage()
            if font:
                pdf.setFont(font, 12)
            y = 800
        pdf.drawString(40, y, line)
        y -= 14
    pdf.save()
    return buffer.getvalue()


def english_pdf(text):
    return _write(text)


def tamil_pdf(text):
    if not TAMIL_FONT.exists():
        pytest.skip("Put NotoSansTamil-Regular.ttf in tests/fixtures/ (or set TAMIL_FONT_PATH) to run Tamil PDF tests")
    pdfmetrics.registerFont(TTFont("Tamil", str(TAMIL_FONT)))
    return _write(text, font="Tamil")


def scanned_pdf():
    """A page with a drawn rectangle and no text layer, like a scan."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.rect(50, 50, 400, 600, fill=1)
    pdf.save()
    return buffer.getvalue()