# Nihongo Desk 日

Ventana flotante y compacta para estudiar japonés en sesiones cortas mientras juegas o trabajas: kana, kanji y vocabulario por nivel JLPT y gramática, con repaso espaciado. Funciona sin conexión, sin cuenta y con interfaz en **español o inglés** (botón `ES/EN` en la barra de título).

![Inicio](docs/screens/01_inicio.png) ![Sesión](docs/screens/08_sesion_kanji_ficha.png) ![Gramática](docs/screens/12_sesion_gramatica_particula.png)

Incluye una **mascota anime opcional** (Momo y Kurumi) que reacciona a tus aciertos y fallos. Puede ir flotando sobre el escritorio o integrada en el panel, y su fondo, tamaño, posición y reacciones son configurables: [docs/MASCOT.md](docs/MASCOT.md).

![Mascota](docs/screens/mascota_flotante.png)

- Diseño, pantallas y arquitectura: [docs/DESIGN.md](docs/DESIGN.md)
- Mascota: [docs/MASCOT.md](docs/MASCOT.md)
- Origen y licencias del contenido japonés: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)

## Instalación

Requiere Python 3.10 o superior.

**Windows 10**

```bat
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
run.bat
```

**Linux**

```bash
sudo apt install libxcb-cursor0 fonts-noto-cjk
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

Para crear un ejecutable sin Python: `pip install pyinstaller` y luego `python tools/build_exe.py`. El resultado queda en `dist/NihongoDesk/`.

## Uso rápido

| Acción | Cómo |
|---|---|
| Mostrar / ocultar | `Ctrl + Shift + J` (configurable) o el icono de la bandeja |
| Responder | clic o teclas `1`–`6`; en preguntas escritas, `Enter` |
| Siguiente pregunta | `Enter` / `Espacio` |
| Salir de la sesión | `Esc` (se guarda y se puede continuar) |
| Escribir japonés | teclea romaji: `gakkou` → がっこう |
| Mover / tamaño compacto | arrastrar / doble clic en la barra de título |
| Acoplar a un lateral | `⇤` `⇥` |
| Mascota | arrastrar para moverla, `Ctrl` + rueda para el tamaño, clic derecho para su menú; se configura en **Mascota (友)** |

**League of Legends:** usa el modo de ventana *Sin bordes* y activa el **modo juego** (`遊`). La app no interactúa con el juego: el atajo usa la API `RegisterHotKey` de Windows y no hay ganchos de teclado.

**Wayland:** las aplicaciones no pueden registrar atajos globales. Crea un atajo del sistema que ejecute `nihongo-desk --toggle` (o `.venv/bin/python -m nihongo_desk --toggle`).

## Desarrollo

```bash
.venv/bin/pytest                                     # pruebas del núcleo
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/screenshots.py   # regenera docs/screens
.venv/bin/python tools/build_content.py              # regenera content.db (ver DATA_SOURCES.md)
.venv/bin/python tools/mascot_art.py                 # regenera las expresiones (requiere numpy, scipy y Pillow)
```

Los datos del usuario se guardan en `%APPDATA%\NihongoDesk` (Windows) o `~/.local/share/NihongoDesk` (Linux). Para usar otra carpeta, define `NIHONGO_DESK_HOME`.
