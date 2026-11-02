# PDF-to-Excel Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A double-click Windows app that reads property-profile PDFs and appends one row per person to the People tab of an Excel workbook.

**Architecture:** `pdf_reader` turns a PDF into a `Person`. `people_sheet` holds all header/dedupe/append rules and talks to a tiny `SheetBackend` interface. `workbooks` implements that interface twice (Excel via COM, openpyxl file editing) and does backups. `runner` glues a batch together; `gui` is a Tkinter front end over `runner`.

**Tech Stack:** Python 3.14, pdfplumber, openpyxl, pywin32, Tkinter; pytest + fpdf2 for tests; PyInstaller for the .exe.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-11-01-pdf-to-excel-bot-design.md` (column order, field mapping, dedupe, backups).
- Columns, exact text and order: Name, Property ID, Address Value, Holder, Property Type, Classification, Owner Location, Phone Number, Email Address, Age.
- Address Value ← "Property Value"; Owner Location ← "Home Address".
- Never modify a workbook without first writing a backup to `backups/` next to it.
- The user's real sample PDF is never copied into the project.
- Not a git repo and the user hasn't asked for commits: no commit steps.

## File Structure

```
spreadsheetBotExcel/
  app.py                         entry point -> gui.main()
  pdf_excel_bot/
    __init__.py
    person.py                    COLUMNS, Person dataclass, as_row(), missing_fields()
    pdf_reader.py                read_person(path) -> Person, PdfReadError
    people_sheet.py              SheetBackend protocol, append_people(), AppendResult, SheetLayoutError
    workbooks.py                 make_backup(), excel_available(), open_workbook(), FileWorkbook, ExcelWorkbook, WorkbookLockedError
    runner.py                    run(pdfs, workbook, log, prefer_excel) -> RunSummary
    gui.py                       Tkinter window, settings persistence
  tests/
    conftest.py                  fixture: synthetic profile PDF built with fpdf2
    test_pdf_reader.py
    test_people_sheet.py
    test_runner.py
  requirements.txt / requirements-dev.txt
  run_bot.bat / build_exe.bat / README.md
```

## Interfaces (shared names every task relies on)

```python
# person.py
COLUMNS: tuple[str, ...]          # the 10 column names, in order
@dataclass
class Person:
    name: str = ""; property_id: str = ""; address_value: float | str | None = None
    holder: str = ""; property_type: str = ""; classification: str = ""
    owner_location: str = ""; phone_number: str = ""; email_address: str = ""
    age: int | str | None = None; source: str = ""
    def as_row(self) -> dict[str, object]        # column name -> value (None/"" for blanks)
    def missing_fields(self) -> list[str]        # column names with blank values

# pdf_reader.py
class PdfReadError(Exception)
def read_person(pdf_path: str | os.PathLike) -> Person   # raises PdfReadError

# people_sheet.py
class SheetBackend(Protocol):
    def read_values(self) -> list[list[object]]          # rows from A1, ragged OK
    def write_cell(self, row: int, col: int, value: object, number_format: str | None = None) -> None
class SheetLayoutError(Exception)
@dataclass
class AppendResult: added: list[Person]; duplicates: list[Person]; warnings: list[str]; first_row: int | None
def append_people(sheet: SheetBackend, people: list[Person]) -> AppendResult

# workbooks.py
class WorkbookLockedError(Exception)
def make_backup(path: Path, now: datetime | None = None) -> Path
def excel_available() -> bool
def open_workbook(path: Path, prefer_excel: bool = True) -> FileWorkbook | ExcelWorkbook
#   both: .mode (str), SheetBackend methods, .save(), .show(), .close()

# runner.py
@dataclass
class RunSummary: added: list[Person]; duplicates: list[Person]; failed: list[tuple[str, str]]; backup: Path | None; mode: str | None
def run(pdf_paths: list[Path], workbook_path: Path, log: Callable[[str], None], prefer_excel: bool = True) -> RunSummary
```

---

### Task 1: Project setup + Person model + PDF reader

**Files:** Create `requirements*.txt`, `pdf_excel_bot/__init__.py`, `person.py`, `pdf_reader.py`, `tests/conftest.py`, `tests/test_pdf_reader.py`

- [ ] Create `.venv`, install requirements + dev requirements.
- [ ] `conftest.py`: fixture `profile_pdf(tmp_path)` that draws the sample layout with fpdf2: bold name at top; "Contact Information" with `Wireless: (512) 555-0134` and `Landline: (512) 555-0199` and `Email: jordan.avery@example.com`; "Property & Financial Statistics" table (Attribute/Details header, label column x≈81, value column x≈301, ruled rows), Address wrapping onto 2 lines, Classification as the last row on page 1; page 2 repeats the header and has Home Address, Born, Age. Also fixture `blank_pdf` (a page with no text).
- [ ] Failing tests in `test_pdf_reader.py`:
  - every field of the synthetic person is extracted exactly (name, id as text, value as float 12345.67, holder, type, classification "Cash", owner location = home address, phones joined "; ", email, age 47 as int)
  - Classification (last row before the page break) is not dropped
  - `blank_pdf` raises `PdfReadError` mentioning scanned image
  - `Person.missing_fields()` lists Email Address when no email is present
- [ ] Run `pytest tests/test_pdf_reader.py -v` → FAIL (module missing).
- [ ] Implement `person.py` and `pdf_reader.py`: group words into lines (|top diff| ≤ 3); name = first line of page 1; contact lines = between "Contact Information" and the first table header / next section heading; table header = line starting "Attribute" containing "Details", value column x = Details.x0 − 2; label/value split by x; value-only line appends to the current label (persists across pages); table zone ends on a line whose font size differs from the header's by > 1.5; money/age parsing keeps raw text on failure; missing Property ID or name → `PdfReadError`.
- [ ] Run tests → PASS. Then run against the real sample (path passed as argument, file not copied) and eyeball every field.

### Task 2: People sheet logic

**Files:** Create `people_sheet.py`, `tests/test_people_sheet.py`

- [ ] Failing tests using an in-memory `ListSheet(SheetBackend)` test double:
  - empty sheet → headers written in COLUMNS order in row 1, people from row 2
  - existing headers in a different order (and "Phone"/"Email" aliases) → values land under the right headers
  - header row on row 3 under a title → detected; appends after last data row
  - existing Property ID (stored as number 1068268088.0) → person skipped as duplicate; duplicate within the same batch skipped
  - header row missing "Age" → header added in next free column, warning returned
  - non-empty sheet without recognisable headers → `SheetLayoutError`
  - number formats: Property ID "@", Address Value `"$"#,##0.00` (only when numeric), Age "0"
- [ ] Run → FAIL. Implement `append_people`. Run → PASS.

### Task 3: Workbook backends + backups

**Files:** Create `workbooks.py`; extend `tests/test_people_sheet.py` → new `tests/test_workbooks.py`

- [ ] Failing tests: `make_backup` copies to `backups/<stem>_backup_2026-11-01_093000.xlsx`; `FileWorkbook` round-trip (append via `append_people`, save, reload with openpyxl, values + number formats present); missing People tab is created; `.xlsm` keeps VBA flag; locked file → `WorkbookLockedError` (simulate by holding the file open exclusively with `msvcrt.locking`); `.xls` with no Excel → clear error.
- [ ] Implement `FileWorkbook` (openpyxl), `ExcelWorkbook` (pywin32 COM: attach to running Excel via `GetActiveObject` else `Dispatch`, `Visible = True`, reuse already-open workbook by FullName, find/create People, `UsedRange` read in one call, `Save()`, leave Excel open), `excel_available()` (registry `HKCR\Excel.Application`), `open_workbook()` chooser.
- [ ] Run → PASS. Note: `ExcelWorkbook` cannot be exercised on the dev PC (no Excel).

### Task 4: Runner + GUI + packaging + README

**Files:** Create `runner.py`, `gui.py`, `app.py`, `tests/test_runner.py`, `run_bot.bat`, `build_exe.bat`, `README.md`

- [ ] Failing test: `run([good_pdf, blank_pdf, good_pdf_copy], workbook, log)` in file mode → 1 added, 1 duplicate, 1 failed, backup exists, log mentions each file; if every PDF fails the workbook is untouched and no backup is made.
- [ ] Implement `runner.run`. Run → PASS.
- [ ] Implement `gui.py` (PDF list with Add PDFs… / Add folder… / Remove / Clear, workbook picker, Run, log; background thread + queue; COM init on the worker thread; remembers workbook path in `%APPDATA%\PdfExcelBot\settings.json`) and `app.py`.
- [ ] Launch the GUI, run it end-to-end on the real sample into a test workbook, screenshot.
- [ ] `build_exe.bat` with PyInstaller `--onefile --windowed`; build; launch the .exe.
- [ ] README: what it does, how to run (exe / bat), column mapping, backups, troubleshooting.
