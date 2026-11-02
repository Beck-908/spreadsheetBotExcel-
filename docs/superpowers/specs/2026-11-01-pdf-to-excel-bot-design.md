# PDF-to-Excel Bot — Design

Date: 2026-11-01
Status: Approved by user

## Goal

A double-click Windows app that reads one or more property-profile PDFs (one person per PDF)
and appends one row per person to the **People** tab of a chosen Excel workbook.

## Output columns (in this order when the bot writes headers)

| Excel column    | Source in PDF                                         | Stored as            |
|-----------------|-------------------------------------------------------|----------------------|
| Name            | Bold heading at the top of page 1                     | text                 |
| Property ID     | Table row "Property ID"                               | text (keeps digits)  |
| Address Value   | Table row "Property Value"                            | number, `$#,##0.00`  |
| Holder          | Table row "Holder"                                    | text                 |
| Property Type   | Table row "Property Type"                             | text                 |
| Classification  | Table row "Classification"                            | text                 |
| Owner Location  | Table row "Home Address"                              | text                 |
| Phone Number    | Phone numbers in the "Contact Information" section, joined with "; " | text  |
| Email Address   | First email address anywhere in the PDF, else blank   | text                 |
| Age             | Table row "Age"                                       | whole number         |

## PDF format (from sample "SANCTUM MANAGEMENT PTE LIMITED.pdf")

- Page 1 top: person's name (bold, 11pt), then a photo.
- "Contact Information" heading, then lines like `Wireless: (408) 223-2253`.
- "Property & Financial Statistics" heading, then a two-column table with header row
  `Attribute | Details`. The table can continue on the next page, where the header row repeats.
- Values can wrap onto several lines (e.g. Address).
- The default PDF table extractor drops the last row before a page break, so the bot does **not**
  rely on table borders. It groups words into lines by vertical position and splits each line into
  label (left of the "Details" column) and value (right of it). A line with only a value is a
  continuation of the previous label, including across pages.

## Excel behaviour

- Finds the sheet named `People` (case-insensitive); creates it if missing.
- Finds the header row by scanning the first 10 rows for a row containing "Name" and "Property ID"
  (case/space-insensitive; "Phone"/"Email" accepted as aliases). If the sheet is empty, writes the
  headers in the order above in row 1. If an existing header row is missing one of the columns,
  the bot adds that header in the next free column and logs a warning.
- Appends below the last row that has any value. Skips a person whose Property ID already exists
  in the sheet or earlier in the same batch.
- Two backends behind one interface:
  - **Excel backend** (Excel installed): drives Excel through COM, makes it visible, opens the
    workbook (or reuses it if already open), activates People, writes, saves, leaves Excel open.
  - **File backend** (no Excel): edits the .xlsx/.xlsm with openpyxl, then opens it with the default
    app. If the file is locked, tells the user to close it.

## Safety

- Before every run, copy the workbook to `backups/<name>_backup_<YYYY-MM-DD_HHMMSS><ext>` next to it.
- Per-PDF failures (no text layer, no name, no Property ID) are logged and skipped; the batch continues.
- End-of-run summary: added / skipped as duplicate / failed, plus missing fields per person.

## App

- Tkinter window: PDF list with Add PDFs… / Add folder… / Remove / Clear; workbook picker; Run;
  scrolling log. Work runs on a background thread. Last workbook path is remembered per user
  (`%APPDATA%\PdfExcelBot\settings.json`).
- Packaged with PyInstaller as one `.exe`; `run_bot.bat` runs from source.

## Testing

- Unit tests run against a synthetic PDF in the same layout (fake person, table split across pages,
  wrapped address, two phones, an email) generated at test time.
- Sheet logic tested against openpyxl workbooks: empty sheet, existing headers in another order,
  duplicates, missing People tab.
- Manual check that every field is extracted correctly from the real sample (not copied into the repo).
- The Excel (COM) backend cannot be tested on the dev PC (no Excel installed).
