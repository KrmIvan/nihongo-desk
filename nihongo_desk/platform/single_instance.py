"""Instancia única + orden `--toggle` (útil en Wayland o para atajos del sistema)."""
from __future__ import annotations

import getpass

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SERVER_NAME = f"NihongoDesk-{getpass.getuser()}"


def send_to_running(command: str, timeout_ms: int = 400) -> bool:
    """Envía una orden a una instancia abierta. True si la había."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write(command.encode())
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    return True


class InstanceServer(QObject):
    command = Signal(str)

    def __init__(self):
        super().__init__()
        QLocalServer.removeServer(SERVER_NAME)  # limpia un socket huérfano tras un cierre brusco
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_conn)
        self.server.listen(SERVER_NAME)

    def _on_conn(self):
        sock = self.server.nextPendingConnection()
        sock.readyRead.connect(lambda: self.command.emit(bytes(sock.readAll()).decode(errors="ignore").strip()))
