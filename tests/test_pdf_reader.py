import pytest

from conftest import DEFAULT_PAGE1_ROWS, build_profile_pdf
from pdf_excel_bot.pdf_reader import PdfReadError, read_person


def test_reads_every_field(profile_pdf):
    person = read_person(profile_pdf)

    assert person.name == "Jordan Avery Testcase"
    assert person.property_id == "5550001234"
    assert person.value == 12345.67
    assert person.holder == "EXAMPLE HOLDINGS INC"
    assert person.property_type == "SC01: DIVIDENDS"
    assert person.classification == "Cash"
    assert person.owner_location == "42 Test Lane, Austin, TX 78701"  # Home Address
    assert person.address == "C O PAT EXAMPLE, 100 MAIN STREET, SUITE 200, SPRINGFIELD, IL 62701"
    assert person.phone_number == "(512) 555-0134; (512) 555-0199"
    assert person.email_address == "jordan.avery@example.com"
    assert person.age == 47
    assert person.source == "jordan.pdf"
    assert person.missing_fields() == []


def test_last_row_before_page_break_is_kept(profile_pdf):
    # pdfplumber's table extractor drops this row on the real sample.
    assert read_person(profile_pdf).classification == "Cash"


def test_value_wrapped_across_lines_is_joined(tmp_path):
    rows = [*DEFAULT_PAGE1_ROWS[:3], ("Holder", ["EXAMPLE HOLDINGS", "INTERNATIONAL LLC"]), *DEFAULT_PAGE1_ROWS[4:]]
    person = read_person(build_profile_pdf(tmp_path / "wrap.pdf", page1_rows=rows))
    assert person.holder == "EXAMPLE HOLDINGS INTERNATIONAL LLC"
    assert person.property_type == "SC01: DIVIDENDS"


def test_value_continuing_onto_next_page(tmp_path):
    # Address starts on page 1 and its second line is the first thing in page 2's table.
    page1 = [*DEFAULT_PAGE1_ROWS[:5], ("Address", ["C O PAT EXAMPLE, 100 MAIN STREET,"])]
    page2 = [("", ["SUITE 200, SPRINGFIELD, IL 62701"]), ("Classification", ["Securities"]), ("Age", ["70"])]
    person = read_person(build_profile_pdf(tmp_path / "split.pdf", page1_rows=page1, page2_rows=page2))
    assert person.classification == "Securities"
    assert person.age == 70


def test_missing_email_is_blank_and_reported(tmp_path):
    person = read_person(build_profile_pdf(tmp_path / "noemail.pdf", contacts=[("Wireless:", "(408) 223-2253")]))
    assert person.email_address == ""
    assert person.phone_number == "(408) 223-2253"
    assert person.missing_fields() == ["Email Address"]


@pytest.mark.parametrize("text,value", [
    ("$12,345.67", 12345.67), ("12345.67 USD", 12345.67), ("Approx. $1,200", 1200.0), ("$ 900", 900.0),
    ("Not disclosed", None),
])
def test_property_value_is_always_a_number(tmp_path, text, value):
    rows = [*DEFAULT_PAGE1_ROWS[:1], ("Property Value", [text]), *DEFAULT_PAGE1_ROWS[2:]]
    assert read_person(build_profile_pdf(tmp_path / "value.pdf", page1_rows=rows)).value == value


def test_unparseable_age_keeps_raw_text(tmp_path):
    page2 = [("Home Address", ["42 Test Lane, Austin, TX 78701"]), ("Age", ["Unknown"])]
    person = read_person(build_profile_pdf(tmp_path / "raw.pdf", page2_rows=page2))
    assert person.age == "Unknown"


def test_scanned_pdf_raises(blank_pdf):
    with pytest.raises(PdfReadError, match="scanned"):
        read_person(blank_pdf)


def test_missing_property_id_raises(tmp_path):
    rows = [r for r in DEFAULT_PAGE1_ROWS if r[0] != "Property ID"]
    with pytest.raises(PdfReadError, match="Property ID"):
        read_person(build_profile_pdf(tmp_path / "noid.pdf", page1_rows=rows))
