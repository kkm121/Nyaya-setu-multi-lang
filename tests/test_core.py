# Core tests (no internet and no model needed)

import json
import os

import pytest

from nyaya.corpus import CORPUS_PATH, MAPPING_PATH, clean_text, load_chunks, load_mapping
from nyaya.drafting import DOC_TYPES, adds_nothing_new
from nyaya.llm import extractive_answer
from nyaya.query import analyse, find_section_refs, law_period
from nyaya.translate import lock, protected_ok, unlock
from nyaya.verify import numbers_match, verify_answer

pytestmark = pytest.mark.skipif(not os.path.exists(CORPUS_PATH), reason="run python -m nyaya.corpus first")


@pytest.fixture(scope="module")
def chunks():
    # join all parts of a section, with single spaces
    out = {}
    for c in load_chunks():
        key = (c["act"], c["section"])
        text = " ".join(c["text"].split())
        if key in out:
            out[key]["text"] += " " + text
        else:
            out[key] = dict(c, text=text)
    return out


@pytest.fixture(scope="module")
def mapping():
    return load_mapping()


# Corpus
def test_key_sections_present(chunks):
    for key in [("BNS", "103"), ("BNS", "318"), ("BNSS", "173"), ("BSA", "63"), ("NIA", "138"),
                ("CPA", "35"), ("RTI", "6"), ("COI", "21"), ("IPC", "302")]:
        assert key in chunks, key


def test_murder_text(chunks):
    assert "death or imprisonment for life" in chunks[("BNS", "103")]["text"]


def test_legit_repeated_lines_kept():
    raw = "(1) see section 64, section 65,\nfoo\n(2) see section 64, section 65,\nbar"
    assert clean_text(raw).count("see section 64, section 65,") == 2


def test_mapping_known_pairs(mapping):
    assert mapping["IPC-302"][0]["to_section"] == "103"
    assert mapping["IPC-420"][0]["to_section"] == "318"
    assert mapping["CRPC-154"][0]["to_section"] == "173"
    assert mapping["CRPC-438"][0]["to_section"] == "482"
    assert mapping["IEA-65B"][0]["to_section"] == "63"
    assert mapping["IPC-124A"][0]["status"] == "Deleted"


# Query understanding
@pytest.mark.parametrize("q,expected", [
    ("punishment under section 302 IPC", ("IPC", "302")),
    ("Is 498A IPC bailable?", ("IPC", "498A")),
    ("notice under Section 138 NI Act", ("NIA", "138")),
    ("Article 21 rights", ("COI", "21")),
    ("section 35(3) of BNSS notice", ("BNSS", "35")),
])
def test_section_refs(q, expected):
    assert expected in find_section_refs(q)


def test_cheque_alias():
    assert "NIA" in analyse("My cheque bounced last week")["acts"]


def test_spelling_normalized_for_indian_law():
    from nyaya.query import normalize
    assert normalize("The check my friend had given bounced.") == "The cheque my friend had given bounced."
    assert normalize("Is this offense bailable?") == "Is this offence bailable?"
    # "check" without money context stays a normal word
    assert normalize("Please check the police station hours") == "Please check the police station hours"


def test_law_period():
    assert law_period("FIR filed on 12/03/2023") == "old"
    assert law_period("it happened on 05/08/2025") == "new"
    assert law_period("my landlord is not returning deposit") is None


# Verification
RESULTS = [
    {"act": "BNS", "section": "103", "title": "Punishment for murder",
     "text": "Whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine."},
    {"act": "NIA", "section": "138", "title": "Dishonour of cheque",
     "text": "punished with imprisonment for a term which may be extended to two years, or with fine which may extend to twice the amount of the cheque"},
]


def test_supported_sentence_kept():
    out = verify_answer("**In short:** Murder is punished with death or imprisonment for life [S1].", RESULTS, [])
    assert out["supported"] == 1 and not out["abstain"]


def test_unknown_section_removed():
    ans = "**In short:** Murder is punished with death [S1].\n- Section 999 says you get bail [S1]."
    out = verify_answer(ans, RESULTS, [])
    assert "999" not in out["answer"] and out["removed"] == 1


def test_fake_citation_tag_removed():
    out = verify_answer("Murder is punished with death or imprisonment for life [S1][S9].", RESULTS, [])
    assert "[S9]" not in out["answer"]


def test_wrong_number_flagged():
    assert numbers_match("Jail up to seven years [S2].", RESULTS[1]["text"]) == ["7"]
    assert numbers_match("Jail up to two years or fine up to twice the amount [S2].", RESULTS[1]["text"]) == []


def test_uncited_legal_number_claim_removed():
    out = verify_answer("Murder is punished with death [S1].\nThe punishment is 14 years in jail.", RESULTS, [])
    assert "14 years" not in out["answer"]


def test_not_in_sources_abstains():
    assert verify_answer("NOT_IN_SOURCES", RESULTS, [])["abstain"]


def test_extractive_answer_is_grounded():
    res = [dict(r, act_label=r["act"], unit="Section") for r in RESULTS]
    out = verify_answer(extractive_answer(res, []), res, [])
    assert not out["abstain"] and out["removed"] == 0


# Pipeline (fast mode, no model, no network for English)
class _FakeRetriever:
    embedder = None

    def search(self, query, k=5):
        res = [dict(r, act_label=r["act"], act_name=r["act"], unit="Section", exact=False, id=f"{r['act']}-{r['section']}")
               for r in RESULTS]
        return {"results": res, "notes": [], "period": None, "confidence": 0.9, "low_confidence": False}


def test_pipeline_fast_answer_is_grounded():
    from nyaya.llm import ExtractiveBackend
    from nyaya.pipeline import NyayaPipeline
    r = NyayaPipeline(_FakeRetriever(), ExtractiveBackend()).answer("my cheque bounced", "en")
    assert not r["abstained"] and r["check"]["removed"] == 0
    assert "«" not in r["answer"] and "[S1]" in r["answer"]


def test_nonsense_questions_refused_real_ones_kept():
    from nyaya.llm import ExtractiveBackend
    from nyaya.pipeline import NyayaPipeline
    from nyaya.retrieve import Retriever
    p = NyayaPipeline(Retriever(use_dense=False), ExtractiveBackend())
    for bad in ["asdf qwer zxcv", "qwerty asdfgh", "hello", "hi there", "lol"]:
        assert not p.looks_like_question(bad), bad
    for good in ["divorce", "bail", "cheque bounced", "IPC 420", "What is BNS 103?",
                 "My landlord is not returning my deposit."]:
        assert p.looks_like_question(good), good
    assert p.answer("asdf qwer zxcv", "en")["error"] == "ask_unclear"
    assert p.answer("<script>alert(1)</script>", "en")["error"] == "ask_unclear"   # tags are stripped first


def test_pipeline_empty_question():
    from nyaya.llm import ExtractiveBackend
    from nyaya.pipeline import NyayaPipeline
    assert "error" in NyayaPipeline(_FakeRetriever(), ExtractiveBackend()).answer("  ", "en")


# Translation locking (offline)
def test_lock_unlock_roundtrip():
    text = "Under BNS Section 318(4) [S1] and IPC Section 420 [S2], call 15100."
    locked, saved = lock(text)
    assert "318" not in locked and "[S1]" not in locked
    assert unlock(locked, saved) == text
    assert protected_ok(text, unlock(locked, saved))


# Interface text
def test_hindi_reviewed_covers_every_key():
    from nyaya.ui_text import EN, EXAMPLES, REVIEWED
    assert set(REVIEWED["hi"]["text"]) == set(EN)
    assert len(REVIEWED["hi"]["examples"]) == len(EXAMPLES)


def test_no_stray_colons_in_translated_text():
    # a lone " : " is left behind when the translator moves a protected colon
    import json
    from nyaya.ui_text import EN
    with open(os.path.join(os.path.dirname(__file__), "..", "nyaya", "ui_text.json"), encoding="utf-8") as f:
        langs = json.load(f)
    for lang, d in langs.items():
        for k, v in d["text"].items():
            assert " : " not in v or " : " in EN.get(k, ""), (lang, k)


def test_every_form_field_has_text():
    from nyaya.drafting import RELATIONS
    from nyaya.ui_text import EN
    for spec in DOC_TYPES.values():
        for key, _, _ in spec["fields"]:
            assert f"f_{key}" in EN, key
        for opts in spec.get("options", {}).values():
            for o in opts:
                assert f"o_{o}" in EN, o
    assert all(f"o_{r}" in EN for r in RELATIONS)
    assert all(f"d_{k}" in EN for k in DOC_TYPES)


# Drafting (more in tests/test_drafting.py)
def test_template_law_exists(chunks):
    for spec in DOC_TYPES.values():
        for key in spec["law"]:
            assert key in chunks, key


def test_template_claims_match_law(chunks):
    assert "by post, to the Superintendent of Police" in chunks[("BNSS", "173")]["text"]
    assert "given forthwith, free of cost" in chunks[("BNSS", "173")]["text"]
    assert "not be required to give any reason" in chunks[("RTI", "6")]["text"]
    assert "forty-eight hours" in chunks[("RTI", "7")]["text"]
    assert "fifteen days" in chunks[("NIA", "138")]["text"]
    assert "within one month" in chunks[("NIA", "142")]["text"]
    assert "two years" in chunks[("CPA", "69")]["text"]
    assert "thirty days" in chunks[("RTI", "7")]["text"]
    assert "below poverty line" in chunks[("RTI", "7")]["text"]
    assert "all citizens shall have the right to information" in chunks[("RTI", "3")]["text"]
    assert "condone" in chunks[("CPA", "69")]["text"] or "sufficient cause" in chunks[("CPA", "69")]["text"]


def test_draft_guard_blocks_invented_details():
    facts = "I lent money to my friend Ravi in March. He gave me a cheque."
    assert adds_nothing_new(facts, "I lent money to Ravi in March. He then gave me a cheque.")
    assert not adds_nothing_new(facts, "I lent Rs. 50000 to Ravi in March.")
    assert not adds_nothing_new(facts, "I lent money to Ravi Kumar of Pune in March.")
