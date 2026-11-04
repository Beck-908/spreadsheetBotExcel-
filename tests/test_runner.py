import openpyxl
import pytest
import win32con
import win32file

from conftest import build_profile_pdf
from pdf_excel_bot.person import COLUMNS
from pdf_excel_bot.runner import run
from pdf_excel_bot.workbooks import WorkbookLockedError


@pytest.fixture
def book(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "People"
    wb.active.append(COLUMNS)
    path = tmp_path / "company.xlsx"
    wb.save(path)
    return path


def test_batch_adds_skips_and_reports(tmp_path, book, profile_pdf, blank_pdf):
    same_person_again = build_profile_pdf(tmp_path / "jordan_copy.pdf")
    log = []

    summary = run([profile_pdf, blank_pdf, same_person_again], book, log.append, show_result=False)

    assert [p.name for p in summary.added] == ["Jordan Avery Testcase"]
    assert [p.source for p in summary.duplicates] == ["jordan_copy.pdf"]
    assert [name for name, _ in summary.failed] == ["scanned.pdf"]
    assert summary.mode == "file"
    assert summary.backup.exists() and summary.backup.parent == tmp_path / "backups"

    ws = openpyxl.load_workbook(book)["People"]
    assert ws.max_row == 2
    assert ws["A2"].value == "Jordan Avery Testcase"

    text = "\n".join(log)
    for name in ("jordan.pdf", "scanned.pdf", "jordan_copy.pdf"):
        assert name in text
    assert "1 added, 1 skipped as duplicates, 1 failed" in text
    assert log[0].startswith("PDF to Excel Bot ")  # which build ran
    assert "✓ Read Jordan Avery Testcase, Property ID 5550001234, Value $12,345.67, from jordan.pdf" in text


def test_progress_callbacks_and_rows(tmp_path, book, profile_pdf, blank_pdf):
    other = build_profile_pdf(tmp_path / "other.pdf", page1_rows=[("Property ID", ["777"]), ("Holder", ["X INC"])])
    events = []

    summary = run(
        [profile_pdf, blank_pdf, other], book, lambda _: None, show_result=False,
        on_reading=lambda pdf: events.append(("reading", pdf.name)),
        on_read=lambda pdf, person, error: events.append(("read", pdf.name, person and person.property_id, bool(error))),
    )

    assert events == [
        ("reading", "jordan.pdf"), ("read", "jordan.pdf", "5550001234", False),
        ("reading", "scanned.pdf"), ("read", "scanned.pdf", None, True),
        ("reading", "other.pdf"), ("read", "other.pdf", "777", False),
    ]
    assert summary.first_row == 2  # header in row 1; the two added people are rows 2 and 3
    assert [p.property_id for p in summary.added] == ["5550001234", "777"]
    assert summary.warnings == []


def test_nothing_readable_leaves_workbook_alone(tmp_path, book, blank_pdf):
    before = book.read_bytes()
    log = []

    summary = run([blank_pdf], book, log.append, show_result=False)

    assert summary.added == [] and summary.backup is None
    assert book.read_bytes() == before
    assert not (tmp_path / "backups").exists()
    assert "not touched" in log[-1]


def test_locked_workbook_raises_before_backup(tmp_path, book, profile_pdf):
    handle = win32file.CreateFile(str(book), win32con.GENERIC_READ, win32con.FILE_SHARE_READ, None,
                                  win32con.OPEN_EXISTING, 0, None)
    try:
        with pytest.raises(WorkbookLockedError):
            run([profile_pdf], book, lambda _: None, show_result=False)
    finally:
        handle.Close()
    assert not (tmp_path / "backups").exists()
