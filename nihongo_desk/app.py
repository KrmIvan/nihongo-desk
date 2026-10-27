"""Punto de entrada: `python -m nihongo_desk [--toggle|--quit|--hidden|--selftest[=informe.txt]|--version]`."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .core.paths import user_data_dir
from .platform.single_instance import InstanceServer, send_to_running


def _log_error(text: str) -> str:
    """Guarda el error en la carpeta de datos (los .exe sin consola no tienen dónde mostrarlo)."""
    try:
        path = user_data_dir() / "error.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} · Nihongo Desk {__version__}\n{text}")
        return str(path)
    except OSError:
        return ""


def _excepthook(kind, value, tb):
    text = "".join(traceback.format_exception(kind, value, tb))
    _log_error(text)
    sys.__stderr__ and sys.__stderr__.write(text)


def _fatal(text: str) -> int:
    path = _log_error(text)
    if sys.__stderr__:
        sys.__stderr__.write(text)
    if QApplication.instance():
        QMessageBox.critical(None, "Nihongo Desk",
                             "No se pudo iniciar Nihongo Desk / Nihongo Desk could not start.\n\n"
                             f"{text.strip().splitlines()[-1]}\n\n{path}")
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    if "--version" in argv:
        print(__version__)
        return 0
    selftest = next((a for a in argv if a.startswith("--selftest")), None)
    sys.excepthook = _excepthook
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("Nihongo Desk")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("NihongoDesk")
    app.setQuitOnLastWindowClosed(False)

    if selftest:
        from .selftest import run
        return run(app, selftest.partition("=")[2] or None)

    command = "toggle" if "--toggle" in argv else "quit" if "--quit" in argv else "show"
    if send_to_running(command):
        return 0  # ya había una instancia abierta: se le pasa la orden
    if command == "quit":
        return 0

    try:
        from .ui import theme
        from .ui.main_window import MainWindow

        theme.load_bundled_fonts()
        app.setFont(theme.app_font())
        win = MainWindow()
        server = InstanceServer()
        server.command.connect(win.handle_command)
        if "--hidden" not in argv:
            win.show_window()
        win.mascot.notify("app_started")
    except Exception:  # noqa: BLE001 — cualquier fallo de arranque se registra y se muestra
        return _fatal(traceback.format_exc())
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
