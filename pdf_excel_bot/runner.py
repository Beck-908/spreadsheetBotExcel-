"""One bot run: read every PDF, back up the workbook, append the people, report."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import VERSION
from .pdf_reader import PdfReadError, read_person
from .people_sheet import append_people
from .person import Person
from .workbooks import make_backup, open_workbook


@dataclass
class RunSummary:
    added: list[Person] = field(default_factory=list)
    duplicates: list[Person] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (PDF file name, reason)
    backup: Path | None = None
    mode: str | None = None  # "Excel" or "file"


def run(
    pdf_paths: list[Path],
    workbook_path: Path,
    log: Callable[[str], None],
    prefer_excel: bool = True,
    show_result: bool = True,
) -> RunSummary:
    """Raises WorkbookError / SheetLayoutError when the workbook itself can't be used."""
    summary = RunSummary()
    people: list[Person] = []
    log(f"PDF to Excel Bot {VERSION}")
    for pdf in map(Path, pdf_paths):
        try:
            person = read_person(pdf)
        except PdfReadError as exc:
            summary.failed.append((pdf.name, str(exc)))
            log(f"✗ {pdf.name}: {exc}")
            continue
        people.append(person)
        missing = person.missing_fields()
        note = f" (not in PDF: {', '.join(missing)})" if missing else ""
        value = f"${person.value:,.2f}" if person.value is not None else "none"
        log(f"✓ Read {person.name}, Property ID {person.property_id}, Value {value}, from {pdf.name}{note}")

    if not people:
        log("Nothing to add because no PDF could be read. The workbook was not touched.")
        return summary

    workbook = open_workbook(Path(workbook_path), prefer_excel)
    try:
        summary.mode = workbook.mode
        summary.backup = make_backup(workbook.path)
        log(f"Backup saved to {summary.backup}")
        if workbook.mode == "Excel":
            log("Writing into the People tab in Excel…")
        else:
            log("Excel isn't available on this PC, so the bot is editing the workbook file directly…")

        result = append_people(workbook, people)
        workbook.save()
        if show_result:
            workbook.show()
    finally:
        workbook.close()

    summary.added, summary.duplicates = result.added, result.duplicates
    for warning in result.warnings:
        log(f"⚠ {warning}")
    for person in result.duplicates:
        log(f"– Skipped {person.name} from {person.source}: Property ID {person.property_id} is already in the People tab.")
    if result.first_row:
        log(f"Added rows {result.first_row}–{result.first_row + len(result.added) - 1} of the People tab.")
    log(
        f"Done: {len(summary.added)} added, {len(summary.duplicates)} skipped as duplicates, "
        f"{len(summary.failed)} failed."
    )
    return summary
