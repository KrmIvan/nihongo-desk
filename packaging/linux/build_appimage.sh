#!/usr/bin/env bash
# Genera dist/NihongoDesk-<versión>-x86_64.AppImage y lo prueba con --selftest.
#
#   ./packaging/linux/build_appimage.sh
#
# Requisitos de la máquina de compilación: python3 (3.10+) con venv, curl.
# No necesita sudo: libxcb-cursor0 se descarga con «apt-get download» si falta.
# Para la máxima compatibilidad, compila en la distribución más antigua que
# quieras soportar (GitHub Actions usa Ubuntu 22.04 → glibc 2.35).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BUILD="$ROOT/build/linux"
DIST="$ROOT/dist"
mkdir -p "$BUILD" "$DIST"

PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x .venv/bin/python ]]; then PY=.venv/bin/python
  else python3 -m venv "$BUILD/venv" && PY="$BUILD/venv/bin/python"; fi
fi
echo "==> Dependencias de Python ($PY)"
"$PY" -m pip install -q -r requirements.txt "pyinstaller>=6.10"
VERSION="$("$PY" -c 'import nihongo_desk; print(nihongo_desk.__version__)')"
echo "==> Nihongo Desk $VERSION"

# --- libxcb-cursor0: Qt ≥ 6.5 lo necesita para la plataforma xcb y no viene en todas las distros
EXTRA="$BUILD/extra-libs"
mkdir -p "$EXTRA"
if ! ls "$EXTRA"/libxcb-cursor.so.0* >/dev/null 2>&1; then
  SYS_LIB="$(ldconfig -p | awk '/libxcb-cursor.so.0 /{print $NF; exit}')"
  if [[ -n "$SYS_LIB" ]]; then
    cp -L "$SYS_LIB" "$EXTRA/libxcb-cursor.so.0"
  elif command -v apt-get >/dev/null; then
    echo "==> Descargando libxcb-cursor0 (sin instalarlo)"
    (cd "$BUILD" && apt-get download libxcb-cursor0 >/dev/null && dpkg-deb -x libxcb-cursor0_*.deb deb-x \
      && cp -L deb-x/usr/lib/*/libxcb-cursor.so.0 "$EXTRA/libxcb-cursor.so.0")
  else
    echo "AVISO: no se encontró libxcb-cursor.so.0; el AppImage necesitará el paquete libxcb-cursor0" >&2
  fi
fi
export NIHONGO_EXTRA_LIBS="$EXTRA"

# --- Noto Sans JP (SIL OFL 1.1): para que el japonés se vea aunque el sistema no tenga fuentes CJK
FONTS="$BUILD/fonts"
mkdir -p "$FONTS"
if [[ ! -s "$FONTS/NotoSansJP.ttf" ]]; then
  echo "==> Descargando Noto Sans JP"
  curl -fsSL -o "$FONTS/NotoSansJP.ttf" \
    "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"
  curl -fsSL -o "$FONTS/OFL.txt" "https://github.com/google/fonts/raw/main/ofl/notosansjp/OFL.txt"
fi
export NIHONGO_FONTS="$FONTS"

echo "==> PyInstaller"
"$PY" -m PyInstaller packaging/nihongo_desk.spec --noconfirm --clean \
  --distpath "$BUILD/pyi-dist" --workpath "$BUILD/pyi-work" >"$BUILD/pyinstaller.log" 2>&1 \
  || { tail -40 "$BUILD/pyinstaller.log"; exit 1; }
cp "$FONTS/OFL.txt" "$BUILD/pyi-dist/NihongoDesk/_internal/nihongo_desk/assets/fonts/OFL.txt" 2>/dev/null || true

echo "==> AppDir"
APPDIR="$BUILD/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$BUILD/pyi-dist/NihongoDesk" "$APPDIR/usr/lib-nihongo"
cp packaging/linux/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp packaging/linux/nihongo-desk.desktop "$APPDIR/nihongo-desk.desktop"
cp nihongo_desk/assets/icons/daruma.png "$APPDIR/nihongo-desk.png"
cp nihongo_desk/assets/icons/daruma.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/nihongo-desk.png"
ln -sf nihongo-desk.png "$APPDIR/.DirIcon"

TOOL="$ROOT/build/tools/appimagetool-x86_64.AppImage"
if [[ ! -x "$TOOL" ]]; then
  echo "==> Descargando appimagetool"
  mkdir -p "$(dirname "$TOOL")"
  curl -fsSL -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "$TOOL"
fi

OUT="$DIST/NihongoDesk-$VERSION-x86_64.AppImage"
echo "==> appimagetool → $OUT"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT" >"$BUILD/appimagetool.log" 2>&1 \
  || { tail -30 "$BUILD/appimagetool.log"; exit 1; }
chmod +x "$OUT"

if [[ "${SKIP_SELFTEST:-0}" != "1" ]]; then
  echo "==> Autoprueba"
  REPORT="$BUILD/selftest.txt"
  # sin pantalla usa «offscreen»; con pantalla (o xvfb-run) prueba también la plataforma xcb real
  if [[ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then export QT_QPA_PLATFORM=offscreen; fi
  APPIMAGE_EXTRACT_AND_RUN=1 NIHONGO_NO_DESKTOP_INTEGRATION=1 "$OUT" --selftest="$REPORT" >/dev/null 2>&1 || true
  cat "$REPORT" 2>/dev/null || { echo "La autoprueba no generó informe"; exit 1; }
  grep -q "RESULTADO: OK" "$REPORT"
fi
ls -lh "$OUT"
