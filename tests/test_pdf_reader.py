from datetime import date

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


@pytest.mark.parametrize("header", [
    ["11/1/26, 9:15 PM                    Jordan Avery Testcase - Profile"],  # Chrome/Edge "Save as PDF"
    ["9:15 PM", "https://example.com/profiles/5550001234"],
    ["Page 1 of 2"],
    ["1"],
])
def test_name_skips_printed_page_headers(tmp_path, header):
    person = read_person(build_profile_pdf(tmp_path / "printed.pdf", header=header))
    assert person.name == "Jordan Avery Testcase"
    assert person.value == 12345.67


def test_name_is_the_biggest_text_above_the_profile(tmp_path):
    # Small site text above the name is not the name.
    person = read_person(build_profile_pdf(tmp_path / "x.pdf", banner=[("Search results for owner", 8)]))
    assert person.name == "Jordan Avery Testcase"


def test_name_matching_the_file_name_wins_over_a_big_banner(tmp_path):
    pdf = build_profile_pdf(tmp_path / "Jordan Avery Testcase.pdf", banner=[("PROPERTY REPORT", 18)])
    assert read_person(pdf).name == "Jordan Avery Testcase"


def test_long_name_wrapped_onto_two_lines(tmp_path):
    pdf = build_profile_pdf(tmp_path / "x.pdf", name="SANCTUM MANAGEMENT PTE\nLIMITED")
    assert read_person(pdf).name == "SANCTUM MANAGEMENT PTE LIMITED"


def test_no_name_text_falls_back_to_a_name_row_then_the_file_name(tmp_path):
    rows = [("Responsible Person", ["Pat Example"]), *DEFAULT_PAGE1_ROWS]
    person = read_person(build_profile_pdf(tmp_path / "x.pdf", name="", page1_rows=rows))
    assert person.name == "Pat Example" and person.notes

    person = read_person(build_profile_pdf(tmp_path / "Jordan_Avery Testcase (1).pdf", name=""))
    assert person.name == "Jordan Avery Testcase"
    assert "file name" in person.notes[0]


def test_wrapped_label_keeps_its_value(tmp_path):
    # A narrow label column wraps "Property Value" onto two lines; the value sits on the first.
    rows = [DEFAULT_PAGE1_ROWS[0], ("Property\nValue", ["$9,876.50"]), *DEFAULT_PAGE1_ROWS[2:]]
    person = read_person(build_profile_pdf(tmp_path / "x.pdf", page1_rows=rows))
    assert person.value == 9876.50
    assert person.property_type == "SC01: DIVIDENDS"


def test_other_labels_and_age_from_birth_date(tmp_path):
    page1 = [("Property ID", ["5550001234"]), ("Amount", ["$500.00"]), ("Holder", ["X INC"]),
             ("Type", ["Wages"]), ("Category", ["Cash"]), ("Location", ["AUSTIN, TX"]),
             ("Property Address", ["1 Main St"])]
    page2 = [("Born", ["Mar 1979"])]
    person = read_person(build_profile_pdf(tmp_path / "x.pdf", page1_rows=page1, page2_rows=page2),
                         today=date(2026, 11, 1))
    assert (person.value, person.property_type, person.classification) == (500.0, "Wages", "Cash")
    assert person.owner_location == "AUSTIN, TX" and person.address == "1 Main St"
    assert person.age == 47
    assert person.missing_fields() == []


def test_phone_numbers_without_a_contact_section(tmp_path):
    rows = [*DEFAULT_PAGE1_ROWS, ("Phone", ["(512) 555-0100"])]
    person = read_person(build_profile_pdf(tmp_path / "x.pdf", contacts=[], page1_rows=rows))
    assert person.phone_number == "(512) 555-0100"  # and not the 10-digit Property ID


def test_scanned_pdf_raises(blank_pdf):
    with pytest.raises(PdfReadError, match="scanned"):
        read_person(blank_pdf)


def test_missing_property_id_raises(tmp_path):
    rows = [r for r in DEFAULT_PAGE1_ROWS if r[0] != "Property ID"]
    with pytest.raises(PdfReadError, match="Property ID"):
        read_person(build_profile_pdf(tmp_path / "noid.pdf", page1_rows=rows))
