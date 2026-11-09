# Translator Comparison: IndicTrans2 vs NLLB-200
# 1. Hand-written Hindi questions -> English -> does search still find the right law?
# 2. English legal answers -> 7 languages -> meaning kept (multilingual-e5 similarity to the English),
#    locked terms intact, speed.
# Usage: python -m eval.compare_mt

import json
import os
import time

import nyaya.translate as tr
from eval.run_eval import EVAL_DIR, load, retrieval_scores
from nyaya.retrieve import Retriever

ANSWERS = [
    "**In short:** Cheating is punished under BNS Section 318(4) [S1].\n- The punishment can be jail for up to seven years and a fine [S1].",
    "**In short:** If the police refuse to record your FIR, you can send the complaint in writing by post to the Superintendent of Police [S1].",
    "**In short:** You must send a written notice to the person who gave the cheque within 30 days of getting the bank memo [S1].\n- They then have 15 days to pay [S1].",
    "**In short:** A woman facing domestic violence can ask the Magistrate for a protection order [S1].\n- Call 15100 for free legal aid.",
    "**In short:** An arrested person must be taken before a Magistrate within 24 hours [S1].",
    "**In short:** You do not need to give any reason when you ask for information under the RTI Act [S1].",
    "**In short:** A consumer complaint must be filed within two years from the date the problem started [S1].",
    "**In short:** IPC Section 420 now corresponds to BNS Section 318(4) [S2].",
]
LANGS = ["hi", "ta", "te", "kn", "bn", "mr", "gu"]


def run(engine, retriever):
    tr._local["engine"] = engine
    tr.ENGINE = "local"
    out = {"engine": engine}

    # 1. Hindi questions written by hand
    t = time.time()
    s = retrieval_scores(retriever, load(os.path.join(EVAL_DIR, "questions_hi_native.jsonl")), to_en=True, lang="hi")
    out["hi_native_recall@5"] = s["recall@5"]
    out["hi_native_mrr"] = s["mrr"]
    out["hi_native_seconds"] = round(time.time() - t, 1)

    # 2. answers into 7 languages
    emb = retriever.embedder
    en_vecs = emb.encode(["query: " + a for a in ANSWERS], normalize_embeddings=True)
    per_lang = {}
    for lang in LANGS:
        t = time.time()
        outs = [tr.translate(a, lang, "en") for a in ANSWERS]
        secs = time.time() - t
        vecs = emb.encode(["query: " + o for o in outs], normalize_embeddings=True)
        sims = [float(a @ b) for a, b in zip(en_vecs, vecs)]
        per_lang[lang] = {
            "meaning_similarity": round(sum(sims) / len(sims), 3),
            "locked_terms_ok": f"{sum(tr.protected_ok(a, o) for a, o in zip(ANSWERS, outs))}/{len(ANSWERS)}",
            "seconds_per_answer": round(secs / len(ANSWERS), 2),
            "sample": outs[0],
        }
        print(f"[{engine}] {lang}: {per_lang[lang]['meaning_similarity']} locked {per_lang[lang]['locked_terms_ok']} "
              f"{per_lang[lang]['seconds_per_answer']}s", flush=True)
    out["languages"] = per_lang
    out["avg_meaning_similarity"] = round(sum(v["meaning_similarity"] for v in per_lang.values()) / len(LANGS), 3)
    return out


def main():
    retriever = Retriever(use_dense=True, use_rerank=True)
    report = [run("indictrans2", retriever), run(tr.NLLB, retriever)]
    path = os.path.join(EVAL_DIR, "results_mt_compare.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    for r in report:
        print(f"[RESULT] {r['engine']}: hindi recall@5 {r['hi_native_recall@5']} mrr {r['hi_native_mrr']} | "
              f"avg meaning {r['avg_meaning_similarity']}", flush=True)
    print("[INFO] Saved", path)


if __name__ == "__main__":
    main()
