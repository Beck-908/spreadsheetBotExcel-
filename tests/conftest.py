"""Test fixtures: synthetic profile PDFs laid out like the real ones (fake people only)."""

from pathlib import Path

import pytest
from fpdf import FPDF

# Geometry copied from the real sample PDF (points, US Letter).
TABLE_LEFT, TABLE_MID, TABLE_RIGHT = 75, 296, 536
LABEL_X, VALUE_X = 81, 301
ROW_H, LINE_H = 24.5, 13.2

DEFAULT_CONTACTS = [
    ("Wireless:", "(512) 555-0134"),
    ("Landline:", "(512) 555-0199"),
    ("Email:", "jordan.avery@example.com"),
]
DEFAULT_PAGE1_ROWS = [
    ("Property ID", ["5550001234"]),
    ("Property Value", ["$12,345.67"]),
    ("Property Type", ["SC01: DIVIDENDS"]),
    ("Holder", ["EXAMPLE HOLDINGS INC"]),
    ("Location", ["SPRINGFIELD, IL"]),
    ("Address", ["C O PAT EXAMPLE, 100 MAIN STREET,", "SUITE 200, SPRINGFIELD, IL 62701"]),
    ("Pending Claims", ["0-0"]),
    ("Classification", ["Cash"]),
]
DEFAULT_PAGE2_ROWS = [
    ("Home Address", ["42 Test Lane, Austin, TX 78701"]),
    ("Born", ["Mar 1979"]),
    ("Age", ["47"]),
]


def _table(pdf: FPDF, top: float, rows: list[tuple[str, list[str]]]) -> None:
    """Draw an Attribute/Details table starting at `top`, one ruled row per entry."""
    all_rows = [("Attribute", ["Details"])] + rows
    y = top
    pdf.line(TABLE_LEFT, y, TABLE_RIGHT, y)
    for i, (label, value_lines) in enumerate(all_rows):
        height = ROW_H + LINE_H * (len(value_lines) - 1)
        baseline = y + 15
        pdf.set_font("Helvetica", "B", 10)
        pdf.text(LABEL_X, baseline, label)
        pdf.set_font("Helvetica", "B" if i == 0 else "", 10)
        for n, line in enumerate(value_lines):
            pdf.text(VALUE_X, baseline + n * LINE_H, line)
        y += height
        pdf.line(TABLE_LEFT, y, TABLE_RIGHT, y)
    for x in (TABLE_LEFT, TABLE_MID, TABLE_RIGHT):
        pdf.line(x, top, x, y)


def build_profile_pdf(
    path: Path,
    name: str = "Jordan Avery Testcase",
    contacts: list[tuple[str, str]] | None = None,
    page1_rows: list[tuple[str, list[str]]] | None = None,
    page2_rows: list[tuple[str, list[str]]] | None = None,
    header: list[str] | None = None,
) -> Path:
    """header: small lines printed above the name, like a browser's "Save as PDF" date/title header."""
    contacts = DEFAULT_CONTACTS if contacts is None else contacts
    page1_rows = DEFAULT_PAGE1_ROWS if page1_rows is None else page1_rows
    page2_rows = DEFAULT_PAGE2_ROWS if page2_rows is None else page2_rows

    pdf = FPDF(unit="pt", format="letter")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 8)
    for n, text in enumerate(header or []):
        pdf.text(30, 22 + n * 12, text)
    if header:
        pdf.text(30, 780, "1/2")  # page number at the bottom
    pdf.set_font("Helvetica", "B", 11)
    pdf.text((612 - pdf.get_string_width(name)) / 2, 82, name)
    pdf.rect(239, 107, 134, 200)  # stands in for the photo

    pdf.set_font("Helvetica", "B", 16)
    pdf.text(72, 345, "Contact Information")
    y = 370
    for label, value in contacts:
        pdf.set_font("Helvetica", "B", 11)
        pdf.text(72, y, label)
        pdf.set_font("Helvetica", "", 11)
        pdf.text(72 + pdf.get_string_width(label) + 6, y, value)
        y += 18

    pdf.set_font("Helvetica", "B", 16)
    pdf.text(72, y + 30, "Property & Financial Statistics")
    _table(pdf, y + 50, page1_rows)

    if page2_rows:
        pdf.add_page()
        _table(pdf, 72, page2_rows)
    pdf.output(str(path))
    return path


@pytest.fixture(autouse=True)
def no_excel(monkeypatch):
    # The dev PC has no Excel; make that explicit so tests take the file path everywhere.
    monkeypatch.setattr("pdf_excel_bot.workbooks.excel_available", lambda: False)


@pytest.fixture
def profile_pdf(tmp_path: Path) -> Path:
    return build_profile_pdf(tmp_path / "jordan.pdf")


@pytest.fixture
def blank_pdf(tmp_path: Path) -> Path:
    pdf = FPDF(unit="pt", format="letter")
    pdf.add_page()
    pdf.rect(100, 100, 300, 300)  # a page with graphics but no text, like a scan
    path = tmp_path / "scanned.pdf"
    pdf.output(str(path))
    return path
