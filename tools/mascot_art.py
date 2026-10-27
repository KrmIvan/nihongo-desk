"""Prepara las ilustraciones de las mascotas a partir de su imagen original.

Para cada personaje en ``nihongo_desk/assets/characters/<id>/source/original.*``:

1. borra el texto «hola» y las marcas de saludo dibujadas sobre el fondo;
2. crea la postura ``idle`` (brazos abajo) reflejando el brazo bajado sobre el
   lado que saluda; la postura ``wave`` es la original;
3. quita el fondo plano (relleno por inundación + alfa suave en los bordes);
4. escala ×2 y retoca ojos y boca para cada expresión, más su fotograma de
   parpadeo y de habla; guarda cada fotograma en WebP.

Son retoques de la ilustración original, no dibujos nuevos: si en el futuro
hay ilustraciones hechas a mano, basta con sustituir las imágenes de
``expressions/`` (el manifiesto no cambia).

Requiere numpy, scipy y Pillow (solo para desarrollo):
    python tools/mascot_art.py [--sheet salida.png]
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
CHARS = ROOT / "nihongo_desk" / "assets" / "characters"

SS = 4      # superresolución de trabajo para los retoques (antialias)
OUT = 2     # escala final respecto a la original

# Medidas en píxeles de la imagen original (comprobadas a mano con rejilla).
PARAMS = {
    "momo": dict(
        cx=152.5, seam=113, y0=100, y1=290, erase=[(0, 0, 86, 112), (28, 104, 51, 138)],
        eyes=[(119.5, 71, 134.5, 87.5), (153, 68.5, 170, 84)],
        mouth=(139, 93.5, 151, 97.5), skin_at=(145, 84),
        ink=(92, 52, 58), mouth_ink=(150, 72, 82), blush=(246, 150, 160),
    ),
    "kurumi": dict(
        cx=147, seam=110, y0=104, y1=290, erase=[(0, 0, 86, 104), (0, 104, 47, 130)],
        eyes=[(112, 67, 128.5, 82.5), (146.5, 63.5, 164, 79)],
        mouth=(133.5, 88.5, 146.5, 93), skin_at=(139, 81),
        ink=(84, 50, 44), mouth_ink=(146, 70, 70), blush=(242, 150, 150),
    ),
}

# expresión -> (postura, ojos, boca, extras)
EXPRESSIONS = {
    "neutral":     ("idle", "open", "orig", []),
    "happy":       ("idle", "open", "smile_open", ["blush"]),
    "very_happy":  ("idle", "happy", "grin", ["blush", "sparkle_cheeks"]),
    "focused":     ("idle", "open", "flat", []),
    "thinking":    ("idle", "half", "side", []),
    "surprised":   ("idle", "wide", "o", []),
    "confused":    ("idle", "open", "wavy", ["sweat"]),
    "sad":         ("idle", "half_sad", "frown", ["tear_gloss"]),
    "shy":         ("idle", "open", "small", ["blush_strong"]),
    "encouraging": ("wave", "sparkle", "grin", ["blush"]),
    "celebrating": ("wave", "happy", "grin", ["blush", "sparkle_cheeks"]),
    "sleeping":    ("idle", "closed", "sleep", ["blush"]),
    "greeting":    ("wave", "open", "orig", []),
}
BLINK_EYES = {"open", "wide", "half", "half_sad", "sparkle"}
TALK_MOUTH = {"neutral": "talk", "happy": "talk_wide", "greeting": "talk", "encouraging": "talk_wide"}


# ------------------------------------------------------------------ postura y fondo
def load_rgb(cid: str) -> np.ndarray:
    src = next((CHARS / cid / "source").glob("original.*"))
    return np.asarray(Image.open(src).convert("RGB")).astype(float)


def bg_color(a: np.ndarray) -> np.ndarray:
    return np.median(a[:5].reshape(-1, 3), 0)


def clean(a: np.ndarray, p: dict) -> np.ndarray:
    a = a.copy()
    bg = bg_color(a)
    for x0, y0, x1, y1 in p["erase"]:
        a[y0:y1, x0:x1] = bg
    return a


def idle_pose(a: np.ndarray, p: dict) -> np.ndarray:
    """Refleja el lado del brazo bajado sobre el del brazo que saluda."""
    h, w, _ = a.shape
    ys, xs = np.mgrid[0:h, 0:w]
    src_x = np.clip(np.round(2 * p["cx"] - xs).astype(int), 0, w - 1)
    mir = a[ys, src_x]
    wx = np.clip((p["seam"] - xs) / 3.0 + 0.5, 0, 1)
    wy = np.clip((ys - p["y0"] + 8) / 8.0, 0, 1) * np.clip((p["y1"] - ys) / 8.0, 0, 1)
    wgt = (wx * wy)[..., None]
    out = a * (1 - wgt) + mir * wgt
    # en el bajo de la falda, conserva el original donde el reflejo es fondo
    bg = bg_color(a)
    mir_bg = np.abs(mir - bg).sum(2) < 20
    org_fg = np.abs(a - bg).sum(2) > 40
    keep = mir_bg & org_fg & (ys > 240) & (xs > p["seam"] - 30)
    out[keep] = a[keep]
    return out


def cutout(a: np.ndarray, lo: float = 22, hi: float = 110) -> Image.Image:
    """Quita un fondo plano: inundación desde el borde + bolsas grandes + alfa suave."""
    bg = bg_color(a)
    dist = np.abs(a - bg).sum(2)
    near = dist < lo
    lab, n = ndimage.label(near)
    sizes = ndimage.sum(near, lab, range(1, n + 1))
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    is_bg = np.zeros_like(near)
    for i, s in enumerate(sizes, 1):
        if i in border or s >= 8:
            is_bg |= lab == i
    ring = ndimage.binary_dilation(is_bg, iterations=3) & ~is_bg
    alpha = np.ones(dist.shape)
    alpha[is_bg] = 0
    soft = np.clip((dist - lo) / (hi - lo), 0, 1) ** 1.4
    alpha[ring] = soft[ring]
    # el borde semitransparente toma el color del píxel opaco más cercano (el
    # contorno): así no queda el halo claro del fondo ni del «ringing» del JPEG
    _, (iy, ix) = ndimage.distance_transform_edt(alpha < 0.999, return_indices=True)
    rgb = a.copy()
    rgb[ring] = a[iy[ring], ix[ring]]
    rgba = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def upscale(im: Image.Image, k: int) -> Image.Image:
    """Escala RGBA con alfa premultiplicado para no crear halos."""
    pre = im.convert("RGBa")
    big = pre.resize((im.width * k, im.height * k), Image.LANCZOS)
    return big.convert("RGBA")


# ------------------------------------------------------------------ retoques de cara
class Face:
    """Retoca la cara sobre un recorte ``im`` cuyo origen es ``origin`` (px originales)."""

    def __init__(self, im: Image.Image, p: dict, origin: tuple[float, float]):
        self.im = im
        self.p = p
        self.d = ImageDraw.Draw(im, "RGBA")
        self.k = SS * OUT
        self.ox, self.oy = origin
        self.src = np.asarray(im.convert("RGB")).astype(float)
        sx, sy = p["skin_at"]
        x, y = self.s(sx, sy)
        patch = self.src[int(y) - 4:int(y) + 4, int(x) - 4:int(x) + 4]
        self.skin_ref = patch.reshape(-1, 3).mean(0)

    def s(self, *v):  # coordenadas originales -> lienzo de trabajo
        return [(x - (self.ox if i % 2 == 0 else self.oy)) * self.k for i, x in enumerate(v)]

    def skin_around(self, box, grow):
        """Color de piel local: mediana de un anillo alrededor de la zona."""
        x0, y0, x1, y1 = self.s(box[0] - grow - 3, box[1] - grow - 3, box[2] + grow + 3, box[3] + grow + 3)
        ix0, iy0, ix1, iy1 = self.s(box[0] - grow, box[1] - grow, box[2] + grow, box[3] + grow)
        region = self.src[int(y0):int(y1), int(x0):int(x1)]
        yy, xx = np.mgrid[int(y0):int(y1), int(x0):int(x1)]
        ring = ~((xx >= ix0) & (xx < ix1) & (yy >= iy0) & (yy < iy1))
        px = region[ring]
        ok = np.abs(px - self.skin_ref).sum(1) < 36
        if ok.sum() < 20:
            return tuple(int(v) for v in self.skin_ref)
        return tuple(int(v) for v in np.median(px[ok], 0))

    # -- utilidades
    def cover(self, box, grow=1.0, shrink_top=0.0):
        x0, y0, x1, y1 = box
        skin = self.skin_around(box, grow)
        m = Image.new("L", self.im.size, 0)
        ImageDraw.Draw(m).ellipse(self.s(x0 - grow, y0 - grow + shrink_top, x1 + grow, y1 + grow), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(self.k * 0.6))
        self.im.paste(Image.new("RGBA", self.im.size, skin + (255,)), (0, 0), m)

    def line(self, pts, width, color=None):
        color = color or self.p["ink"]
        pts = [tuple(self.s(*pt)) for pt in pts]
        self.d.line(pts, fill=color + (255,), width=int(width * self.k), joint="curve")
        r = width * self.k / 2
        for x, y in (pts[0], pts[-1]):
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=color + (255,))

    @staticmethod
    def arc_pts(x0, x1, y, depth, n=16, tilt=0.0):
        pts = []
        for i in range(n + 1):
            t = i / n
            pts.append((x0 + (x1 - x0) * t, y + depth * math.sin(math.pi * t) + tilt * (t - 0.5)))
        return pts

    def tilt(self, i):
        (a, b) = self.p["eyes"]
        return ((b[1] + b[3]) - (a[1] + a[3])) / 2 / max(1, (b[0] - a[0]))

    # -- ojos
    def eyes(self, kind):
        if kind == "open":
            return
        for i, box in enumerate(self.p["eyes"]):
            x0, y0, x1, y1 = box
            w, h = x1 - x0, y1 - y0
            cx = (x0 + x1) / 2
            if kind in ("closed", "happy"):
                self.cover(box, grow=0.8)
                if kind == "closed":
                    yy = y0 + h * 0.62
                    self.line(self.arc_pts(x0 + 0.5, x1 - 0.5, yy, h * 0.16), 1.5)
                    # pestaña exterior
                    ox = x0 + 0.5 if i == 0 else x1 - 0.5
                    self.line([(ox, yy), (ox + (-1.6 if i == 0 else 1.6), yy - 1.2)], 1.1)
                else:
                    yy = y0 + h * 0.62
                    self.line(self.arc_pts(x0 + 1.2, x1 - 1.2, yy, -h * 0.30), 1.6)
            elif kind == "wide":
                self._scale_eye(box, 1.16)
                self._highlight(cx + w * 0.12, y0 + h * 0.36, w * 0.10)
            elif kind == "sparkle":
                self._star(cx - w * 0.12, y0 + h * 0.42, w * 0.20)
                self._highlight(cx + w * 0.18, y0 + h * 0.66, w * 0.07)
            elif kind in ("half", "half_sad"):
                # párpado bajado hasta la mitad: tapa la parte superior y dibuja el borde
                mask = Image.new("L", self.im.size, 0)
                md = ImageDraw.Draw(mask)
                cut = y0 + h * (0.34 if kind == "half" else 0.36)
                md.ellipse(self.s(x0 - 1, y0 - 1.5, x1 + 1, y1 + 1), fill=255)
                md.rectangle(self.s(x0 - 2, cut, x1 + 2, y1 + 3), fill=0)
                mask = mask.filter(ImageFilter.GaussianBlur(self.k * 0.4))
                skin = self.skin_around(box, 1.0)
                self.im.paste(Image.new("RGBA", self.im.size, skin + (255,)), (0, 0), mask)
                if kind == "half":
                    self.line(self.arc_pts(x0 + 0.2, x1 - 0.2, cut + 0.4, -0.7), 1.9)
                else:  # cejas tristes: borde inclinado hacia fuera
                    hi_in, lo_out = (cut - 0.6, cut + 1.0)
                    pts = [(x0 + 0.2, lo_out), (x1 - 0.2, hi_in)] if i == 0 else [(x0 + 0.2, hi_in), (x1 - 0.2, lo_out)]
                    self.line(pts, 1.9)

    def _scale_eye(self, box, f):
        x0, y0, x1, y1 = box
        pad = 1.5
        bb = [int(v) for v in self.s(x0 - pad, y0 - pad, x1 + pad, y1 + pad)]
        crop = self.im.crop(bb)
        nw, nh = int(crop.width * f), int(crop.height * f)
        big = crop.resize((nw, nh), Image.LANCZOS)
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        pos = (int(cx - nw / 2), int(cy - nh / 2))
        m = Image.new("L", (nw, nh), 0)
        ImageDraw.Draw(m).ellipse((nw * 0.08, nh * 0.08, nw * 0.92, nh * 0.92), fill=255)
        m = m.filter(ImageFilter.GaussianBlur(self.k * 0.5))
        self.cover(box, grow=0.6)
        self.im.paste(big, pos, m)

    def _highlight(self, x, y, r):
        (x, y), r = self.s(x, y), r * self.k
        self.d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 235))

    def _star(self, x, y, r):
        (x, y), r = self.s(x, y), r * self.k
        pts = []
        for j in range(8):
            ang = math.pi / 4 * j - math.pi / 2
            rr = r if j % 2 == 0 else r * 0.28
            pts.append((x + rr * math.cos(ang), y + rr * math.sin(ang)))
        self.d.polygon(pts, fill=(255, 255, 255, 245))

    # -- boca
    def mouth(self, kind):
        if kind == "orig":
            return
        x0, y0, x1, y1 = self.p["mouth"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w = x1 - x0
        self.cover((x0 - 0.5, y0 - 1, x1 + 0.5, y1 + 1), grow=0.6)
        ink, mink = self.p["ink"], self.p["mouth_ink"]
        tongue = (236, 128, 136)
        if kind == "smile_open":
            self._open_mouth(cx, cy - 1, w * 0.62, 3.6, mink, tongue)
        elif kind in ("grin", "talk_wide"):
            self._open_mouth(cx, cy - 1.5, w * (0.9 if kind == "grin" else 0.7), 5.4 if kind == "grin" else 4.2, mink, tongue)
        elif kind == "talk":
            self._open_mouth(cx, cy - 0.8, w * 0.42, 2.8, mink, tongue)
        elif kind == "o":
            r = 2.0
            self.d.ellipse(self.s(cx - r * 0.85, cy - r, cx + r * 0.85, cy + r * 1.1), fill=mink + (255,),
                           outline=ink + (255,), width=int(0.6 * self.k))
        elif kind == "sleep":
            r = 1.1
            self.d.ellipse(self.s(cx - r, cy - r * 0.6, cx + r, cy + r), fill=mink + (255,))
        elif kind == "flat":
            self.line([(cx - w * 0.28, cy), (cx + w * 0.28, cy - 0.2)], 1.1)
        elif kind == "small":
            self.line(self.arc_pts(cx - w * 0.22, cx + w * 0.22, cy - 0.3, 0.9), 1.0)
        elif kind == "side":
            self.line([(cx - w * 0.10, cy + 0.2), (cx + w * 0.34, cy - 0.5)], 1.1)
        elif kind == "frown":
            self.line(self.arc_pts(cx - w * 0.26, cx + w * 0.26, cy + 0.9, -1.4), 1.1)
        elif kind == "wavy":
            pts = [(cx - w * 0.34 + w * 0.68 * t / 20, cy + 0.8 * math.sin(t / 20 * 2.5 * math.pi)) for t in range(21)]
            self.line(pts, 1.0)

    def _open_mouth(self, cx, top, w, h, fill, tongue):
        ink = self.p["ink"]
        x0, x1 = cx - w / 2, cx + w / 2
        pts = [(x0, top)] + [(cx + (w / 2) * math.cos(math.pi * (1 - i / 20)), top + h * math.sin(math.pi * i / 20)) for i in range(21)] + [(x1, top)]
        poly = [tuple(self.s(*pt)) for pt in pts]
        self.d.polygon(poly, fill=fill + (255,))
        # lengua: elipse en la parte baja recortada a la boca
        tm = Image.new("L", self.im.size, 0)
        ImageDraw.Draw(tm).polygon(poly, fill=255)
        tl = Image.new("L", self.im.size, 0)
        ImageDraw.Draw(tl).ellipse(self.s(cx - w * 0.32, top + h * 0.55, cx + w * 0.32, top + h * 1.4), fill=255)
        tl = Image.fromarray(np.minimum(np.asarray(tm), np.asarray(tl)))
        self.im.paste(Image.new("RGBA", self.im.size, tongue + (255,)), (0, 0), tl)
        self.d.line(poly + [poly[0]], fill=ink + (255,), width=int(0.7 * self.k), joint="curve")

    # -- extras
    def extras(self, names):
        (lx0, ly0, lx1, ly1), (rx0, ry0, rx1, ry1) = self.p["eyes"]
        blush = self.p["blush"]
        for n in names:
            if n in ("blush", "blush_strong"):
                alpha = 70 if n == "blush" else 120
                for bx, by in (((lx0 + lx1) / 2 - 1, ly1 + 3.2), ((rx0 + rx1) / 2 + 1, ry1 + 3.2)):
                    layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
                    ImageDraw.Draw(layer).ellipse(self.s(bx - 5, by - 2.2, bx + 5, by + 2.2), fill=blush + (alpha,))
                    layer = layer.filter(ImageFilter.GaussianBlur(self.k * 0.9))
                    self.im.alpha_composite(layer)
                    if n == "blush_strong":
                        for j in range(3):
                            sx = bx - 2.6 + j * 2.3
                            self.line([(sx + 0.7, by - 1.1), (sx - 0.5, by + 1.0)], 0.55, (226, 110, 125))
            elif n == "sweat":
                x, y, r = rx1 + 5, ry0 + 2, 2.6
                drop = [tuple(self.s(x, y - r * 2.4))]
                drop += [tuple(self.s(x + r * math.cos(a), y + r * math.sin(a)))
                         for a in [math.radians(d) for d in range(-30, 211, 10)]]
                self.d.polygon(drop, fill=(176, 220, 248, 245))
                self.d.line(drop + [drop[0]], fill=(92, 142, 196, 255), width=int(0.55 * self.k), joint="curve")
                self.d.ellipse(self.s(x - 1.2, y - 0.6, x - 0.3, y + 0.8), fill=(255, 255, 255, 235))
            elif n == "tear_gloss":
                for (x0, y0, x1, y1) in self.p["eyes"]:
                    self.d.line([tuple(self.s(x0 + 2.5, y1 - 1.2)), tuple(self.s(x1 - 2.5, y1 - 1.2))],
                                fill=(255, 255, 255, 200), width=int(0.7 * self.k))
            elif n == "sparkle_cheeks":
                for (x, y, r) in ((lx0 - 6, ly0 - 3, 2.4), (rx1 + 6.5, ry0 - 5, 2.8), (rx1 + 3, ry1 + 7, 1.6)):
                    pts = []
                    for j in range(8):
                        ang = math.pi / 4 * j
                        rr = r if j % 2 == 0 else r * 0.3
                        pts.append(tuple(self.s(x + rr * math.cos(ang), y + rr * math.sin(ang))))
                    self.d.polygon(pts, fill=(255, 214, 102, 255), outline=(214, 150, 40, 255))


def face_box(p: dict, margin: float = 16) -> tuple[int, int, int, int]:
    xs = [v for b in p["eyes"] for v in (b[0], b[2])] + [p["mouth"][0], p["mouth"][2]]
    ys = [v for b in p["eyes"] for v in (b[1], b[3])] + [p["mouth"][1], p["mouth"][3]]
    return (int(min(xs) - margin), int(min(ys) - margin), int(max(xs) + margin), int(max(ys) + margin))


def render(base_big: Image.Image, base_out: Image.Image, p: dict, eyes: str, mouth: str, extras: list) -> Image.Image:
    """Retoca solo el recorte de la cara a SS×OUT y lo pega sobre la imagen a OUT."""
    k = SS * OUT
    fx0, fy0, fx1, fy1 = face_box(p)
    crop = base_big.crop((fx0 * k, fy0 * k, fx1 * k, fy1 * k))
    f = Face(crop, p, (fx0, fy0))
    f.eyes(eyes)
    f.mouth(mouth)
    f.extras(extras)
    small = crop.convert("RGBa").resize((crop.width // SS, crop.height // SS), Image.LANCZOS).convert("RGBA")
    out = base_out.copy()
    out.paste(small, (fx0 * OUT, fy0 * OUT))
    return out


def sharpen(im: Image.Image) -> Image.Image:
    r, g, b, a = im.split()
    rgb = Image.merge("RGB", (r, g, b)).filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    return Image.merge("RGBA", (*rgb.split(), a))


def build(cid: str) -> dict[str, Image.Image]:
    p = PARAMS[cid]
    a = clean(load_rgb(cid), p)
    poses = {"wave": cutout(a), "idle": cutout(idle_pose(a, p))}
    big = {k: upscale(v, SS * OUT) for k, v in poses.items()}
    base = {k: v.convert("RGBa").resize((v.width // SS, v.height // SS), Image.LANCZOS).convert("RGBA")
            for k, v in big.items()}
    out_dir = CHARS / cid / "expressions"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.*"):
        old.unlink()
    frames: dict[str, Image.Image] = {}
    for name, (pose, eyes, mouth, extras) in EXPRESSIONS.items():
        args = (big[pose], base[pose], p)
        frames[name] = render(*args, eyes, mouth, extras)
        if eyes in BLINK_EYES:
            frames[f"{name}_blink"] = render(*args, "closed", mouth, extras)
        if name in TALK_MOUTH:
            frames[f"{name}_talk"] = render(*args, eyes, TALK_MOUTH[name], extras)
    bbox = None
    for im in frames.values():
        b = im.getbbox()
        bbox = b if bbox is None else (min(bbox[0], b[0]), min(bbox[1], b[1]), max(bbox[2], b[2]), max(bbox[3], b[3]))
    bbox = (max(0, bbox[0] - 6), max(0, bbox[1] - 6), bbox[2] + 6, bbox[3] + 6)
    for name, im in frames.items():
        frames[name] = sharpen(im.crop(bbox))
        # WebP con pérdida mínima y alfa sin pérdida: ~10 veces menos que PNG
        frames[name].save(out_dir / f"{name}.webp", quality=92, alpha_quality=100, method=6)
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", help="guarda una hoja de contacto con todas las expresiones")
    ap.add_argument("--only", nargs="*", default=list(PARAMS))
    args = ap.parse_args()
    sheets = []
    for cid in args.only:
        frames = build(cid)
        print(cid, len(frames), "imágenes")
        sheets.append(frames)
    if args.sheet:
        cell_w = max(im.width for fr in sheets for im in fr.values())
        cell_h = max(im.height for fr in sheets for im in fr.values())
        names = [n for n in sheets[0] if not n.endswith(("_blink", "_talk"))]
        sc = 0.5
        cw, ch = int(cell_w * sc), int(cell_h * sc)
        sheet = Image.new("RGBA", (cw * len(names), ch * len(sheets)), (60, 64, 80, 255))
        for r, fr in enumerate(sheets):
            for c, n in enumerate(names):
                im = fr[n].resize((int(fr[n].width * sc), int(fr[n].height * sc)), Image.LANCZOS)
                sheet.alpha_composite(im, (c * cw, r * ch))
        sheet.save(args.sheet)


if __name__ == "__main__":
    main()
