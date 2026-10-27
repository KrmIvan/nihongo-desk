import random
import time

import pytest

from nihongo_desk.content import kana, romaji
from nihongo_desk.content.repository import ContentRepo
from nihongo_desk.core import i18n
from nihongo_desk.core.paths import resources_dir
from nihongo_desk.core.srs import DAY, ItemState, review
from nihongo_desk.core.userdb import UserDB
from nihongo_desk.exercises.engine import KANJI_EXERCISES, VOCAB_EXERCISES, Engine
from nihongo_desk.exercises.model import normalize


@pytest.fixture
def engine(tmp_path):
    db = UserDB(tmp_path / "user.db")
    return Engine(ContentRepo(resources_dir()), db, random.Random(1))


def test_romaji_conversion():
    assert romaji.to_hiragana("nihongo") == "にほんご"
    assert romaji.to_hiragana("gakkou") == "がっこう"
    assert romaji.to_hiragana("shinbun") == "しんぶん"
    assert romaji.to_hiragana("kyou") == "きょう"
    assert romaji.to_hiragana("hon") == "ほん"
    assert romaji.to_hiragana("konnnichiha") == "こんにちは"
    assert romaji.convert_live("ky") == "ky"
    assert romaji.convert_live("kan") == "かn"


def test_kana_tables():
    assert len([k for k in kana.ALL_KANA if k.script == "h"]) == 104
    assert kana.BY_KEY["k:シ"].romaji == "shi"
    assert "si" in kana.BY_KEY["h:し"].accepted()
    assert kana.confusables_of(kana.BY_KEY["h:ぬ"]) == ["め"]


def test_normalize_kana_answers():
    assert normalize("taberu", "kana") == normalize("た.べる", "kana")
    assert normalize("nichi", "kana") == normalize("ニチ", "kana")
    assert normalize("ko-hi-", "kana") == normalize("コーヒー", "kana")


def test_srs_progression():
    s = ItemState()
    now = time.time()
    s = review(s, True, now)
    assert s.interval == 1 and s.due == pytest.approx(now + DAY)
    s = review(s, True, now)
    assert s.interval == 3
    s = review(s, True, now)
    assert s.interval > 3 and s.mastery >= 2
    s = review(s, False, now)
    assert s.interval == 0 and s.lapses == 1 and s.ease < 2.5


def test_kana_questions(engine):
    for ex in ("choice", "write", "inverse"):
        for diff in ("easy", "normal", "hard"):
            specs = engine.plan("kana", {"scripts": ["h", "k"], "groups": kana.BASE_GROUPS + kana.EXTRA_GROUPS,
                                         "exercise": ex, "difficulty": diff}, 20)
            assert len(specs) == 20
            for s in specs:
                q = engine.build(s)
                if q.kind == "choice":
                    assert len(set(q.options)) == len(q.options) == {"easy": 3, "normal": 4, "hard": 6}[diff]
                    assert q.check(q.answer_index)
                else:
                    assert q.check(kana.BY_KEY[q.key].romaji)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_kanji_and_vocab_questions(engine, lang):
    i18n.set_language(lang)
    for ex in KANJI_EXERCISES:
        for s in engine.plan("kanji", {"levels": [5, 4], "exercise": ex}, 12):
            q = engine.build(s)
            assert q is not None
            if q.kind == "choice":
                assert len(set(q.options)) == len(q.options) and q.check(q.answer_index)
            elif q.kind == "text":
                assert q.accepted
            elif q.kind == "match":
                assert len(q.pairs) == 4
    for ex in VOCAB_EXERCISES:
        for s in engine.plan("vocab", {"levels": [5], "exercise": ex}, 12):
            q = engine.build(s)
            assert q is not None
            if q.kind == "choice":
                assert len(set(q.options)) == len(q.options) == 4 and q.check(q.answer_index)
            else:
                assert q.check(next(iter(q.accepted)))
    i18n.set_language("es")


def test_grammar_and_review(engine):
    specs = engine.plan("grammar", {"levels": [5, 4], "exercise": "mixed"}, 50)
    assert len(specs) == len(engine.repo.grammar)
    for s in specs:
        q = engine.build(s)
        if q.kind == "order":
            assert q.check(q.accepted_orders[0])
        else:
            assert q.check(q.answer_index)
    engine.db.record("kana", "h:ぬ", 0, "choice", False, 1200)
    due = engine.plan_review(["kana"], {"kana": {"exercise": "write"}})
    assert due == [] or due[0]["key"] == "h:ぬ"  # vence a los 10 minutos
    assert engine.db.weakest()[0]["item_key"] == "h:ぬ"
