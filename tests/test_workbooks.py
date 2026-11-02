from datetime import datetime

import openpyxl
import pytest
import win32con
import win32file

from pdf_excel_bot.people_sheet import append_people
from pdf_excel_bot.person import COLUMNS, Person
from pdf_excel_bot.workbooks import FileWorkbook, WorkbookError, WorkbookLockedError, make_backup, open_workbook


def make_xlsx(path, sheets=("People",), rows=()):
    wb = openpyxl.Workbook()
    wb.active.title = sheets[0]
    for name in sheets[1:]:
        wb.create_sheet(name)
    for row in rows:
        wb[sheets[0]].append(row)
    wb.save(path)
    return path


def test_backup_goes_in_backups_folder(tmp_path):
    book = make_xlsx(tmp_path / "book.xlsx")
    backup = make_backup(book, now=datetime(2026, 11, 1, 9, 30, 0))
    assert backup == tmp_path / "backups" / "book_backup_2026-11-01_093000.xlsx"
    assert backup.read_bytes() == book.read_bytes()


def test_file_workbook_round_trip(tmp_path):
    book = make_xlsx(tmp_path / "book.xlsx", sheets=("Summary", "People"))
    wb = open_workbook(book, prefer_excel=True)  # falls back to file mode without Excel
    assert isinstance(wb, FileWorkbook)
    append_people(wb, [Person(name="Jordan Avery", property_id="5550001234", value=12345.67, age=47)])
    wb.save()
    wb.close()

    saved = openpyxl.load_workbook(book)
    assert saved.sheetnames == ["Summary", "People"]
    assert saved.active.title == "People"
    assert not saved["Summary"].sheet_view.tabSelected  # otherwise Excel opens the tabs grouped
    ws = saved["People"]
    assert [c.value for c in ws[1]] == list(COLUMNS)
    assert ws["A2"].value == "Jordan Avery"
    assert ws["B2"].value == "5550001234" and ws["B2"].number_format == "@"
    assert ws["C2"].value == 12345.67 and ws["C2"].number_format == '"$"#,##0.00'
    assert ws["K2"].value == 47


def test_people_tab_found_case_insensitively(tmp_path):
    book = make_xlsx(tmp_path / "book.xlsx", sheets=("people",), rows=[COLUMNS])
    wb = open_workbook(book)
    assert wb.read_values()[0] == list(COLUMNS)
    wb.close()


def test_missing_people_tab_is_created(tmp_path):
    book = make_xlsx(tmp_path / "book.xlsx", sheets=("Sheet1",))
    wb = open_workbook(book)
    append_people(wb, [Person(name="A", property_id="1")])
    wb.save()
    wb.close()
    assert openpyxl.load_workbook(book).sheetnames == ["Sheet1", "People"]


def test_workbook_open_in_another_program_is_reported(tmp_path):
    book = make_xlsx(tmp_path / "book.xlsx")
    # Excel holds open workbooks with write-sharing denied; do the same.
    handle = win32file.CreateFile(str(book), win32con.GENERIC_READ, win32con.FILE_SHARE_READ, None,
                                  win32con.OPEN_EXISTING, 0, None)
    try:
        with pytest.raises(WorkbookLockedError, match="close it"):
            open_workbook(book)
    finally:
        handle.Close()


def test_missing_workbook(tmp_path):
    with pytest.raises(WorkbookError, match="not found"):
        open_workbook(tmp_path / "nope.xlsx")


def test_old_xls_needs_excel(tmp_path):
    book = tmp_path / "old.xls"
    book.write_bytes(b"not really xls")
    with pytest.raises(WorkbookError, match=".xlsx"):
        open_workbook(book)
