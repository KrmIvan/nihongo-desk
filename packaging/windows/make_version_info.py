"""Escribe build/version_info.txt (propiedades del .exe en Windows) con la versión de la app."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from nihongo_desk import __version__  # noqa: E402

nums = tuple(int(x) for x in (__version__.split(".") + ["0", "0", "0"])[:4])
text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Nihongo Desk'),
      StringStruct('FileDescription', 'Nihongo Desk'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'NihongoDesk'),
      StringStruct('OriginalFilename', 'NihongoDesk.exe'),
      StringStruct('ProductName', 'Nihongo Desk'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"""
out = ROOT / "build" / "version_info.txt"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(text, encoding="utf-8")
print(__version__)
