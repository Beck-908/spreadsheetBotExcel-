"""The record the bot carries from one PDF into one spreadsheet row."""

from dataclasses import dataclass, field

# Column headers, in the order the bot writes them into an empty People tab.
COLUMNS = (
    "Responsible Person",
    "Property ID",
    "Value",
    "Holder",
    "Property Type",
    "Classification",
    "Owner Location",
    "Address",
    "Phone Number",
    "Email Address",
    "Age",
)


@dataclass
class Person:
    name: str = ""  # the name at the top of the PDF; goes in Responsible Person
    property_id: str = ""  # as printed; written to Excel as a number when it is all digits
    value: float | None = None  # the property value as a number; blank when the PDF has no figure
    holder: str = ""
    property_type: str = ""
    classification: str = ""
    owner_location: str = ""  # the PDF's Home Address
    address: str = ""  # the PDF's Address
    phone_number: str = ""
    email_address: str = ""
    age: int | str | None = None
    source: str = ""  # PDF file name, for log messages
    notes: list[str] = field(default_factory=list)  # where a field came from when it wasn't the usual place

    def as_row(self) -> dict[str, object]:
        return {
            "Responsible Person": self.name,
            "Property ID": self.property_id,
            "Value": self.value,
            "Holder": self.holder,
            "Property Type": self.property_type,
            "Classification": self.classification,
            "Owner Location": self.owner_location,
            "Address": self.address,
            "Phone Number": self.phone_number,
            "Email Address": self.email_address,
            "Age": self.age,
        }

    def missing_fields(self) -> list[str]:
        return [column for column, value in self.as_row().items() if value is None or value == ""]
