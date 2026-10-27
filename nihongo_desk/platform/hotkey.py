"""Atajo de teclado global para mostrar/ocultar la ventana.

- Windows: RegisterHotKey (API oficial de Win32). No instala ganchos de
  teclado ni lee pulsaciones de otras aplicaciones: Windows solo avisa cuando
  se pulsa exactamente esa combinación. Detecta conflictos (combinación ocupada).
- Linux X11: pynput (XRecord). No puede detectar conflictos.
- Linux Wayland: los atajos globales no están permitidos a las aplicaciones;
  se documenta usar un atajo del sistema que ejecute `nihongo-desk --toggle`.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal


def parse(seq: str) -> tuple[set[str], str]:
    """'Ctrl+Shift+J' -> ({'ctrl','shift'}, 'j')."""
    parts = [p.strip() for p in seq.split("+") if p.strip()]
    mods = {p.lower() for p in parts[:-1]}
    mods = {"meta" if m in ("meta", "win", "super") else m for m in mods}
    return mods, parts[-1].lower() if parts else ""


class HotkeyManager(QObject):
    activated = Signal()

    def __init__(self):
        super().__init__()
        self.backend = None
        self.status = "off"   # ok | fail | wayland | unsupported | off
        self.sequence = ""

    def register(self, seq: str) -> bool:
        self.unregister()
        self.sequence = seq
        try:
            if sys.platform == "win32":
                self.backend = _WindowsHotkey(seq, self.activated.emit)
            elif os.environ.get("XDG_SESSION_TYPE") == "wayland" and not os.environ.get("NIHONGO_FORCE_X11_HOTKEY"):
                self.status = "wayland"
                return False
            else:
                self.backend = _PynputHotkey(seq, self.activated.emit)
            self.status = "ok"
            return True
        except Exception:  # combinación ocupada, falta de pynput, etc.
            self.backend = None
            self.status = "fail"
            return False

    def unregister(self) -> None:
        if self.backend:
            self.backend.close()
        self.backend = None


# ---------------------------------------------------------------- Windows
class _WindowsHotkey(QAbstractNativeEventFilter):
    HOTKEY_ID = 0x4E44  # "ND"
    WM_HOTKEY = 0x0312
    MODS = {"alt": 0x1, "ctrl": 0x2, "shift": 0x4, "meta": 0x8}
    NAMED = {"space": 0x20, "tab": 0x09, "home": 0x24, "end": 0x23, "ins": 0x2D, "insert": 0x2D, "del": 0x2E,
             "pgup": 0x21, "pgdown": 0x22, "`": 0xC0, "´": 0xC0, "º": 0xC0}

    def __init__(self, seq: str, callback):
        super().__init__()
        import ctypes
        from ctypes import wintypes
        self._ctypes, self._wintypes = ctypes, wintypes
        self.callback = callback
        mods, key = parse(seq)
        if key.startswith("f") and key[1:].isdigit():
            vk = 0x70 + int(key[1:]) - 1
        elif len(key) == 1 and key.isalnum():
            vk = ord(key.upper())
        elif key in self.NAMED:
            vk = self.NAMED[key]
        else:
            raise ValueError(f"tecla no soportada: {key}")
        flags = 0x4000  # MOD_NOREPEAT
        for m in mods:
            flags |= self.MODS[m]
        if not ctypes.windll.user32.RegisterHotKey(None, self.HOTKEY_ID, flags, vk):
            raise OSError("RegisterHotKey falló (combinación en uso)")
        QCoreApplication.instance().installNativeEventFilter(self)

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = self._wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                self.callback()
                return True, 0
        return False, 0

    def close(self):
        self._ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
        QCoreApplication.instance().removeNativeEventFilter(self)


# ---------------------------------------------------------------- Linux X11
class _PynputHotkey:
    def __init__(self, seq: str, callback):
        from pynput import keyboard
        mods, key = parse(seq)
        names = {"ctrl": "<ctrl>", "shift": "<shift>", "alt": "<alt>", "meta": "<cmd>"}
        if len(key) > 1:
            key = f"<{key}>"
        combo = "+".join([names[m] for m in sorted(mods)] + [key])
        # la señal Qt se emite desde el hilo de pynput: Qt la entrega en el hilo principal
        self.listener = keyboard.GlobalHotKeys({combo: callback})
        self.listener.daemon = True
        self.listener.start()

    def close(self):
        self.listener.stop()
