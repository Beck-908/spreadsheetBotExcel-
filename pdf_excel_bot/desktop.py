"""The desktop window: the React UI (frontend/dist) in a native window, driving the bot through Api.

The page calls Api's public methods as window.pywebview.api.<name>(...); each call runs on its
own worker thread and its return value resolves the page's promise. While a run is going,
progress goes back to the page as window.__botEvent({...}). PDFs dropped on the window go back
as window.__botDropped([paths]): only a Python drop listener gets their full paths.
"""

import json
import os
import sys
import threading
import traceback
from pathlib import Path

import openpyxl
import webview
from webview.dom import DOMEventHandler

from . import VERSION, workbooks
from .people_sheet import SheetLayoutError, count_people
from .person import Person
from .runner import run
from .settings import load_settings, save_run_log, save_settings
from .workbooks import SHEET_NAME, WorkbookError

APP_NAME = "PDF to Excel Bot"
MAX_RECENT = 6
MODES = ("auto", "excel", "file")


def ui_index() -> Path:
    """The built UI: bundled into the .exe as ui/, or frontend/dist when running from source."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "ui" / "index.html"
    return Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"


class Api:
    # pywebview only exposes public names to the page, so everything internal starts with "_".

    def __init__(self, show_result: bool = True):
        self._window = None
        self._show_result = show_result
        self._settings = load_settings()
        self._running = threading.Lock()

    def _attach(self, window) -> None:
        self._window = window

    # --- Called by the page ---------------------------------------------------------------------

    def version(self) -> str:
        return VERSION

    def pick_pdfs(self) -> list[str]:
        chosen = self._window.create_file_dialog(
            webview.FileDialog.OPEN, directory=self._pdf_folder(), allow_multiple=True,
            file_types=("PDF files (*.pdf)",),
        )
        return self._remember_pdfs(list(chosen or []))

    def pick_folder(self) -> list[str]:
        chosen = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=self._pdf_folder())
        if not chosen:
            return []
        folder = Path(chosen[0])
        return self._remember_pdfs(sorted(str(p) for p in folder.iterdir() if p.suffix.lower() == ".pdf"))

    def recent_workbooks(self) -> list[dict]:
        return [self._describe(Path(p)) for p in self._recent() if Path(p).is_file()]

    def pick_workbook(self) -> dict | None:
        recent = self._recent()
        start = str(Path(recent[0]).parent) if recent else str(Path.home() / "Documents")
        chosen = self._window.create_file_dialog(
            webview.FileDialog.OPEN, directory=start,
            file_types=("Excel workbooks (*.xlsx;*.xlsm;*.xls)", "All files (*.*)"),
        )
        if not chosen:
            return None
        path = Path(chosen[0])
        self._remember_workbook(path)
        return self._describe(path)

    def run(self, pdfs: list[str], workbook: str, mode: str) -> dict:
        """Returns {"summary": {...}} or {"error": "message for the user"}; nothing is written on error."""
        if not self._running.acquire(blocking=False):
            return {"error": "A run is already going. Wait for it to finish."}
        log: list[str] = []
        try:
            return self._run([Path(p) for p in pdfs], Path(workbook), mode, log)
        except Exception as exc:  # a bug: report it in the window rather than leave the page hanging
            log.append(traceback.format_exc())
            return {"error": f"Something unexpected went wrong ({type(exc).__name__}: {exc})."}
        finally:
            save_run_log(log)
            self._running.release()

    # --- Internals --------------------------------------------------------------------------------

    def _run(self, pdfs: list[Path], workbook: Path, mode: str, log: list[str]) -> dict:
        if mode not in MODES:
            return {"error": f"Unknown mode {mode!r}."}
        if mode == "excel" and not workbooks.excel_available():
            return {"error": "Excel isn't installed on this PC. Choose Auto or File only."}
        if not workbook.is_file():
            return {"error": f"Workbook not found: {workbook}"}
        self._remember_workbook(workbook)

        results: list[dict] = []  # one per PDF, in the order given (the same file twice gets two)
        place_of: dict[int, int] = {}  # id(Person) -> its index in results

        def on_reading(pdf: Path) -> None:
            self._emit({"type": "reading", "file": pdf.name})

        def on_read(pdf: Path, person: Person | None, error: str | None) -> None:
            if person is None:
                item = {"file": pdf.name, "outcome": "failed", "reason": error}
            else:
                place_of[id(person)] = len(results)
                item = {"file": pdf.name, "outcome": "read", **_person_fields(person)}
            results.append(item)
            self._emit({"type": "read", "result": item})

        try:
            summary = run(pdfs, workbook, log.append, prefer_excel=mode != "file", show_result=self._show_result,
                          on_reading=on_reading, on_read=on_read)
        except (WorkbookError, SheetLayoutError) as exc:
            log.append(f"✗ {exc}")
            return {"error": str(exc)}

        for i, person in enumerate(summary.added):
            results[place_of[id(person)]].update(outcome="added", row=summary.first_row + i)
        for person in summary.duplicates:
            results[place_of[id(person)]]["outcome"] = "duplicate"
        return {"summary": {
            "results": results,
            "backup": str(summary.backup) if summary.backup else None,
            "mode": summary.mode,
            "peopleRows": _count_people(workbook),
            "warnings": summary.warnings,
        }}

    def _emit(self, event: dict) -> None:
        if self._window is not None:
            self._window.evaluate_js(f"window.__botEvent && window.__botEvent({json.dumps(event)})")

    def _listen_for_drops(self) -> None:
        """Runs on every page load. The page itself only sees dropped files' names, never their paths."""
        self._window.dom.document.events.drop += DOMEventHandler(self._on_drop, prevent_default=True)

    def _on_drop(self, event: dict) -> None:
        files = (event.get("dataTransfer") or {}).get("files") or []
        paths = [f["pywebviewFullPath"] for f in files if str(f.get("pywebviewFullPath", "")).lower().endswith(".pdf")]
        if paths and self._window is not None:
            self._remember_pdfs(paths)
            self._window.evaluate_js(f"window.__botDropped && window.__botDropped({json.dumps(paths)})")

    def _describe(self, path: Path) -> dict:
        return {"path": str(path), "name": path.stem, "peopleRows": _count_people(path)}

    def _recent(self) -> list[str]:
        recent = list(self._settings.get("recent_workbooks") or [])
        last = self._settings.get("workbook")  # what the classic window remembered
        if last and last not in recent:
            recent.insert(0, last)
        return recent[:MAX_RECENT]

    def _remember_workbook(self, path: Path) -> None:
        key = os.path.normcase(str(path))
        recent = [str(path)] + [p for p in self._recent() if os.path.normcase(p) != key]
        self._settings["recent_workbooks"] = recent[:MAX_RECENT]
        self._settings["workbook"] = str(path)
        save_settings(self._settings)

    def _pdf_folder(self) -> str:
        return self._settings.get("pdf_folder") or str(Path.home() / "Downloads")

    def _remember_pdfs(self, paths: list[str]) -> list[str]:
        if paths:
            self._settings["pdf_folder"] = str(Path(paths[0]).parent)
            save_settings(self._settings)
        return paths


def _person_fields(person: Person) -> dict:
    return {
        "name": person.name,
        "propertyId": person.property_id,
        "value": person.value,
        "holder": person.holder,
        "missing": person.missing_fields(),
        "notes": person.notes,
    }


def _count_people(path: Path) -> int | None:
    """People already in the workbook's People tab, for the workbook picker. None when it can't tell."""
    if path.suffix.lower() not in (".xlsx", ".xlsm"):
        return None
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = next((ws for ws in wb.worksheets if ws.title.strip().lower() == SHEET_NAME.lower()), None)
            return count_people([list(row) for row in sheet.iter_rows(values_only=True)]) if sheet else 0
        finally:
            wb.close()
    except Exception:  # a count is a nice-to-have; never let it get in the way
        return None


def main() -> None:
    index = ui_index()
    if not index.is_file():
        raise FileNotFoundError(f"The desktop window isn't built yet (no {index}). Run `npm run build` in frontend/.")
    api = Api()
    window = webview.create_window(
        f"{APP_NAME} {VERSION}", url=str(index), js_api=api,
        width=1040, height=780, min_size=(720, 560), background_color="#0a0a0a",
    )
    api._attach(window)
    window.events.loaded += api._listen_for_drops
    webview.start(http_server=True)
