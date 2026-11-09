# Answer Pipeline
# question -> English -> search the law -> model answer -> check citations -> user's language

import re
import time

from .forms import clean
from .llm import ExtractiveBackend, extractive_answer
from .prompts import ABSTAIN_MESSAGE, DISCLAIMER, build_messages
from .translate import back_translation_score, from_english, to_english
from .verify import used_sources, verify_answer

TOP_K = 5


def tidy_markdown(text):
    # a heading like **What the law says:** needs a blank line before it, or markdown joins it to the line above
    text = re.sub(r"\n+(\*\*[^*\n]{2,60}:\*\*)", r"\n\n\1", text)
    # "*   item" bullets from the model -> "- item"
    text = re.sub(r"(?m)^\*\s{2,}", "- ", text)
    return text.strip()


def strip_marks(text):
    return text.replace("«", "").replace("»", "")


class NyayaPipeline:
    def __init__(self, retriever, backend):
        self.retriever = retriever
        self.backend = backend

    def run(self, question, lang="en", check_translation=True, fast=False):
        """Yields (status, result) pairs so the UI can show progress."""
        t0 = time.time()
        question = clean(question, 1000)   # no HTML or control characters, at most 1000 characters
        if not question:
            yield "done", {"error": "ask_empty"}
            return

        # Input Translation
        q_en = question
        if lang != "en" or not question.isascii():
            yield "translating", None
            q_en = to_english(question, lang)

        # A real question has at least two words that appear in the law text (or a section number);
        # keyboard mash like "asdf qwer zxcv" would otherwise still get the "nearest" laws
        if not self.looks_like_question(q_en):
            yield "done", {"error": "ask_unclear"}
            return

        # Search the law
        yield "searching", None
        found = self.retriever.search(q_en, k=TOP_K)
        results, notes = found["results"], found["notes"]

        # Model answer
        yield "writing", None
        low_conf = found["low_confidence"]
        if low_conf:
            raw = "NOT_IN_SOURCES"
        elif fast or isinstance(self.backend, ExtractiveBackend):
            raw = extractive_answer(results, notes)
        else:
            # stream the draft so the user sees progress; it is checked before the final answer
            raw = ""
            for piece in self.backend.chat(build_messages(q_en, results, notes, found["period"]), stream=True):
                raw += piece
                yield "draft", raw

        # Check every citation
        yield "checking", None
        check = verify_answer(raw, results, notes, q_en)
        if check["abstain"]:
            answer_en = ABSTAIN_MESSAGE
            cited = list(range(1, len(results) + 1))
        else:
            answer_en = tidy_markdown(check["answer"])
            cited = used_sources(answer_en, len(results)) or [1]
        answer_en = answer_en + "\n\n_" + DISCLAIMER + "_"

        # Output Translation
        answer, quality = answer_en, 1.0
        if lang != "en":
            yield "translating", None
            answer, quality = from_english(answer_en, lang)
            # fast answers already show the official English text, so skip the slower back-translation check
            if check_translation and not fast and quality > 0:
                score = back_translation_score(answer_en, answer, getattr(self.retriever, "embedder", None), lang)
                quality = min(quality, score)

        answer, answer_en = strip_marks(answer), strip_marks(answer_en)
        yield "done", {
            "question": question,
            "question_en": q_en,
            "answer": answer,
            "answer_en": answer_en,
            "lang": lang,
            "translation_quality": round(quality, 2),
            "sources": results,
            "cited": cited,
            "notes": notes,
            "period": found["period"],
            "confidence": round(found["confidence"], 2),
            "abstained": check["abstain"],
            "check": {k: check[k] for k in ("claims", "supported", "removed")},
            "report": check["report"],
            "backend": "law text (fast)" if fast else getattr(self.backend, "label", self.backend.name),
            "fast": fast,
            "seconds": round(time.time() - t0, 1),
        }

    def looks_like_question(self, text):
        from .query import analyse
        from .retrieve import tokenize
        index = getattr(getattr(self.retriever, "bm25", None), "index", None)
        if index is None:
            return True
        words = [w for w in tokenize(text) if not w.isdigit()]
        known = [w for w in words if w in index]
        info = analyse(text)
        if info["refs"] or info["acts"] or info["legal_terms"]:
            return True                      # "IPC 420", "cheque bounced", "my husband beats me"
        if len(known) >= 2:
            return True
        # one-word questions ("divorce", "bail") must name a legal concept: a word from a section title
        if not hasattr(self, "_title_words"):
            chunks = getattr(self.retriever, "chunks", [])
            self._title_words = set(tokenize(" ".join(c["title"] for c in chunks)))
        return any(w in self._title_words for w in known)

    def answer(self, question, lang="en"):
        result = None
        for status, data in self.run(question, lang):  # draft updates are skipped here
            if status == "done":
                result = data
        return result
