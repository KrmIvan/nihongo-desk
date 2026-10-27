"""Personalidades: cómo se mueve el personaje, cómo reacciona y qué dice.

Cada reacción es ``(expresión, movimiento, efecto, duración_ms, frase, prob_frase, siguiente)``.
La personalidad cambia expresiones, energía de los movimientos, efectos y
frases; no es solo una etiqueta.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Reaction:
    expr: str
    motion: str = "none"          # hop | bounce | nod | tilt | droop | wiggle | sway | none
    effect: str = ""              # sparkles | hearts | notes | confetti | question | exclaim | dots | zz
    ms: int = 1800
    phrase: str = ""              # clave de PHRASES
    chance: float = 0.0           # probabilidad de decir la frase
    then: "Reaction | None" = None


@dataclass(frozen=True)
class Personality:
    id: str
    float_amp: float              # px de flotación (a 280 px de alto)
    float_period: float           # s
    energy: float                 # escala de saltos/rebotes
    blink: tuple[float, float]    # intervalo entre parpadeos (s)
    chattiness: float             # multiplica la probabilidad de hablar
    idle_mood: str
    reactions: dict = field(default_factory=dict)
    phrases: dict = field(default_factory=dict)


R = Reaction
ENCOURAGE = R("encouraging", "hop", "", 1700, "encourage", 0.25)

PERSONALITIES: dict[str, Personality] = {
    "energetic": Personality(
        "energetic", float_amp=5.0, float_period=2.6, energy=1.25, blink=(2.2, 5.0), chattiness=1.2,
        idle_mood="neutral",
        reactions={
            "correct": R("happy", "hop", "notes", 1300, "correct", 0.18),
            "streak3": R("very_happy", "bounce", "sparkles", 1900, "streak", 0.7),
            "streak5": R("celebrating", "bounce", "confetti", 2400, "streak", 0.8),
            "wrong": R("surprised", "wiggle", "exclaim", 650, then=R("encouraging", "hop", "", 1500, "wrong", 0.35)),
            "wrong3": R("sad", "droop", "", 1300, then=R("encouraging", "bounce", "", 1700, "encourage", 0.8)),
            "end_good": R("celebrating", "bounce", "confetti", 3200, "end_good", 1.0),
            "end_ok": R("encouraging", "hop", "sparkles", 2600, "end_ok", 1.0),
            "greet_first": R("greeting", "hop", "", 2400, "greet_first", 0.9),
            "greet_back": R("greeting", "hop", "", 2000, "greet_back", 0.7),
            "wake": R("surprised", "hop", "exclaim", 900, "wake", 0.6),
            "pet": R("very_happy", "hop", "hearts", 1400, "pet", 0.5),
            "fidget": R("happy", "sway", "notes", 2200),
        },
        phrases={
            "correct": [("やったー！", "¡Bien!", "Yay!"), ("いいね！", "¡Muy bien!", "Nice!")],
            "streak": [("絶好調！", "¡Estás en racha!", "You're on fire!"), ("すごい、すごい！", "¡Increíble!", "Amazing!")],
            "encourage": [("ファイト！", "¡Ánimo!", "Go for it!")],
        },
    ),
    "calm": Personality(
        "calm", float_amp=3.2, float_period=3.8, energy=0.7, blink=(3.0, 6.5), chattiness=0.8,
        idle_mood="neutral",
        reactions={
            "correct": R("happy", "nod", "", 1300, "correct", 0.12),
            "streak3": R("happy", "nod", "sparkles", 1600, "streak", 0.4),
            "streak5": R("very_happy", "hop", "sparkles", 2000, "streak", 0.6),
            "wrong": R("thinking", "tilt", "dots", 1100, then=R("encouraging", "nod", "", 1400, "wrong", 0.3)),
            "wrong3": R("sad", "droop", "", 1400, then=R("encouraging", "nod", "", 1700, "encourage", 0.8)),
            "end_good": R("celebrating", "hop", "confetti", 3000, "end_good", 1.0),
            "end_ok": R("happy", "nod", "hearts", 2600, "end_ok", 1.0),
            "greet_first": R("greeting", "nod", "", 2400, "greet_first", 0.9),
            "greet_back": R("greeting", "nod", "", 2000, "greet_back", 0.6),
            "wake": R("surprised", "none", "", 900, "wake", 0.4),
            "pet": R("shy", "nod", "hearts", 1500, "pet", 0.5),
            "fidget": R("thinking", "tilt", "", 2400),
        },
        phrases={
            "correct": [("いい感じだね", "Va muy bien", "Looking good")],
            "wrong": [("ゆっくりでいいよ", "Sin prisa", "No rush")],
        },
    ),
    "shy": Personality(
        "shy", float_amp=2.8, float_period=3.2, energy=0.8, blink=(1.8, 4.0), chattiness=0.6,
        idle_mood="neutral",
        reactions={
            "correct": R("shy", "hop", "", 1300, "correct", 0.12),
            "streak3": R("happy", "hop", "hearts", 1700, "streak", 0.5),
            "streak5": R("very_happy", "bounce", "hearts", 2100, "streak", 0.6),
            "wrong": R("confused", "tilt", "", 1100, then=R("shy", "nod", "", 1400, "wrong", 0.3)),
            "wrong3": R("sad", "droop", "", 1300, then=R("encouraging", "nod", "", 1600, "encourage", 0.7)),
            "end_good": R("celebrating", "hop", "hearts", 3000, "end_good", 1.0),
            "end_ok": R("shy", "nod", "hearts", 2600, "end_ok", 1.0),
            "greet_first": R("greeting", "none", "", 2400, "greet_first", 0.8),
            "greet_back": R("shy", "hop", "", 1800, "greet_back", 0.5),
            "wake": R("surprised", "hop", "exclaim", 900, "wake", 0.5),
            "pet": R("shy", "wiggle", "hearts", 1500, "pet", 0.6),
            "fidget": R("shy", "sway", "", 2200),
        },
        phrases={
            "correct": [("す、すごいです…", "Eh… ¡qué bien!", "W-wow…")],
            "pet": [("は、恥ずかしい…", "Q-qué vergüenza…", "S-so embarrassing…")],
        },
    ),
    "serious": Personality(
        "serious", float_amp=2.0, float_period=4.2, energy=0.55, blink=(3.5, 7.0), chattiness=0.7,
        idle_mood="focused",
        reactions={
            "correct": R("focused", "nod", "", 1100, "correct", 0.12),
            "streak3": R("happy", "nod", "", 1500, "streak", 0.4),
            "streak5": R("very_happy", "hop", "sparkles", 1900, "streak", 0.6),
            "wrong": R("thinking", "tilt", "dots", 1300, "wrong", 0.3),
            "wrong3": R("thinking", "nod", "", 1500, "encourage", 0.7),
            "end_good": R("celebrating", "hop", "sparkles", 2800, "end_good", 1.0),
            "end_ok": R("encouraging", "nod", "", 2400, "end_ok", 1.0),
            "greet_first": R("greeting", "nod", "", 2200, "greet_first", 0.8),
            "greet_back": R("greeting", "nod", "", 1800, "greet_back", 0.5),
            "wake": R("focused", "nod", "", 900, "wake", 0.5),
            "pet": R("surprised", "nod", "", 1100, "pet", 0.5),
            "fidget": R("thinking", "tilt", "dots", 2400),
        },
        phrases={
            "correct": [("正確です", "Exacto", "Accurate")],
            "wrong": [("復習が大切です", "Repasar es importante", "Reviewing matters")],
            "encourage": [("集中しましょう", "Concentrémonos", "Let's focus")],
        },
    ),
}

# frases comunes (ja, es, en); la personalidad añade las suyas
PHRASES: dict[str, list[tuple[str, str, str]]] = {
    "correct": [("正解！", "¡Correcto!", "Correct!"), ("その調子！", "¡Sigue así!", "Keep it up!")],
    "streak": [("すごい！", "¡Increíble!", "Amazing!"), ("さすが！", "¡Así se hace!", "Impressive!")],
    "wrong": [("大丈夫！", "¡No pasa nada!", "It's okay!"), ("惜しい！", "¡Casi!", "So close!"),
              ("次はできるよ", "La próxima te sale", "You'll get the next one")],
    "encourage": [("頑張って！", "¡Ánimo!", "You can do it!"), ("一緒に覚えよう", "Lo aprendemos juntos", "Let's learn it together")],
    "end_good": [("よくできました！", "¡Muy bien hecho!", "Well done!")],
    "end_ok": [("お疲れさま！", "¡Buen trabajo!", "Good work!"),
               ("少しずつ上手になるよ", "Poco a poco irás mejorando", "You'll improve little by little")],
    "greet_first": [("こんにちは！", "¡Hola!", "Hello!")],
    "greet_back": [("おかえり！", "¡Hola de nuevo!", "Welcome back!"), ("また勉強しよう！", "¡Sigamos estudiando!", "Let's study again!")],
    "wake": [("はっ！", "¡Ah!", "Oh!")],
    "sleep": [("すやすや…", "Zzz…", "Zzz…")],
    "pet": [("えへへ", "Jeje", "Hehe")],
}

PERSONALITY_IDS = list(PERSONALITIES)


def get(pid: str | None) -> Personality:
    return PERSONALITIES.get(pid or "", PERSONALITIES["calm"])


def phrase(p: Personality, key: str, rng: random.Random | None = None) -> tuple[str, str, str] | None:
    rng = rng or random
    pool = list(p.phrases.get(key, [])) * 2 + PHRASES.get(key, [])  # las propias salen más
    return rng.choice(pool) if pool else None
