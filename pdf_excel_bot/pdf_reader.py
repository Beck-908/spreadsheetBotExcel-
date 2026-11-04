"""Reads one property-profile PDF into a Person.

Profile layout: the person's name at the top of page 1, a "Contact Information"
section with phone/email lines, then an "Attribute | Details" table that can run
onto the next page (where its header row repeats).

pdfplumber's table extractor drops the row right before a page break, so the
table is rebuilt from word positions instead: words left of the "Details" column
are the label, words right of it are the value, and a line that only has a value
continues the previous label (across pages too).

Every column should end up filled, so each field has fallbacks: other labels the
same thing goes by, the file name for the person's name, and the birth date for
the age. Person.notes records when a fallback was used, for the log.
"""

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pdfplumber

from .person import Person

LINE_TOLERANCE = 3.0  # points; words whose tops are this close share a line
SIZE_TOLERANCE = 1.5  # points; a line in a different font size ends the table
SAME_ROW = 1.8  # a labelled line closer than this many font sizes below the last one wraps the same table row

# Page furniture above the name, such as the header a browser prints ("11/1/26, 9:15 PM  Page title"), a web address
# or a page number.
FURNITURE_RE = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{2,4}\b|^\d{1,2}:\d{2}\s*[AP]M\b|https?://|www\.|^page \d+|^\d+\s*(of|/)\s*\d+$|^\d+$", re.I
)
# Headings that start the profile itself; the name is above them.
SECTION_RE = re.compile(r"^(contact info|property (&|and) financial|property details|attribute\b)", re.I)
PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}")
FORMATTED_PHONE_RE = re.compile(r"\(\d{3}\)\s*\d{3}[\s.-]\d{4}|\b\d{3}[.-]\d{3}[.-]\d{4}\b")  # not a bare 10-digit ID
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
MONEY_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?|-?\.\d+")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

# Table labels each field is found under, best first.
LABELS = {
    "name": ("responsible person", "owner name", "full name", "name", "owner", "reported owner"),
    "property_id": ("property id", "property number", "property no", "property #", "id"),
    "value": ("property value", "value", "amount", "cash value", "reported value", "property amount"),
    "holder": ("holder", "holder name", "reported by"),
    "property_type": ("property type", "type"),
    "classification": ("classification", "class", "category"),
    "owner_location": ("home address", "current address", "residential address", "residence", "owner location"),
    "address": ("address", "property address", "reported address", "last known address"),
    "phone": ("phone", "phone number", "phones", "wireless", "landline", "mobile"),
    "email": ("email", "email address"),
    "age": ("age",),
    "born": ("born", "birth date", "date of birth", "dob", "birthday"),
}


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

    @property
    def top(self) -> float:
        return min(w["top"] for w in self.words)


def read_person(pdf_path: str | os.PathLike, today: date | None = None) -> Person:
    path = Path(pdf_path)
    try:
        with pdfplumber.open(path) as pdf:
            pages = [_lines(page.extract_words(extra_attrs=["size"])) for page in pdf.pages]
    except FileNotFoundError as exc:
        raise PdfReadError("The file isn't there any more. It may have been moved, renamed or deleted.") from exc
    except PermissionError as exc:
        raise PdfReadError("Windows wouldn't let the bot open this file. Close it in other programs and try again.") from exc
    except Exception as exc:  # pdfminer raises many unrelated exception types for bad files
        raise PdfReadError(f"Couldn't open the PDF ({exc}).") from exc

    all_lines = [line for page in pages for line in page]
    if not all_lines:
        raise PdfReadError("No readable text found. It may be a scanned image, which the bot can't read.")

    table = _table_fields(pages)
    notes: list[str] = []

    def field(key: str, contains: tuple[str, ...] = ()) -> str:
        return _pick(table, LABELS[key], contains)

    property_id = field("property_id").replace(" ", "")
    if not property_id:
        raise PdfReadError("No Property ID found. Is this a property profile PDF?")

    owner_location = field("owner_location", contains=("home",))
    if not owner_location and table.get("location"):
        owner_location = table["location"]
        notes.append("Owner Location is the PDF's Location (no Home Address)")

    age = _parse_int(field("age"))
    if not isinstance(age, int):
        born_age = _age_from_birth(field("born"), today or date.today())
        if born_age is not None:
            age = born_age
            notes.append("Age worked out from the birth date")

    phones = _phones(all_lines) or _unique(FORMATTED_PHONE_RE.findall(field("phone") + "\n" + _text(all_lines)))
    return Person(
        name=_name(pages[0] or all_lines, field("name"), path, notes),
        property_id=property_id,
        value=_parse_money(field("value", contains=("value", "amount"))),
        holder=field("holder", contains=("holder",)),
        property_type=field("property_type", contains=("type",)),
        classification=field("classification"),
        owner_location=owner_location,
        address=field("address", contains=("address",)),
        phone_number="; ".join(phones),
        email_address=_email(all_lines),
        age=age,
        source=path.name,
        notes=notes,
    )


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


def _text(lines: list[_Line]) -> str:
    return "\n".join(line.text for line in lines)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _is_table_header(line: _Line) -> bool:
    return line.words[0]["text"] == "Attribute" and any(w["text"] == "Details" for w in line.words)


def _table_fields(pages: list[list[_Line]]) -> dict[str, str]:
    """Return {normalised label: value} for every Attribute/Details row in the PDF."""
    rows: list[list] = []  # [label, value parts]
    for lines in pages:
        value_x = header_size = None  # set while inside a table on this page
        last_top = None
        for line in lines:
            if _is_table_header(line):
                details = next(w for w in line.words if w["text"] == "Details")
                value_x, header_size, last_top = details["x0"] - 2, line.size, None
                continue
            if value_x is None:
                continue
            if abs(line.size - header_size) > SIZE_TOLERANCE:
                value_x = None  # heading, footer, etc. — the table has ended
                continue
            label = " ".join(w["text"] for w in line.words if w["x0"] < value_x)
            value = " ".join(w["text"] for w in line.words if w["x0"] >= value_x)
            wraps = rows and last_top is not None and line.top - last_top < SAME_ROW * line.size
            if label and wraps:
                rows[-1][0] += " " + label  # a long label ("Property" / "Value") wrapped inside its row
            elif label:
                rows.append([label, []])
            if value and rows:
                rows[-1][1].append(value)
            last_top = line.top
    return {_norm(label): " ".join(parts) for label, parts in rows}


def _pick(table: dict[str, str], labels: tuple[str, ...], contains: tuple[str, ...] = ()) -> str:
    """The value under the first of `labels` the table has; failing that, under any label containing `contains`."""
    for label in labels:
        if table.get(label):
            return table[label]
    for label, value in table.items():
        if value and any(word in label for word in contains):
            return value
    return ""


def _name(lines: list[_Line], table_name: str, path: Path, notes: list[str]) -> str:
    """The name at the top of page 1. If the PDF doesn't have it as readable text, a Name row in
    the table, then the PDF's file name (these profiles are saved under the person's name)."""
    name = _top_name(lines, path.stem)
    if name and "(cid:" not in name:
        return name
    if table_name:
        notes.append("name taken from the table, not the top of the page")
        return table_name
    from_file = _clean_file_name(path.stem)
    if from_file:
        notes.append("name taken from the file name; the top of the page had no readable name")
    return from_file


def _top_name(lines: list[_Line], file_stem: str) -> str:
    """The biggest text above the Contact Information heading, skipping printed headers (date, web address,
    page number). A line matching the file name wins, and a name too long for one line is joined back up."""
    top: list[_Line] = []
    for line in lines:
        text = line.text.strip()
        if SECTION_RE.search(text) or _is_table_header(line):
            break
        if FURNITURE_RE.search(text) or not any(c.isalpha() for c in text) or ":" in text:
            continue  # page furniture, a lone number, or a "Wireless: …" line
        top.append(line)
    if not top:
        return ""

    stem = _letters(file_stem)
    matching = [i for i, line in enumerate(top) if stem and _letters(line.text) == stem]
    biggest = max(line.size for line in top)
    first = matching[0] if matching else next(i for i, line in enumerate(top) if line.size >= biggest - 0.5)

    parts = [top[first]]
    for line in top[first + 1:]:
        close = line.top - parts[-1].top < SAME_ROW * line.size
        if not close or abs(line.size - parts[-1].size) > 0.5:
            break
        parts.append(line)
    return " ".join(part.text for part in parts).strip()


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _clean_file_name(stem: str) -> str:
    """'Jordan_Avery (1)' -> 'Jordan Avery'. Blank when the file name has no letters."""
    text = re.sub(r"\(\d+\)|\bcopy\b", " ", stem, flags=re.I)
    text = " ".join(re.sub(r"[_]+", " ", text).split())
    return text if any(c.isalpha() for c in text) else ""


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
        phones.extend(PHONE_RE.findall(line.text))
    return _unique(phones)


def _email(lines: list[_Line]) -> str:
    match = EMAIL_RE.search(_text(lines))
    return match.group(0) if match else ""


def _parse_money(text: str) -> float | None:
    """The first dollar figure in the text ("$12,345.67", "12345.67 USD", "Approx. $1,200") as a number,
    so Excel can add and sort it. No figure at all ("Not disclosed") leaves the cell blank."""
    match = MONEY_RE.search(text or "")
    return float(match.group(0).replace(",", "")) if match else None


def _parse_int(text: str) -> int | str | None:
    """'47' or '47 years' -> 47. Text with no number ('Unknown') is kept as it is."""
    if not text:
        return None
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else text


def _age_from_birth(text: str, today: date) -> int | None:
    """'Mar 1979', '03/15/1979' or '1979' -> age today. When only the year is known, assumes the birthday has passed."""
    year = YEAR_RE.search(text or "")
    if not year:
        return None
    born = int(year.group(0))
    lowered = text.lower()
    month = next((i for i, m in enumerate(MONTHS, start=1) if m in lowered), None)
    numeric = re.match(r"\s*(\d{1,2})[/-]", text)
    if month is None and numeric and 1 <= int(numeric.group(1)) <= 12:
        month = int(numeric.group(1))
    age = today.year - born - (1 if month and month > today.month else 0)
    return age if 0 <= age < 130 else None
