"""Start PDF to Excel Bot.

Opens the desktop window. If it can't open (for example on a PC without Microsoft's WebView2
runtime), the classic window opens instead and the reason is saved next to the settings.
`app.py --classic` opens the classic window directly.
"""

import sys
import traceback


def main() -> None:
    if "--classic" not in sys.argv:
        try:
            from pdf_excel_bot.desktop import main as desktop_main

            desktop_main()
            return
        except Exception:
            from pdf_excel_bot.settings import SETTINGS_FILE

            try:
                SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
                (SETTINGS_FILE.parent / "desktop window error.log").write_text(traceback.format_exc(), encoding="utf-8")
            except OSError:
                pass

    from pdf_excel_bot.gui import main as classic_main

    classic_main()


if __name__ == "__main__":
    main()
