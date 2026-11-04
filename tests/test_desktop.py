import json

import openpyxl
import pytest
import win32con
import win32file

from conftest import build_profile_pdf
from pdf_excel_bot import settings
from pdf_excel_bot.desktop import Api
from pdf_excel_bot.person import COLUMNS


class FakeWindow:
    """Stands in for the pywebview window: records what Python pushes to the page."""

    def __init__(self):
        self.scripts = []

    def evaluate_js(self, script):
        self.scripts.append(script)

    def calls(self, function):
        """Arguments of each window.<function>(...) call pushed to the page."""
        start = f"{function}("
        return [json.loads(s[s.rindex(start) + len(start):-1]) for s in self.scripts if start in s]

    @property
    def events(self):
        return self.calls("__botEvent")


@pytest.fixture(autouse=True)
def own_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "appdata" / "settings.json")


@pytest.fixture
def book(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "People"
    wb.active.append(COLUMNS)
    wb.active.append(["Already Here", 999])
    path = tmp_path / "Company Records.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def api():
    api = Api(show_result=False)
    api._attach(FakeWindow())
    return api


def test_run_streams_progress_then_final_outcomes(tmp_path, api, book, profile_pdf, blank_pdf):
    copy = build_profile_pdf(tmp_path / "jordan again.pdf")

    reply = api.run([str(profile_pdf), str(blank_pdf), str(copy)], str(book), "auto")

    events = api._window.events
    assert [e["type"] for e in events] == ["reading", "read"] * 3
    assert [e["file"] for e in events if e["type"] == "reading"] == ["jordan.pdf", "scanned.pdf", "jordan again.pdf"]
    first = events[1]["result"]
    assert first["outcome"] == "read" and first["name"] == "Jordan Avery Testcase" and first["value"] == 12345.67

    summary = reply["summary"]
    assert [(r["file"], r["outcome"]) for r in summary["results"]] == [
        ("jordan.pdf", "added"), ("scanned.pdf", "failed"), ("jordan again.pdf", "duplicate"),
    ]
    assert summary["results"][0]["row"] == 3  # header, Already Here, then Jordan
    assert "scanned image" in summary["results"][1]["reason"]
    assert summary["mode"] == "file" and summary["peopleRows"] == 2
    assert summary["backup"].endswith(".xlsx") and "backups" in summary["backup"]
    assert (settings.SETTINGS_FILE.parent / "last run.log").read_text(encoding="utf-8").startswith("PDF to Excel Bot")


def test_same_pdf_twice_is_added_once_then_reported_as_already_there(api, book, profile_pdf):
    reply = api.run([str(profile_pdf), str(profile_pdf)], str(book), "file")
    assert [(r["outcome"], r.get("row")) for r in reply["summary"]["results"]] == [("added", 3), ("duplicate", None)]


def test_workbook_is_remembered_with_its_people_count(api, book, profile_pdf):
    assert api.recent_workbooks() == []
    api.run([str(profile_pdf)], str(book), "file")

    assert api.recent_workbooks() == [{"path": str(book), "name": "Company Records", "peopleRows": 2}]
    assert Api().recent_workbooks()[0]["path"] == str(book)  # survives a restart


def test_classic_window_setting_is_picked_up(book):
    settings.save_settings({"workbook": str(book)})
    assert [w["name"] for w in Api().recent_workbooks()] == ["Company Records"]


@pytest.mark.parametrize("mode,workbook,message", [
    ("excel", None, "Excel isn't installed"),
    ("auto", "missing.xlsx", "Workbook not found"),
    ("fast", None, "Unknown mode"),
])
def test_problems_come_back_as_messages(tmp_path, api, book, profile_pdf, mode, workbook, message):
    target = tmp_path / workbook if workbook else book
    reply = api.run([str(profile_pdf)], str(target), mode)
    assert message in reply["error"]
    assert not (tmp_path / "backups").exists()


def test_locked_workbook_message(api, book, profile_pdf):
    handle = win32file.CreateFile(str(book), win32con.GENERIC_READ, win32con.FILE_SHARE_READ, None,
                                  win32con.OPEN_EXISTING, 0, None)
    try:
        reply = api.run([str(profile_pdf)], str(book), "file")
    finally:
        handle.Close()
    assert "close it" in reply["error"]


def test_dropped_pdfs_reach_the_page_with_full_paths(api):
    # The shape pywebview hands a Python drop listener: full paths only it can see.
    api._on_drop({"dataTransfer": {"files": [
        {"name": "Jordan Avery.pdf", "pywebviewFullPath": r"C:\Profiles\Jordan Avery.pdf"},
        {"name": "notes.txt", "pywebviewFullPath": r"C:\Profiles\notes.txt"},
        {"name": "dragged from a browser.pdf"},  # no path: nothing to add
    ]}})
    assert api._window.calls("__botDropped") == [[r"C:\Profiles\Jordan Avery.pdf"]]
    assert settings.load_settings()["pdf_folder"] == r"C:\Profiles"

    api._on_drop({"dataTransfer": {"files": []}})
    assert len(api._window.calls("__botDropped")) == 1  # nothing pushed for an empty drop


def test_one_run_at_a_time(api, book, profile_pdf):
    api._running.acquire()
    try:
        assert "already going" in api.run([str(profile_pdf)], str(book), "file")["error"]
    finally:
        api._running.release()
