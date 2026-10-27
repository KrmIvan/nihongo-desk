"""Autoprueba del programa empaquetado: `NihongoDesk --selftest[=informe.txt]`.

Comprueba que el paquete trae todo (contenido, mascota, iconos, fuentes, Qt)
y recorre la interfaz sin interacción. Escribe un informe y devuelve 0 si todo
está bien. La usan los scripts de compilación y GitHub Actions.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path


def run(app, report: str | None) -> int:
    lines: list[str] = []
    ok = True

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal ok
        ok &= bool(cond)
        lines.append(f"[{'OK' if cond else 'FALLO'}] {name}{(' · ' + detail) if detail else ''}")

    # datos del usuario en una carpeta temporal: nunca toca el progreso real
    os.environ["NIHONGO_DESK_HOME"] = tempfile.mkdtemp(prefix="nihongo-selftest-")
    try:
        from . import __version__
        from .core.paths import assets_dir, resources_dir, user_data_dir
        from .mascot.character import EXPRESSIONS, all_characters
        from .ui import theme
        from .ui.main_window import MainWindow, app_icon

        lines.append(f"Nihongo Desk {__version__} · Python {sys.version.split()[0]} · {sys.platform}"
                     f" · {'empaquetado' if getattr(sys, 'frozen', False) else 'código fuente'}")
        check("content.db", (resources_dir() / "content.db").is_file(), str(resources_dir()))
        check("icono daruma", (assets_dir() / "icons" / "daruma.png").is_file() and not app_icon().isNull())
        chars = all_characters(reload=True)
        check("personajes", len(chars) >= 1, ", ".join(chars))
        for c in chars.values():
            missing = [e for e in EXPRESSIONS if e not in c.available()]
            check(f"expresiones de {c.id}", not missing and not c.frame("happy", "blink", 120).isNull(),
                  f"faltan {missing}" if missing else f"{len(c.files)} imágenes")
        theme.load_bundled_fonts()
        check("fuente japonesa", bool(theme.fonts()["jp"]), theme.fonts()["jp"] or "ninguna")

        win = MainWindow()
        win.db.set("sounds", False)
        check("primera ejecución crea user.db", (user_data_dir() / "user.db").is_file())
        check("contenido", win.repo.kanji_count() and win.repo.vocab_count(),
              f"kanji {sum(win.repo.kanji_count().values())}, vocab {sum(win.repo.vocab_count().values())}")
        win.show_window()
        win.mascot.notify("app_started")
        for key in ("kana", "kanji", "vocab", "grammar", "stats", "settings", "mascot"):
            win.open_module(key)
        win.start_module_session("kana", {"scripts": ["h"], "groups": ["a"], "exercise": "choice",
                                          "difficulty": "easy"}, 3, "kana")
        scr = win.stack.currentWidget()
        q = getattr(scr, "q", None)
        if q is not None and q.kind == "choice":
            scr.choose(q.answer_index)
        check("sesión de estudio", win.db.totals()["answers"] >= 1)
        check("mascota flotante", win.mascot.window is not None and win.mascot.window.isVisible())
        app.processEvents()
        win.quit()
    except Exception:  # noqa: BLE001
        ok = False
        lines.append("[FALLO] excepción:\n" + traceback.format_exc())

    lines.append("RESULTADO: " + ("OK" if ok else "FALLO"))
    text = "\n".join(lines) + "\n"
    if report:
        Path(report).write_text(text, encoding="utf-8")
    if sys.stdout:
        sys.stdout.write(text)
    return 0 if ok else 1
