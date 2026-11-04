"""Per-user settings (last folders and workbooks), kept in %APPDATA%\\PdfExcelBot."""

import json
import os
from pathlib import Path

SETTINGS_DIR = Path(os.environ.get("APPDATA", Path.home())) / "PdfExcelBot"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass  # remembering paths is a convenience only


def save_run_log(lines: list[str]) -> Path | None:
    """Keep the last run's log next to the settings, for troubleshooting ("send me the log")."""
    path = SETTINGS_FILE.parent / "last run.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    except OSError:
        return None
