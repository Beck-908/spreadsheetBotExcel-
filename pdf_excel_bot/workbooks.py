"""Opening the workbook's People tab, either by driving Excel or by editing the file.

Both classes implement people_sheet.SheetBackend plus save() / show() / close():

- ExcelWorkbook drives the real Excel app (when installed) over COM. Excel keeps
  everything in the workbook intact, and the user watches the rows arrive.
- FileWorkbook edits the .xlsx/.xlsm with openpyxl, for PCs without Excel.
"""

import os
import shutil
import winreg
from datetime import datetime
from pathlib import Path

import openpyxl

SHEET_NAME = "People"


class WorkbookError(Exception):
    """The workbook couldn't be opened or saved; the message is shown to the user."""


class WorkbookLockedError(WorkbookError):
    pass


def make_backup(path: Path, now: datetime | None = None) -> Path:
    """Copy the workbook to backups/<name>_backup_<timestamp><ext> next to it."""
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    backup = path.parent / "backups" / f"{path.stem}_backup_{stamp}{path.suffix}"
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(path, backup)
    return backup


def excel_available() -> bool:
    try:
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Excel.Application\CLSID"))
        return True
    except OSError:
        return False


def open_workbook(path: Path, prefer_excel: bool = True) -> "FileWorkbook | ExcelWorkbook":
    path = Path(path).resolve()
    if not path.exists():
        raise WorkbookError(f"Workbook not found: {path}")
    if prefer_excel and excel_available():
        return ExcelWorkbook(path)
    return FileWorkbook(path)


def _find_sheet(names: list[str]) -> int | None:
    lowered = [name.strip().lower() for name in names]
    return lowered.index(SHEET_NAME.lower()) if SHEET_NAME.lower() in lowered else None


class FileWorkbook:
    mode = "file"

    def __init__(self, path: Path):
        if path.suffix.lower() not in (".xlsx", ".xlsm"):
            raise WorkbookError(
                f"{path.name}: without Excel installed the bot can only edit .xlsx or .xlsm files. "
                "Open it in Excel and save it as .xlsx."
            )
        self.path = path
        self._check_not_locked()
        try:
            self._wb = openpyxl.load_workbook(path, keep_vba=path.suffix.lower() == ".xlsm")
        except Exception as exc:  # openpyxl raises assorted zipfile/XML errors for damaged files
            raise WorkbookError(f"Couldn't read {path.name} ({exc}).") from exc
        index = _find_sheet(self._wb.sheetnames)
        self._ws = self._wb.worksheets[index] if index is not None else self._wb.create_sheet(SHEET_NAME)

    def _check_not_locked(self) -> None:
        try:
            with open(self.path, "r+b"):
                pass
        except PermissionError as exc:
            raise WorkbookLockedError(
                f"{self.path.name} is open in another program. Please close it and run again."
            ) from exc

    def read_values(self) -> list[list[object]]:
        return [list(row) for row in self._ws.iter_rows(values_only=True)]

    def write_cell(self, row: int, col: int, value: object, number_format: str | None = None) -> None:
        cell = self._ws.cell(row=row, column=col, value=value)
        if number_format:
            cell.number_format = number_format

    def save(self) -> None:
        self._check_not_locked()
        # Open on the People tab. Clear the other tabs' selection too, or Excel opens them grouped.
        for ws in self._wb.worksheets:
            ws.sheet_view.tabSelected = ws is self._ws
        self._wb.active = self._ws
        try:
            self._wb.save(self.path)
        except PermissionError as exc:
            raise WorkbookLockedError(
                f"{self.path.name} is open in another program. Please close it and run again."
            ) from exc

    def show(self) -> None:
        """Open the saved workbook in whatever app handles .xlsx on this PC."""
        try:
            os.startfile(self.path)
        except OSError:
            pass  # no spreadsheet app installed; the file is saved regardless

    def close(self) -> None:
        self._wb.close()


class ExcelWorkbook:
    mode = "Excel"

    def __init__(self, path: Path):
        import pythoncom
        import win32com.client

        self.path = path
        pythoncom.CoInitialize()  # needed on every thread that talks to Excel
        try:
            # Reuse the Excel the user already has open, so an open workbook isn't opened twice.
            running = pythoncom.GetActiveObject("Excel.Application")
            self._app = win32com.client.dynamic.Dispatch(running.QueryInterface(pythoncom.IID_IDispatch))
        except pythoncom.com_error:
            self._app = win32com.client.dynamic.Dispatch("Excel.Application")
        self._app.Visible = True

        self._wb = self._already_open() or self._open()
        if self._wb.ReadOnly:
            raise WorkbookLockedError(
                f"Excel opened {path.name} read-only (someone else may have it open). Close it everywhere and run again."
            )
        sheets = self._wb.Worksheets
        names = [sheets.Item(i).Name for i in range(1, sheets.Count + 1)]
        index = _find_sheet(names)
        if index is None:
            self._ws = sheets.Add(After=sheets.Item(sheets.Count))
            self._ws.Name = SHEET_NAME
        else:
            self._ws = sheets.Item(index + 1)
        self._wb.Activate()
        self._ws.Activate()

    def _already_open(self):
        books = self._app.Workbooks
        for i in range(1, books.Count + 1):
            book = books.Item(i)
            if os.path.normcase(book.FullName) == os.path.normcase(str(self.path)):
                return book
        return None

    def _open(self):
        import pythoncom

        try:
            return self._app.Workbooks.Open(str(self.path))
        except pythoncom.com_error as exc:
            raise WorkbookError(f"Excel couldn't open {self.path.name} ({exc}).") from exc

    def read_values(self) -> list[list[object]]:
        used = self._ws.UsedRange
        last_row = used.Row + used.Rows.Count - 1
        last_col = used.Column + used.Columns.Count - 1
        data = self._ws.Range(self._ws.Cells(1, 1), self._ws.Cells(last_row, last_col)).Value
        if not isinstance(data, tuple):  # a single cell comes back as a bare value
            return [[data]]
        return [list(row) for row in data]

    def write_cell(self, row: int, col: int, value: object, number_format: str | None = None) -> None:
        cell = self._ws.Cells(row, col)
        if number_format:
            cell.NumberFormat = number_format  # before the value, so a column formatted as Text doesn't keep it text
        if isinstance(value, int) and not isinstance(value, bool):
            value = float(value)  # Excel can't take 64-bit integers over COM; its numbers are all doubles anyway
        cell.Value = value

    def save(self) -> None:
        self._wb.Save()

    def show(self) -> None:
        self._app.Visible = True
        self._wb.Activate()
        self._ws.Activate()

    def close(self) -> None:
        """Leave Excel open with the workbook showing; just let go of it."""
        import pythoncom

        self._ws = self._wb = self._app = None
        pythoncom.CoUninitialize()
