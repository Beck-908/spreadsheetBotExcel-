"""Reads one property-profile PDF into a Person.

Profile layout: the person's name at the top of page 1, a "Contact Information"
section with phone/email lines, then an "Attribute | Details" table that can run
onto the next page (where its header row repeats).

pdfplumber's table extractor drops the row right before a page break, so the
table is rebuilt from word positions instead: words left of the "Details" column
are the label, words right of it are the value, and a line that only has a value
continues the previous label (across pages too).
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from .person import Person

LINE_TOLERANCE = 3.0  # points; words whose tops are this close share a line
SIZE_TOLERANCE = 1.5  # points; a line in a different font size ends the table

# Page furniture above the name, such as the header a browser prints ("11/1/26, 9:15 PM  Page title"), a web address
# or a page number. The name is the first line at the top of page 1 that isn't one of these.
FURNITURE_RE = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{2,4}\b|^\d{1,2}:\d{2}\s*[AP]M\b|https?://|www\.|^page \d+|^\d+\s*(of|/)\s*\d+$|^\d+$", re.I
)
PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


class PdfReadError(Exception):
    """The PDF couldn't be turned into a Person; the message is shown to the user."""


@dataclass
class _Line:
    words: list[dict]

    @property
    def text(self) -> str:
        return " ".join(w["text"] for w in self.words)

    @property
    def size(self) -> float:
        return max(w["size"] for w in self.words)


def read_person(pdf_path: str | os.PathLike) -> Person:
    path = Path(pdf_path)
    try:
        with pdfplumber.open(path) as pdf:
            pages = [_lines(page.extract_words(extra_attrs=["size"])) for page in pdf.pages]
    except Exception as exc:  # pdfminer raises many unrelated exception types for bad files
        raise PdfReadError(f"Couldn't open the PDF ({exc}).") from exc

    all_lines = [line for page in pages for line in page]
    if not all_lines:
        raise PdfReadError("No readable text found. It may be a scanned image, which the bot can't read.")

    table = _table_fields(pages)
    person = Person(
        name=_name(pages[0] or all_lines),
        property_id=table.get("property id", "").replace(" ", ""),
        value=_parse_money(table.get("property value") or table.get("value", "")),
        holder=table.get("holder", ""),
        property_type=table.get("property type", ""),
        classification=table.get("classification", ""),
        owner_location=table.get("home address", ""),
        address=table.get("address", ""),
        phone_number="; ".join(_phones(all_lines)),
        email_address=_email(all_lines),
        age=_parse_int(table.get("age", "")),
        source=path.name,
    )
    if not person.property_id:
        raise PdfReadError("No Property ID found. Is this a property profile PDF?")
    if not person.name:
        raise PdfReadError("No name found at the top of the first page.")
    if "(cid:" in person.name:
        raise PdfReadError("The name at the top is in a font the PDF doesn't let programs read. Ask for the original PDF.")
    return person


def _lines(words: list[dict]) -> list[_Line]:
    """Group a page's words into lines, top to bottom, each line left to right."""
    groups: list[list[dict]] = []
    for word in sorted(words, key=lambda w: w["top"]):
        if groups and abs(word["top"] - groups[-1][0]["top"]) <= LINE_TOLERANCE:
            groups[-1].append(word)
        else:
            groups.append([word])
    return [_Line(sorted(group, key=lambda w: w["x0"])) for group in groups]


def _norm(text: str) -> str:
    return " ".join(text.lower().rstrip(":").split())


def _is_table_header(line: _Line) -> bool:
    return line.words[0]["text"] == "Attribute" and any(w["text"] == "Details" for w in line.words)


def _table_fields(pages: list[list[_Line]]) -> dict[str, str]:
    """Return {normalised label: value} for every Attribute/Details row in the PDF."""
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for lines in pages:
        value_x = header_size = None  # set while inside a table on this page
        for line in lines:
            if _is_table_header(line):
                details = next(w for w in line.words if w["text"] == "Details")
                value_x, header_size = details["x0"] - 2, line.size
                continue
            if value_x is None:
                continue
            if abs(line.size - header_size) > SIZE_TOLERANCE:
                value_x = None  # heading, footer, etc. — the table has ended
                continue
            label = " ".join(w["text"] for w in line.words if w["x0"] < value_x)
            value = " ".join(w["text"] for w in line.words if w["x0"] >= value_x)
            if label:
                current = _norm(label)
                fields[current] = [value] if value else []
            elif current is not None:
                fields[current].append(value)
    return {label: " ".join(parts) for label, parts in fields.items()}


def _name(lines: list[_Line]) -> str:
    """The first line at the top of page 1, skipping printed headers, web addresses and page numbers."""
    for line in lines:
        if _norm(line.text) == "contact information" or _is_table_header(line):
            return ""  # reached the profile itself without a name
        if not FURNITURE_RE.search(line.text.strip()):
            return line.text
    return ""


def _phones(lines: list[_Line]) -> list[str]:
    """Phone numbers in the Contact Information section, in order, without repeats."""
    start = next((i for i, line in enumerate(lines) if _norm(line.text) == "contact information"), None)
    if start is None:
        return []
    heading_size = lines[start].size
    phones: list[str] = []
    for line in lines[start + 1:]:
        if _is_table_header(line) or line.size >= heading_size - SIZE_TOLERANCE:
            break  # next section
        for phone in PHONE_RE.findall(line.text):
            if phone not in phones:
                phones.append(phone)
    return phones


def _email(lines: list[_Line]) -> str:
    match = EMAIL_RE.search("\n".join(line.text for line in lines))
    return match.group(0) if match else ""


MONEY_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?|-?\.\d+")


def _parse_money(text: str) -> float | None:
    """The first dollar figure in the text ("$12,345.67", "12345.67 USD", "Approx. $1,200") as a number,
    so Excel can add and sort it. No figure at all ("Not disclosed") leaves the cell blank."""
    match = MONEY_RE.search(text or "")
    return float(match.group(0).replace(",", "")) if match else None


def _parse_int(text: str) -> int | str | None:
    if not text:
        return None
    return int(text) if text.strip().isdigit() else text
