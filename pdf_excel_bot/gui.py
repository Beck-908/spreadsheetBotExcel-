"""The bot's window: pick PDFs and a workbook, press Run, watch the log."""

import json
import os
import queue
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import VERSION
from .people_sheet import SheetLayoutError
from .runner import RunSummary, run
from .workbooks import WorkbookError

APP_NAME = "PDF to Excel Bot"
SETTINGS_FILE = Path(os.environ.get("APPDATA", Path.home())) / "PdfExcelBot" / "settings.json"


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


class BotWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings = load_settings()
        self.pdfs: list[Path] = []
        self.messages: queue.Queue = queue.Queue()  # worker thread -> UI thread
        self.workbook = tk.StringVar(value=self.settings.get("workbook", ""))
        self.status = tk.StringVar(value="Add PDFs, choose the workbook, then press Run.")

        root.title(f"{APP_NAME} {VERSION}")
        root.minsize(680, 560)
        frame = ttk.Frame(root, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        heading = ("Segoe UI", 10, "bold")

        ttk.Label(frame, text="1.  PDFs to add (one person per PDF)", font=heading).grid(row=0, column=0, sticky="w")
        pdf_area = ttk.Frame(frame)
        pdf_area.grid(row=1, column=0, sticky="nsew", pady=(4, 12))
        pdf_area.columnconfigure(0, weight=1)
        pdf_area.rowconfigure(0, weight=1)
        self.pdf_list = tk.Listbox(pdf_area, height=7, selectmode="extended", activestyle="none")
        self.pdf_list.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(pdf_area, orient="vertical", command=self.pdf_list.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.pdf_list.configure(yscrollcommand=scroll.set)
        pdf_buttons = ttk.Frame(pdf_area)
        pdf_buttons.grid(row=0, column=2, sticky="n", padx=(8, 0))
        for text, command in (("Add PDFs…", self.add_pdfs), ("Add folder…", self.add_folder),
                              ("Remove", self.remove_selected), ("Clear", self.clear_pdfs)):
            ttk.Button(pdf_buttons, text=text, command=command, width=14).pack(fill="x", pady=2)

        ttk.Label(frame, text="2.  Excel workbook (rows go into its People tab)", font=heading).grid(row=2, column=0, sticky="w")
        book_area = ttk.Frame(frame)
        book_area.grid(row=3, column=0, sticky="ew", pady=(4, 12))
        book_area.columnconfigure(0, weight=1)
        ttk.Entry(book_area, textvariable=self.workbook).grid(row=0, column=0, sticky="ew")
        ttk.Button(book_area, text="Browse…", command=self.choose_workbook, width=14).grid(row=0, column=1, padx=(8, 0))

        self.run_button = ttk.Button(frame, text="▶  Run", command=self.start)
        self.run_button.grid(row=4, column=0, sticky="ew", ipady=6)

        ttk.Label(frame, text="Log", font=heading).grid(row=5, column=0, sticky="w", pady=(12, 0))
        log_area = ttk.Frame(frame)
        log_area.grid(row=6, column=0, sticky="nsew", pady=(4, 6))
        log_area.columnconfigure(0, weight=1)
        log_area.rowconfigure(0, weight=1)
        frame.rowconfigure(6, weight=1)
        self.log_box = tk.Text(log_area, height=10, wrap="word", state="disabled", font=("Consolas", 9))
        self.log_box.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_area, orient="vertical", command=self.log_box.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_box.configure(yscrollcommand=log_scroll.set)

        ttk.Label(frame, textvariable=self.status, foreground="#555").grid(row=7, column=0, sticky="w")
        root.after(100, self._drain_messages)

    # --- PDF list -------------------------------------------------------------

    def _add(self, paths: list[Path]) -> None:
        for path in paths:
            if path not in self.pdfs:
                self.pdfs.append(path)
                self.pdf_list.insert("end", f"{path.name}    ({path.parent})")
        if paths:
            self.settings["pdf_folder"] = str(paths[0].parent)
        self.status.set(f"{len(self.pdfs)} PDF(s) ready.")

    def add_pdfs(self) -> None:
        chosen = filedialog.askopenfilenames(
            title="Choose PDFs", filetypes=[("PDF files", "*.pdf")],
            initialdir=self.settings.get("pdf_folder") or Path.home() / "Downloads",
        )
        self._add([Path(p) for p in chosen])

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Choose a folder of PDFs",
            initialdir=self.settings.get("pdf_folder") or Path.home() / "Downloads",
        )
        if folder:
            found = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() == ".pdf")
            if not found:
                messagebox.showinfo(APP_NAME, "That folder has no PDF files.")
            self._add(found)

    def remove_selected(self) -> None:
        for index in reversed(self.pdf_list.curselection()):
            self.pdf_list.delete(index)
            del self.pdfs[index]
        self.status.set(f"{len(self.pdfs)} PDF(s) ready.")

    def clear_pdfs(self) -> None:
        self.pdf_list.delete(0, "end")
        self.pdfs.clear()
        self.status.set("PDF list cleared.")

    # --- Workbook -------------------------------------------------------------

    def choose_workbook(self) -> None:
        current = Path(self.workbook.get()) if self.workbook.get() else None
        chosen = filedialog.askopenfilename(
            title="Choose the Excel workbook",
            filetypes=[("Excel workbooks", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")],
            initialdir=current.parent if current else Path.home() / "Documents",
        )
        if chosen:
            self.workbook.set(str(Path(chosen)))

    # --- Running --------------------------------------------------------------

    def start(self) -> None:
        if not self.pdfs:
            messagebox.showwarning(APP_NAME, "Add at least one PDF first.")
            return
        workbook = Path(self.workbook.get().strip().strip('"'))
        if not self.workbook.get().strip() or not workbook.is_file():
            messagebox.showwarning(APP_NAME, "Choose the Excel workbook first.")
            return
        self.settings["workbook"] = str(workbook)
        save_settings(self.settings)

        self._set_log("")
        self._busy(True)
        threading.Thread(target=self._work, args=(list(self.pdfs), workbook), daemon=True).start()

    def _work(self, pdfs: list[Path], workbook: Path) -> None:
        try:
            summary = run(pdfs, workbook, lambda message: self.messages.put(("log", message)))
            self.messages.put(("done", summary))
        except (WorkbookError, SheetLayoutError) as exc:
            self.messages.put(("error", str(exc)))
        except Exception:
            self.messages.put(("error", "Something unexpected went wrong:\n\n" + traceback.format_exc()))

    def _drain_messages(self) -> None:
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "done":
                    self._finish(payload)
                else:
                    self._append_log(f"✗ {payload}")
                    self._busy(False)
                    self.status.set("Stopped. Nothing was written. See the log.")
                    messagebox.showerror(APP_NAME, payload)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_messages)

    def _finish(self, summary: RunSummary) -> None:
        self._busy(False)
        # Keep only the PDFs that failed, so they're easy to look at and retry.
        failed = {name for name, _ in summary.failed}
        keep = [p for p in self.pdfs if p.name in failed]
        self.clear_pdfs()
        self._add(keep)
        self.status.set(
            f"Done: {len(summary.added)} added, {len(summary.duplicates)} already there, {len(summary.failed)} failed."
        )
        if summary.failed:
            messagebox.showwarning(
                APP_NAME,
                f"{len(summary.failed)} PDF(s) couldn't be read and are still in the list. The log says why.",
            )

    def _busy(self, busy: bool) -> None:
        self.run_button.configure(state="disabled" if busy else "normal", text="Working…" if busy else "▶  Run")
        if busy:
            self.status.set("Working…")

    def _set_log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.insert("end", text)
        self.log_box.configure(state="disabled")

    def _append_log(self, line: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")


def main() -> None:
    try:  # crisp text on high-DPI screens
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    BotWindow(root)
    root.mainloop()
