"""Planificación de sesiones y construcción de preguntas.

Una sesión es una lista de *specs* serializables ({"module", "key", "ex"}),
lo que permite guardarla y continuarla más tarde. Cada spec se convierte en
una `Question` justo antes de mostrarse (distractores nuevos cada vez).
"""
from __future__ import annotations

import random
import re
import time
from typing import Callable

from ..content import kana as kana_data
from ..content.repository import ContentRepo, Kanji, Word, meaning
from ..core.i18n import language, t
from ..core.srs import ItemState
from ..core.userdb import UserDB
from .model import Question

KANJI_EXERCISES = ["meaning", "reading_choice", "reading_write", "match", "in_word", "onkun"]
VOCAB_EXERCISES = ["ja_meaning", "meaning_ja", "reading_write", "reading_word", "meaning_write", "cloze"]
GRAMMAR_EXERCISES = ["particle", "structure", "order"]
KANA_EXERCISES = ["choice", "write", "inverse"]

Spec = dict


def _shorten(text: str, n: int = 48) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip("; ,") + "…"


def _clean_kun(r: str) -> str:
    return r.replace("-", "").replace(".", "")


def _display_kun(r: str) -> str:
    """'た.べる' -> 'た(べる)' para mostrar el okurigana."""
    r = r.replace("-", "")
    if "." in r:
        stem, oku = r.split(".", 1)
        return f"{stem}({oku})"
    return r


class Engine:
    def __init__(self, repo: ContentRepo, db: UserDB, rng: random.Random | None = None):
        self.repo = repo
        self.db = db
        self.rng = rng or random.Random()

    # =================================================================
    # Planificación
    # =================================================================
    def _prioritize(self, module: str, keys: list[str], n: int, weak_only: bool) -> list[str]:
        """Pendientes → con más errores → nuevos (en orden) → resto al azar."""
        states = self.db.states(module)
        now = time.time()
        if weak_only:
            weak = [k for k in keys if k in states and states[k].wrong > 0]
            weak.sort(key=lambda k: (-states[k].error_rate, -states[k].wrong))
            return weak[:n]
        due = [k for k in keys if k in states and states[k].is_due(now)]
        self.rng.shuffle(due)
        shaky = sorted((k for k in keys if k in states and k not in due and states[k].error_rate > 0.3),
                       key=lambda k: -states[k].error_rate)
        new = [k for k in keys if k not in states]
        chosen: list[str] = []
        for bucket in (due, shaky, new[: max(5, n // 2)]):
            for k in bucket:
                if len(chosen) >= n:
                    break
                if k not in chosen:
                    chosen.append(k)
        rest = [k for k in keys if k not in chosen]
        self.rng.shuffle(rest)
        chosen += rest[: n - len(chosen)]
        self.rng.shuffle(chosen)
        return chosen

    def plan(self, module: str, cfg: dict, n: int) -> list[Spec]:
        return getattr(self, f"_plan_{module}")(cfg, n)

    def _plan_kana(self, cfg: dict, n: int) -> list[Spec]:
        pool = [k.key for k in kana_data.select(cfg["scripts"], cfg["groups"])]
        keys = self._prioritize("kana", pool, n, cfg.get("weak_only", False))
        return [{"module": "kana", "key": k, "ex": cfg["exercise"], "diff": cfg.get("difficulty", "normal")}
                for k in keys]

    def _plan_kanji(self, cfg: dict, n: int) -> list[Spec]:
        pool = cfg.get("picked") or [k.char for k in self.repo.kanji_by_levels(cfg["levels"])]
        ex = cfg["exercise"]
        if ex == "match":
            keys = self._prioritize("kanji", pool, n * 4, cfg.get("weak_only", False))
            groups = [keys[i:i + 4] for i in range(0, len(keys) - 3, 4)][: max(1, n // 3)]
            return [{"module": "kanji", "key": "|".join(g), "ex": "match"} for g in groups]
        keys = self._prioritize("kanji", pool, n, cfg.get("weak_only", False))
        return [{"module": "kanji", "key": k, "ex": self._pick_ex(ex, KANJI_EXERCISES, exclude=("match",))}
                for k in keys]

    def _plan_vocab(self, cfg: dict, n: int) -> list[Spec]:
        pool = [str(x) for x in cfg.get("picked") or []] or [w.key for w in self.repo.words_by_levels(cfg["levels"])]
        keys = self._prioritize("vocab", pool, n, cfg.get("weak_only", False))
        return [{"module": "vocab", "key": k, "ex": self._pick_ex(cfg["exercise"], VOCAB_EXERCISES)} for k in keys]

    def _plan_grammar(self, cfg: dict, n: int) -> list[Spec]:
        items = self.repo.grammar_by_levels(cfg["levels"])
        if cfg["exercise"] != "mixed":
            items = [g for g in items if g.type == cfg["exercise"]]
        keys = self._prioritize("grammar", [g.key for g in items], n, cfg.get("weak_only", False))
        return [{"module": "grammar", "key": k, "ex": "grammar"} for k in keys]

    def plan_review(self, modules: list[str], setups: dict[str, dict], limit: int = 50) -> list[Spec]:
        specs = []
        for r in self.db.due_items(modules, limit=limit):
            m, key = r["module"], r["item_key"]
            setup = setups.get(m, {})
            if m == "kana":
                specs.append({"module": m, "key": key, "ex": setup.get("exercise", "choice"),
                              "diff": setup.get("difficulty", "normal")})
            elif m == "kanji":
                ex = setup.get("exercise", "meaning")
                specs.append({"module": m, "key": key, "ex": self._pick_ex("mixed" if ex == "match" else ex,
                                                                           KANJI_EXERCISES, exclude=("match",))})
            elif m == "vocab":
                specs.append({"module": m, "key": key, "ex": self._pick_ex(setup.get("exercise", "mixed"),
                                                                           VOCAB_EXERCISES)})
            else:
                specs.append({"module": m, "key": key, "ex": "grammar"})
        self.rng.shuffle(specs)
        return specs

    def plan_quick(self, modules: list[str], setups: dict[str, dict], last_module: str | None) -> list[Spec]:
        specs = self.plan_review(modules, setups, limit=30)
        main = last_module if last_module in ("kana", "kanji", "vocab", "grammar") else "kana"
        cfg = dict(setups[main])
        if main == "kanji" and cfg.get("exercise") == "match":
            cfg["exercise"] = "mixed"
        seen = {(s["module"], s["key"]) for s in specs}
        specs += [s for s in self.plan(main, cfg, 40) if (s["module"], s["key"]) not in seen]
        return specs

    def _pick_ex(self, ex: str, allowed: list[str], exclude: tuple = ()) -> str:
        if ex == "mixed":
            return self.rng.choice([e for e in allowed if e not in exclude])
        return ex

    # =================================================================
    # Construcción
    # =================================================================
    def build(self, spec: Spec) -> Question | None:
        builder: Callable[[Spec], Question | None] = getattr(self, f"_build_{spec['module']}")
        return builder(spec)

    def _choices(self, correct: str, pool: list[str], k: int) -> tuple[list[str], int]:
        cands = list(dict.fromkeys(p for p in pool if p and p != correct))
        self.rng.shuffle(cands)
        opts = cands[: k - 1] + [correct]
        self.rng.shuffle(opts)
        return opts, opts.index(correct)

    def progress_text(self, module: str, key: str) -> str:
        s: ItemState = self.db.state(module, key)
        if s.correct + s.wrong == 0:
            return t("progress.new")
        if s.is_due(time.time()) or s.lapses >= 2 and s.error_rate > 0.3:
            return t("progress.review", c=s.correct, w=s.wrong)
        return t("progress.learned" if s.learned else "progress.learning", c=s.correct, w=s.wrong)

    # ---- kana ----------------------------------------------------------
    def _build_kana(self, spec: Spec) -> Question | None:
        k = kana_data.BY_KEY.get(spec["key"])
        if k is None:
            return None
        diff = spec.get("diff", "normal")
        n_opts = {"easy": 3, "normal": 4, "hard": 6}.get(diff, 4)
        family = [x for x in kana_data.ALL_KANA if x.script == k.script and (x.group == "yoon") == (k.group == "yoon")
                  and not (x.accepted() & k.accepted())]
        if diff == "hard":
            conf = set(kana_data.confusables_of(k))
            family.sort(key=lambda x: (x.char not in conf, self.rng.random()))
            family = family[: n_opts - 1]
        else:
            self.rng.shuffle(family)

        q = Question("kana", k.key, 0, spec["ex"], "choice", "")
        if spec["ex"] == "write":
            q.kind, q.instruction, q.prompt = "text", t("ins.kana.write"), k.char
            q.accepted, q.input_mode = k.accepted(), "romaji"
        elif spec["ex"] == "inverse":
            q.instruction, q.prompt, q.prompt_jp = t("ins.kana.inverse"), k.romaji, False
            q.options, q.answer_index = self._choices(k.char, [x.char for x in family], n_opts)
        else:
            q.instruction, q.prompt = t("ins.kana.choice"), k.char
            q.options, q.answer_index = self._choices(k.romaji, [x.romaji for x in family], n_opts)
            q.options_jp = False
        q.correct_display = f"{k.char} = {k.romaji}"
        q.explanation = self._kana_explanation(k)
        return q

    def _kana_explanation(self, k: kana_data.Kana) -> str:
        show_romaji = self.db.get("kana_romaji_explanations")
        parts = []
        if k.group in kana_data.BASE_GROUPS:
            row = kana_data.select([k.script], [k.group])
            parts.append(t("fb.kana.group", g=" ".join(x.char for x in row)))
        else:
            parts.append(t(f"fb.kana.{k.group}"))
        conf = kana_data.confusables_of(k)
        if conf:
            other = next(x for x in kana_data.ALL_KANA if x.char == conf[0])
            parts.append(t("fb.kana.confuse", c=other.char, r=other.romaji if show_romaji else "…"))
        if k.variants:
            parts.append(t("fb.kana.variants", v=", ".join(k.variants)))
        return " ".join(parts)

    # ---- kanji ---------------------------------------------------------
    def _kanji_meaning(self, k: Kanji, n: int = 2) -> tuple[str, str]:
        ms, lang = meaning(k.meanings, language())
        return ", ".join(ms[:n]), lang

    def _kanji_details(self, k: Kanji) -> list[tuple[str, str]]:
        ms, lang = meaning(k.meanings, language())
        words = self.repo.words_with_kanji(k.char, 3)
        wtxt = "  ·  ".join(f"{w.word}【{w.reading}】{_shorten(meaning(w.meanings, language())[0][0] if meaning(w.meanings, language())[0] else '', 22)}" for w in words)
        out = [(t("detail.meaning"), ", ".join(ms[:4]) + ("" if lang == language() else " (EN)")),
               (t("onyomi"), "、".join(k.onyomi) or "—"),
               (t("kunyomi"), "、".join(_display_kun(r) for r in k.kunyomi) or "—")]
        if wtxt:
            out.append((t("detail.examples"), wtxt))
        out += [(t("detail.level"), f"N{k.jlpt}"), (t("detail.progress"), self.progress_text("kanji", k.char))]
        return out

    def _kanji_pool(self, k: Kanji) -> list[Kanji]:
        pool = self.repo.kanji_by_levels([k.jlpt])
        if len(pool) < 12:
            pool += self.repo.kanji_by_levels([lvl for lvl in (5, 4, 3) if lvl != k.jlpt])
        return [p for p in pool if p.char != k.char]

    def _build_kanji(self, spec: Spec) -> Question | None:
        ex = spec["ex"]
        if ex == "match":
            return self._kanji_match(spec)
        k = self.repo.kanji(spec["key"])
        if k is None:
            return None
        has_on, has_kun = bool(k.onyomi), bool(k.kunyomi)
        if ex == "onkun" and not (has_on and has_kun):
            ex = "reading_choice"
        if ex in ("reading_choice", "reading_write", "onkun") and not (has_on or has_kun):
            ex = "meaning"
        words = self.repo.words_with_kanji(k.char, 6) if ex == "in_word" else []
        if ex == "in_word" and not words:
            ex = "meaning"

        q = Question("kanji", k.char, k.jlpt, ex, "choice", t(f"ins.kanji.{ex}"), prompt=k.char)
        q.details = self._kanji_details(k)
        pool = self._kanji_pool(k)
        self.rng.shuffle(pool)
        correct_meaning, _ = self._kanji_meaning(k)
        if ex == "meaning":
            q.options, q.answer_index = self._choices(correct_meaning, [self._kanji_meaning(p)[0] for p in pool[:12]], 4)
            q.options_jp = False
            q.correct_display = f"{k.char} = {correct_meaning}"
        elif ex == "reading_choice":
            own = {r for r in k.onyomi} | {_display_kun(r) for r in k.kunyomi}
            use_on = has_on and (not has_kun or self.rng.random() < 0.5)
            correct = self.rng.choice(k.onyomi) if use_on else _display_kun(self.rng.choice(k.kunyomi))
            others = [r for p in pool[:20] for r in (p.onyomi if use_on else [_display_kun(x) for x in p.kunyomi])
                      if r not in own]
            q.options, q.answer_index = self._choices(correct, others, 4)
            q.correct_display = f"{k.char} → {correct}"
            q.hint = correct_meaning
        elif ex == "reading_write":
            q.kind, q.input_mode, q.hint = "text", "kana", correct_meaning
            q.accepted = set(k.onyomi) | {_clean_kun(r) for r in k.kunyomi} | {r.split(".")[0].replace("-", "")
                                                                              for r in k.kunyomi}
            q.correct_display = "、".join(list(k.onyomi) + [_display_kun(r) for r in k.kunyomi])
        elif ex == "onkun":
            is_on = self.rng.random() < 0.5
            reading = self.rng.choice(k.onyomi) if is_on else _display_kun(self.rng.choice(k.kunyomi))
            q.hint = reading
            q.options, q.answer_index, q.options_jp = [t("onyomi"), t("kunyomi")], 0 if is_on else 1, False
            q.correct_display = f"{reading}: {t('onyomi') if is_on else t('kunyomi')}"
            q.explanation = t("fb.onkun.on" if is_on else "fb.onkun.kun")
        elif ex == "in_word":
            w = self.rng.choice(words)
            q.prompt = w.word.replace(k.char, "〇")
            q.reading = w.reading
            wm, _ = meaning(w.meanings, language())
            q.hint = _shorten(wm[0], 40) if wm else ""
            q.options, q.answer_index = self._choices(k.char, [p.char for p in pool[:10]], 4)
            q.correct_display = f"{w.word}【{w.reading}】"
        return q

    def _kanji_match(self, spec: Spec) -> Question | None:
        ks = [self.repo.kanji(c) for c in spec["key"].split("|")]
        ks = [k for k in ks if k]
        if len(ks) < 2:
            return None
        q = Question("kanji", spec["key"], ks[0].jlpt, "match", "match", t("ins.kanji.match"))
        q.pairs = [(k.char, self._kanji_meaning(k, 2)[0], k.char) for k in ks]
        return q

    # ---- vocabulario ---------------------------------------------------
    def _word_meaning(self, w: Word) -> tuple[str, str]:
        ms, lang = meaning(w.meanings, language())
        return (_shorten(ms[0]) if ms else "?"), lang

    def _build_vocab(self, spec: Spec) -> Question | None:
        w = self.repo.word(spec["key"])
        if w is None:
            return None
        ex = spec["ex"]
        has_kanji = w.word != w.reading
        if ex in ("reading_write", "reading_word") and not has_kanji:
            ex = "meaning_write" if ex == "reading_write" else "ja_meaning"
        if ex == "cloze" and not (w.example_ja and w.example_target):
            ex = "ja_meaning"
        if ex == "audio":
            ex = "ja_meaning"

        m, mlang = self._word_meaning(w)
        fallback = mlang != language()
        q = Question("vocab", w.key, w.jlpt, ex, "choice", t(f"ins.vocab.{ex}"), prompt=w.word)
        if has_kanji:
            q.reading = w.reading
        pool = [p for p in self.repo.words_by_levels([w.jlpt]) if p.id != w.id]
        self.rng.shuffle(pool)
        pool = pool[:20]

        if ex == "ja_meaning":
            q.options, q.answer_index = self._choices(m, [self._word_meaning(p)[0] for p in pool], 4)
            q.options_jp = False
        elif ex == "meaning_ja":
            q.prompt, q.prompt_jp, q.reading = m, False, ""
            q.options, q.answer_index = self._choices(w.word, [p.word for p in pool], 4)
        elif ex == "reading_write":
            q.kind, q.input_mode, q.reading_is_answer = "text", "kana", True
            q.accepted, q.hint = {w.reading}, m
        elif ex == "reading_word":
            q.prompt, q.reading = w.reading, ""
            similar = [p.word for p in pool if p.word != p.reading]
            q.options, q.answer_index = self._choices(w.word, similar, 4)
            q.hint = m
        elif ex == "meaning_write":
            q.kind, q.input_mode = "text", "kana"
            q.prompt, q.prompt_jp, q.reading = m, False, ""
            q.accepted = {w.reading, w.word}
        elif ex == "cloze":
            q.prompt = w.example_ja.replace(w.example_target, "＿＿", 1)
            q.reading = ""
            q.hint = f"{w.example_en} (EN)" if language() == "es" else w.example_en
            targets = [p.example_target for p in pool if p.example_target and p.example_target != w.example_target]
            q.options, q.answer_index = self._choices(w.example_target, targets, 4)

        q.correct_display = f"{w.word}【{w.reading}】 {m}" if has_kanji else f"{w.word}  {m}"
        if ex == "cloze":
            q.correct_display = f"{w.example_target}  →  {w.word}【{w.reading}】 {m}"
        if fallback:
            q.explanation = t("fb.lang_fallback")
        q.romaji = ""  # se calcula en la UI si el usuario lo activa
        q.details = [(t("detail.meaning"), "; ".join(meaning(w.meanings, language())[0][:3]))]
        if w.example_ja and ex != "cloze":
            q.details.append((t("detail.example"), f"{w.example_ja}\n{w.example_en}"))
        q.details += [(t("detail.level"), f"N{w.jlpt}"), (t("detail.progress"), self.progress_text("vocab", w.key))]
        return q

    # ---- gramática -----------------------------------------------------
    def _build_grammar(self, spec: Spec) -> Question | None:
        g = self.repo.grammar_item(spec["key"])
        if g is None:
            return None
        lang = language()
        q = Question("grammar", g.id, g.jlpt, g.type, "choice", t(f"ins.grammar.{g.type}"))
        q.hint = g.translation.get(lang, "")
        q.explanation = g.explanation.get(lang, "")
        if g.type == "order":
            q.kind = "order"
            q.tokens = list(g.tokens)
            while len(q.tokens) > 1 and q.tokens == list(g.accepted[0]):
                self.rng.shuffle(q.tokens)
            q.accepted_orders = [list(a) for a in g.accepted]
            q.correct_display = "".join(g.accepted[0]) + "。"
        else:
            q.prompt = re.sub("＿+", "＿＿", g.sentence)
            opts = list(g.options)
            self.rng.shuffle(opts)
            q.options, q.answer_index = opts, opts.index(g.answer)
            q.correct_display = g.sentence.replace("＿＿", g.answer).replace("＿", g.answer)
        q.details = [(t("detail.level"), f"N{g.jlpt} · {t('demo')}"),
                     (t("detail.progress"), self.progress_text("grammar", g.id))]
        return q
