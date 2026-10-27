"""Punto de entrada: `python -m nihongo_desk [--toggle|--quit|--hidden]`."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .platform.single_instance import InstanceServer, send_to_running


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("Nihongo Desk")
    app.setOrganizationName("NihongoDesk")
    app.setQuitOnLastWindowClosed(False)

    command = "toggle" if "--toggle" in argv else "quit" if "--quit" in argv else "show"
    if send_to_running(command):
        return 0  # ya había una instancia abierta: se le pasa la orden
    if command == "quit":
        return 0

    from .ui import theme
    from .ui.main_window import MainWindow

    app.setFont(theme.app_font())
    win = MainWindow()
    server = InstanceServer()
    server.command.connect(win.handle_command)
    if "--hidden" not in argv:
        win.show_window()
    win.mascot.notify("app_started")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
