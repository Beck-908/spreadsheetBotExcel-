import pytest

from pdf_excel_bot.people_sheet import SheetLayoutError, append_people
from pdf_excel_bot.person import COLUMNS, Person


class ListSheet:
    """In-memory SheetBackend: rows of values, 1-based like Excel."""

    def __init__(self, rows=None):
        self.rows = [list(row) for row in rows or []]
        self.formats = {}

    def read_values(self):
        return [list(row) for row in self.rows]

    def write_cell(self, row, col, value, number_format=None):
        while len(self.rows) < row:
            self.rows.append([])
        cells = self.rows[row - 1]
        while len(cells) < col:
            cells.append(None)
        cells[col - 1] = value
        if number_format:
            self.formats[(row, col)] = number_format

    def row(self, n):
        return self.rows[n - 1]


def person(property_id="5550001234", name="Jordan Avery", **fields):
    defaults = dict(
        value=12345.67, holder="EXAMPLE INC", property_type="SC01: DIVIDENDS",
        classification="Cash", owner_location="42 Test Lane, Austin, TX", address="1 Main St, Springfield, IL",
        phone_number="(512) 555-0134",
        email_address="j@example.com", age=47,
    )
    return Person(name=name, property_id=property_id, **{**defaults, **fields})


def test_empty_sheet_gets_headers_then_people():
    sheet = ListSheet()
    result = append_people(sheet, [person()])

    assert sheet.row(1) == list(COLUMNS)
    assert sheet.row(2) == ["Jordan Avery", "5550001234", 12345.67, "EXAMPLE INC", "SC01: DIVIDENDS", "Cash",
                            "42 Test Lane, Austin, TX", "1 Main St, Springfield, IL", "(512) 555-0134", "j@example.com", 47]
    assert result.first_row == 2
    assert [p.property_id for p in result.added] == ["5550001234"]


def test_existing_headers_in_other_order_and_aliases():
    headers = ["Email", "Name", "Age", "Phone", "Property ID", "Address Value", "Holder", "Property Type",
               "Classification", "Owner Location"]
    sheet = ListSheet([headers, ["old@example.com", "Old Person", 80, None, "111"]])
    append_people(sheet, [person()])

    new = dict(zip(headers, sheet.row(3)))
    assert new["Email"] == "j@example.com"
    assert new["Name"] == "Jordan Avery"
    assert new["Phone"] == "(512) 555-0134"
    assert new["Property ID"] == "5550001234"
    assert new["Age"] == 47


def test_headers_from_earlier_versions_and_a_plain_value_column():
    # "Name" and "Address Value" are what the bot used to write; a hand-made sheet may just say "Value".
    for value_header in ("Address Value", "Value", "Property Value"):
        headers = ["Name", "Property ID", value_header, "Holder", "Property Type", "Classification",
                   "Owner Location", "Address", "Phone Number", "Email Address", "Age"]
        sheet = ListSheet([headers])
        result = append_people(sheet, [person()])
        assert result.warnings == []
        row = dict(zip(headers, sheet.row(2)))
        assert row["Name"] == "Jordan Avery" and row[value_header] == 12345.67
        assert sheet.formats[(2, 3)] == '"$"#,##0.00'


def test_header_row_below_a_title_and_trailing_blank_rows():
    sheet = ListSheet([
        ["People Report"],
        [],
        list(COLUMNS),
        ["A", "1"],
        ["B", "2", None, None, None, None, None, None, None, None, None, "note in an extra column"],
        [None, None, None],  # formatted-but-empty rows that spreadsheets report
        [None, ""],
    ])
    result = append_people(sheet, [person()])
    assert result.first_row == 6
    assert sheet.row(6)[:2] == ["Jordan Avery", "5550001234"]


def test_duplicate_property_ids_are_skipped():
    # Excel hands back numeric cells as floats.
    sheet = ListSheet([list(COLUMNS), ["Existing", 5550001234.0]])
    result = append_people(sheet, [person(), person("777", "New"), person("777", "New again")])

    assert [p.property_id for p in result.added] == ["777"]
    assert [p.name for p in result.duplicates] == ["Jordan Avery", "New again"]
    assert len(sheet.rows) == 3


def test_missing_column_is_added_with_warning():
    sheet = ListSheet([list(COLUMNS[:-1]) + [None, "Notes"]])  # no Age; a gap, then an unrelated column
    result = append_people(sheet, [person()])

    assert sheet.row(1)[12] == "Age"
    assert sheet.row(2)[12] == 47
    assert result.warnings == ["The People tab had no 'Age' column, so it was added in column M."]


def test_data_without_headers_is_refused():
    sheet = ListSheet([["some", "thing"], ["else", "here"]])
    with pytest.raises(SheetLayoutError, match="Property ID"):
        append_people(sheet, [person()])
    assert sheet.rows == [["some", "thing"], ["else", "here"]]


def test_number_formats():
    sheet = ListSheet()
    append_people(sheet, [person(), person("888", value=None, age="Unknown")])

    assert sheet.formats[(2, 2)] == "@"
    assert sheet.formats[(2, 3)] == '"$"#,##0.00'
    assert sheet.formats[(2, 11)] == "0"
    assert len(sheet.row(3)) < 3 or sheet.row(3)[2] is None  # no figure in the PDF: Value left blank
    assert (3, 11) not in sheet.formats  # an age that is text stays unformatted


def test_blank_fields_leave_cells_empty():
    sheet = ListSheet()
    append_people(sheet, [person(email_address="", age=None)])
    assert sheet.row(2)[9:] == []  # nothing written past Phone Number
