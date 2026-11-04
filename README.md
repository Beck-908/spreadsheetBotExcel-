# PDF to Excel Bot

Reads property-profile PDFs (one person per PDF) and adds each person as a new row in the
**People** tab of an Excel workbook.

## Using it

1. Double-click **`dist\PDF to Excel Bot.exe`** (or `run_bot.bat` if you run it from source).
2. Drag PDFs onto the window, or use the **paperclip** (pick PDFs) or **folder** (every PDF in a folder) buttons.
3. Pick the workbook from the menu at the bottom left. It remembers your recent workbooks and
   shows how many people each one already holds. **Choose another workbook…** opens any other.
4. Optionally change **Auto** to **Excel** (always type into Excel) or **File only** (edit the file
   without opening Excel). Auto uses Excel when it's installed.
5. Press the **arrow** button.

Each PDF appears as it's read, then shows the row it went into, "Already in sheet", or why it
couldn't be read. A one-line summary says what changed and where the backup went. When it
finishes, the workbook opens on the People tab. **Try the failed PDFs again** puts any failures
back in the box.

The .exe is self-contained, so coworkers don't need Python. Copy that one file to them.
Windows may warn "Windows protected your PC" the first time, because the file isn't
code-signed. Click **More info → Run anyway**.

## What goes where

| People tab column  | Taken from the PDF                                   |
|--------------------|------------------------------------------------------|
| Responsible Person | The name at the top of page 1 (see below)            |
| Property ID        | Property ID, stored as a number (leading zeros still show) |
| Value              | Property Value, stored as a number in dollar format (blank if the PDF gives no figure) |
| Holder             | Holder                                               |
| Property Type      | Property Type                                        |
| Classification     | Classification                                       |
| Owner Location     | Home Address                                         |
| Address            | Address                                              |
| Phone Number       | Every phone number under Contact Information, separated by "; " |
| Email Address      | Any email address in the PDF (blank if none)         |
| Age                | Age, or worked out from the birth date ("Born") if there's no Age |

**The name.** The bot takes the biggest text above "Contact Information" on page 1, skipping a
browser's printed date/title header, web addresses and page numbers. A name that wraps onto two
lines is joined back up. If a line on top matches the PDF's file name, that line wins. If the
top of the page has no readable name at all, the bot uses a "Responsible Person"/"Name"/"Owner"
row in the table, and failing that the PDF's file name. The log says when it did that.

**Other labels.** The bot also understands common alternatives, such as "Amount" or "Value" for
Property Value, "Type", "Category", "Property Address", and "Location" when there's no Home Address.

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

**Which version?** The window title and the top of the window show the version, for example
"PDF to Excel Bot 2.0". If someone gets different results from you, check they have the same one.

**The log.** Every run's full log (the name and value read from every PDF, warnings, and any
error details) is saved to `%APPDATA%\PdfExcelBot\last run.log`. Paste that into Windows
Explorer's address bar to find it. Send it along when reporting a problem.

**The classic window.** The window needs Microsoft's WebView2 runtime, which comes with Windows 10
and 11 through Edge. If it can't open, the bot opens its older plain window instead and saves the
reason to `%APPDATA%\PdfExcelBot\desktop window error.log`. You can also open the classic window
on purpose with `app.py --classic`.

| Message | What to do |
|---------|------------|
| "(name taken from the file name…)" | The top of the page had no readable name, so the file name was used. Name PDFs after the person. |
| "No readable text found… scanned image" | The PDF is a picture of a page. Ask for the original PDF; the bot can't read scans. |
| "The file isn't there any more" | The PDF was moved, renamed or deleted after you added it. Add it again from where it is now. |
| "Excel isn't installed on this PC" | You chose **Excel** mode on a PC without Excel. Choose **Auto** or **File only**. |
| "No Property ID found" | That PDF isn't in the property-profile layout. |
| "…is open in another program" | Close the workbook (no-Excel mode only) and press Run again. |
| "…no header row with 'Responsible Person' (or 'Name') and 'Property ID'" | The People tab has data but no recognizable headers. Add a header row, or point the bot at the right workbook. |

## For developers

You need Python 3.12+ and Node.js 20+.

```bat
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
build_exe.bat
```

`build_exe.bat` builds the window's UI (`frontend\` into `frontend\dist`), then packs everything into
`dist\PDF to Excel Bot.exe`.

**Working on the UI.** Run `npm run dev` in `frontend\` and open http://localhost:5174. In the
browser the UI talks to a fake bot with made-up people (`frontend/src/lib/bot.ts`), so you can
click through everything without touching real files. To see your changes in the real window,
run `npm run build` and then `.venv\Scripts\python app.py`.

| File | Job |
|------|-----|
| `pdf_excel_bot/pdf_reader.py` | Turns one PDF into a `Person`. It rebuilds the Attribute/Details table from word positions, because the standard table extractor drops the last row before a page break. |
| `pdf_excel_bot/people_sheet.py` | Finds headers, skips duplicates and appends rows, through a two-method `SheetBackend` interface. |
| `pdf_excel_bot/workbooks.py` | `ExcelWorkbook` (drives Excel via COM), `FileWorkbook` (openpyxl) and backups. |
| `pdf_excel_bot/runner.py` | One batch run, with optional per-PDF progress callbacks. |
| `pdf_excel_bot/desktop.py` | The desktop window: shows `frontend/dist` with pywebview, and its `Api` is what the page calls (pick files, list workbooks, run). It also listens for dropped files, because only Python gets their full paths. |
| `frontend/` | The window's UI (React, Tailwind, shadcn). `src/lib/bot.ts` is the page's side of `Api`, plus the fake bot. `src/components/ai-blob.tsx` comes from React Bits (Starter licence). |
| `pdf_excel_bot/gui.py` | The classic Tkinter window, kept as the fallback. |
| `pdf_excel_bot/settings.py` | Recent workbooks, last PDF folder and the last run's log, in `%APPDATA%\PdfExcelBot`. |

Tests build fake PDFs in the same layout (`tests/conftest.py`), so no real customer data is stored here.
The Excel (COM) path hasn't been tested on a machine with Excel yet.

Design notes are in `docs/superpowers/specs/2026-11-01-pdf-to-excel-bot-design.md`.
