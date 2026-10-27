# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller común a Windows y Linux (carpeta, no un único archivo:
arranca en 1–2 s en lugar de descomprimir ~150 MB en cada inicio).

    pyinstaller packaging/nihongo_desk.spec --noconfirm

Variables de entorno opcionales (las ponen los scripts de compilación):
    NIHONGO_EXTRA_LIBS   carpeta con .so extra para Linux (p. ej. libxcb-cursor.so.0)
    NIHONGO_FONTS        carpeta con fuentes a incluir en assets/fonts (Noto Sans JP en Linux)
"""
import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
PKG = ROOT / "nihongo_desk"
IS_WIN = sys.platform == "win32"

datas = [(str(PKG / "resources"), "nihongo_desk/resources")]
# assets sin las imágenes fuente (solo sirven para regenerar las expresiones)
for path in (PKG / "assets").rglob("*"):
    if path.is_file() and "source" not in path.relative_to(PKG / "assets").parts:
        datas.append((str(path), str(path.parent.relative_to(ROOT)).replace("\\", "/")))
if os.environ.get("NIHONGO_FONTS"):
    for f in Path(os.environ["NIHONGO_FONTS"]).glob("*.[to]tf"):
        datas.append((str(f), "nihongo_desk/assets/fonts"))

binaries = []
if os.environ.get("NIHONGO_EXTRA_LIBS"):
    for so in Path(os.environ["NIHONGO_EXTRA_LIBS"]).glob("*.so*"):
        binaries.append((str(so), "."))

hidden = ["PySide6.QtMultimedia", "PySide6.QtNetwork"]
if sys.platform.startswith("linux"):
    hidden += ["pynput.keyboard._xorg", "pynput.mouse._xorg"]

# módulos de Qt que la app no usa (reducen mucho el tamaño)
excludes = ["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
            "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtQml", "PySide6.QtQuick",
            "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtCharts",
            "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
            "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtBluetooth",
            "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort",
            "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
            "PySide6.QtVirtualKeyboard", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvgWidgets",
            "PySide6.QtXml", "PySide6.QtNfc", "PySide6.QtHttpServer", "pytest", "numpy", "scipy", "PIL"]

a = Analysis(
    [str(PKG / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NihongoDesk",
    console=False,
    icon=str(PKG / "assets" / "icons" / "daruma.ico") if IS_WIN else None,
    version=str(ROOT / "build" / "version_info.txt") if IS_WIN and (ROOT / "build" / "version_info.txt").is_file() else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="NihongoDesk", upx=False)
