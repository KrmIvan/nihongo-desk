"""Empaqueta Nihongo Desk con PyInstaller (ejecutar en el sistema destino).

Windows:  .venv\\Scripts\\python tools\\build_exe.py   ->  dist\\NihongoDesk\\NihongoDesk.exe
Linux:    .venv/bin/python tools/build_exe.py          ->  dist/NihongoDesk/NihongoDesk
"""
import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
sep = ";" if sys.platform == "win32" else ":"
PyInstaller.__main__.run([
    str(ROOT / "nihongo_desk" / "__main__.py"),
    "--name", "NihongoDesk",
    "--noconfirm", "--windowed",
    "--add-data", f"{ROOT / 'nihongo_desk' / 'resources'}{sep}nihongo_desk/resources",
    "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"),
    *(["--hidden-import", "pynput.keyboard._xorg"] if sys.platform.startswith("linux") else []),
])
print("Listo:", ROOT / "dist" / "NihongoDesk", os.linesep)
