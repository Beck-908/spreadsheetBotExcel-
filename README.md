# PDF to Excel Bot

Reads property-profile PDFs (one person per PDF) and adds each person as a new row in the
**People** tab of an Excel workbook.

## Using it

1. Double-click **`dist\PDF to Excel Bot.exe`** (or `run_bot.bat` if you run it from source).
2. **Add PDFs…** to pick one or more PDFs, or **Add folder…** to add every PDF in a folder.
3. **Browse…** to pick the workbook. The bot remembers it next time.
4. Press **Run** and watch the log.

When it finishes, the workbook opens on the People tab with the new rows at the bottom.
Any PDF that couldn't be read stays in the list, and the log says why.

The .exe is self-contained, so coworkers don't need Python. Copy that one file to them.
Windows may warn "Windows protected your PC" the first time, because the file isn't
code-signed. Click **More info → Run anyway**.

## What goes where

| People tab column  | Taken from the PDF                                   |
|--------------------|------------------------------------------------------|
| Responsible Person | The name at the top of page 1                        |
| Property ID        | Property ID (kept as text so no digits are lost)     |
| Value              | Property Value, stored as a number in dollar format (blank if the PDF gives no figure) |
| Holder             | Holder                                               |
| Property Type      | Property Type                                        |
| Classification     | Classification                                       |
| Owner Location     | Home Address                                         |
| Address            | Address                                              |
| Phone Number       | Every phone number under Contact Information, separated by "; " |
| Email Address      | Any email address in the PDF (blank if none)         |
| Age                | Age                                                  |

- **Column order doesn't matter.** The bot finds columns by their header names in the first
  10 rows. It also accepts "Name" for Responsible Person, "Property Value" or "Address Value"
  for Value, and "Phone" and "Email".
- **Empty People tab:** the bot writes the headers in the order above.
- **No People tab:** the bot creates one.
- **Missing column:** if your header row lacks one of these columns, the bot adds it at the end
  and says so in the log.
- **No duplicates:** a person whose Property ID is already in the sheet is skipped, so running
  the same PDFs twice is harmless.
- **Gaps:** fields a PDF doesn't have are left blank and listed in the log.

## Excel or no Excel

- **Excel installed:** the bot opens Excel, goes to the People tab and types the rows in.
  If the workbook is already open, it uses that window, so you don't need to close it.
  Works with .xlsx, .xlsm and .xls.
- **No Excel on the PC:** the bot edits the .xlsx/.xlsm file directly. In this mode the
  workbook must be closed in other programs, and .xls files aren't supported (save as .xlsx).

**Backups:** before every run, the bot copies the workbook into a `backups` folder next to it,
for example `backups\Company Records_backup_2026-11-01_093000.xlsx`. To undo a run, copy the
backup back. Delete old backups whenever you like.

## Troubleshooting

| Message | What to do |
|---------|------------|
| "No readable text found… scanned image" | The PDF is a picture of a page. Ask for the original PDF; the bot can't read scans. |
| "No Property ID found" | That PDF isn't in the property-profile layout. |
| "…is open in another program" | Close the workbook (no-Excel mode only) and press Run again. |
| "…no header row with 'Responsible Person' (or 'Name') and 'Property ID'" | The People tab has data but no recognizable headers. Add a header row, or point the bot at the right workbook. |

## For developers

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
build_exe.bat
```

`build_exe.bat` rebuilds `dist\PDF to Excel Bot.exe`.

| File | Job |
|------|-----|
| `pdf_excel_bot/pdf_reader.py` | Turns one PDF into a `Person`. It rebuilds the Attribute/Details table from word positions, because the standard table extractor drops the last row before a page break. |
| `pdf_excel_bot/people_sheet.py` | Finds headers, skips duplicates and appends rows, through a two-method `SheetBackend` interface. |
| `pdf_excel_bot/workbooks.py` | `ExcelWorkbook` (drives Excel via COM), `FileWorkbook` (openpyxl) and backups. |
| `pdf_excel_bot/runner.py` | One batch run. |
| `pdf_excel_bot/gui.py` | The window. |

Tests build fake PDFs in the same layout (`tests/conftest.py`), so no real customer data is stored here.
The Excel (COM) path hasn't been tested on a machine with Excel yet.

Design notes are in `docs/superpowers/specs/2026-11-01-pdf-to-excel-bot-design.md`.
