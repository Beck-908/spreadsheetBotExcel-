"""Puts people into the People tab: finds the header row, skips duplicates, appends rows.

Works through the tiny SheetBackend interface, so the same rules apply whether the
bot is driving Excel or editing the workbook file directly.
"""

import re
from dataclasses import dataclass, field
from typing import Protocol

from .person import COLUMNS, Person

HEADER_SEARCH_ROWS = 10
NUMBER_FORMATS = {"Property ID": "0", "Value": '"$"#,##0.00', "Age": "0"}
MAX_EXACT_DIGITS = 15  # Excel keeps 15 significant digits; longer IDs stay text


class SheetBackend(Protocol):
    def read_values(self) -> list[list[object]]:
        """Cell values from A1 down/right to the last used cell; rows may be ragged."""

    def write_cell(self, row: int, col: int, value: object, number_format: str | None = None) -> None:
        """Write one cell (1-based row and column)."""


class SheetLayoutError(Exception):
    """The People tab can't be written safely; the message is shown to the user."""


@dataclass
class AppendResult:
    added: list[Person] = field(default_factory=list)
    duplicates: list[Person] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    first_row: int | None = None  # sheet row of the first added person


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


# Normalised header text -> column it fills. Short forms, and the headers earlier versions wrote, are accepted too.
HEADER_NAMES = {_norm(column): column for column in COLUMNS} | {
    "name": "Responsible Person",
    "propertyvalue": "Value",
    "addressvalue": "Value",
    "phone": "Phone Number",
    "email": "Email Address",
}


def append_people(sheet: SheetBackend, people: list[Person]) -> AppendResult:
    result = AppendResult()
    values = sheet.read_values()

    header_row = _find_header_row(values)
    if header_row is None:
        if any(_filled(v) for row in values for v in row):
            raise SheetLayoutError(
                "The People tab has data but no header row with 'Responsible Person' (or 'Name') and 'Property ID' "
                f"in its first {HEADER_SEARCH_ROWS} rows, so the bot doesn't know where to put things."
            )
        header_row, values = 1, [list(COLUMNS)]
        for col, title in enumerate(COLUMNS, start=1):
            sheet.write_cell(1, col, title)

    headers = values[header_row - 1]
    col_of = _map_columns(headers)
    next_free = max((i for i, v in enumerate(headers, start=1) if _filled(v)), default=0) + 1
    for column in COLUMNS:
        if column not in col_of:
            sheet.write_cell(header_row, next_free, column)
            col_of[column] = next_free
            result.warnings.append(
                f"The People tab had no '{column}' column, so it was added in column {_column_letter(next_free)}."
            )
            next_free += 1

    last_row = max((i for i, row in enumerate(values, start=1) if any(_filled(v) for v in row)), default=0)
    last_row = max(last_row, header_row)

    id_col = col_of["Property ID"]
    seen = {_id_key(row[id_col - 1]) for row in values[header_row:] if len(row) >= id_col and _filled(row[id_col - 1])}

    for person in people:
        if _id_key(person.property_id) in seen:
            result.duplicates.append(person)
            continue
        last_row += 1
        for column, value in person.as_row().items():
            if not _filled(value):
                continue
            if column == "Property ID":
                value, number_format = _id_cell(value)
            else:
                # Text in a numeric column (an age of "Unknown") stays plain text.
                number_format = NUMBER_FORMATS.get(column) if isinstance(value, (int, float)) else None
            sheet.write_cell(last_row, col_of[column], value, number_format)
        seen.add(_id_key(person.property_id))
        result.added.append(person)
        result.first_row = result.first_row or last_row
    return result


def count_people(values: list[list[object]]) -> int | None:
    """People already in a sheet: filled rows under the header row. None when there's data but no header row."""
    header_row = _find_header_row(values)
    if header_row is None:
        return None if any(_filled(v) for row in values for v in row) else 0
    return sum(1 for row in values[header_row:] if any(_filled(v) for v in row))


def _filled(value: object) -> bool:
    return value is not None and str(value).strip() != ""


def _find_header_row(values: list[list[object]]) -> int | None:
    for i, row in enumerate(values[:HEADER_SEARCH_ROWS], start=1):
        columns = {HEADER_NAMES.get(_norm(v)) for v in row if _filled(v)}
        if {"Responsible Person", "Property ID"} <= columns:
            return i
    return None


def _map_columns(headers: list[object]) -> dict[str, int]:
    col_of: dict[str, int] = {}
    for col, header in enumerate(headers, start=1):
        column = HEADER_NAMES.get(_norm(header)) if _filled(header) else None
        if column and column not in col_of:
            col_of[column] = col
    return col_of


def _id_key(value: object) -> str:
    """Compare Property IDs whether the cell holds a number (1068268088.0) or text ("1068268088", "0012")."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return (text.lstrip("0") or "0") if text.isdigit() else text


def _id_cell(property_id: str) -> tuple[object, str | None]:
    """An all-digit ID goes in as a number. Leading zeros stay visible through the format ("0012" shows as 0012)."""
    if not property_id.isdigit() or len(property_id.lstrip("0")) > MAX_EXACT_DIGITS:
        return property_id, "@"
    number_format = "0" * len(property_id) if property_id.startswith("0") else NUMBER_FORMATS["Property ID"]
    return int(property_id), number_format


def _column_letter(col: int) -> str:
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return letters
