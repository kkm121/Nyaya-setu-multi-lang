# Evaluation
# Usage:
#   python -m eval.run_eval                      retrieval only (fast)
#   python -m eval.run_eval --langs hi,ta        retrieval for questions in other languages
#   python -m eval.run_eval --e2e --backend llamacpp --limit 20   full answers with a model

import argparse
import json
import os
import time

from nyaya.corpus import ROOT
from nyaya.retrieve import Retriever

EVAL_DIR = os.path.join(ROOT, "eval")
QUESTIONS = os.path.join(EVAL_DIR, "questions.jsonl")


def load(path=QUESTIONS):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def translated_questions(lang):
    # hand-written Hindi set, or machine-translated copies of the English set (cached)
    from nyaya.translate import translate
    if lang.endswith("_native"):
        return load(os.path.join(EVAL_DIR, f"questions_{lang}.jsonl"))
    path = os.path.join(EVAL_DIR, f"questions_{lang}.jsonl")
    if os.path.exists(path):
        return load(path)
    out = []
    for q in load():
        out.append(dict(q, q=translate(q["q"], lang, "en"), q_en=q["q"]))
        time.sleep(0.2)
    with open(path, "w", encoding="utf-8") as f:
        for q in out:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    return out


def retrieval_scores(retriever, questions, k=5, to_en=False, lang="auto"):
    from nyaya.translate import to_english
    hits = rr = n = 0
    abstain_ok = abstain_n = wrongly_low = 0
    misses = []
    for q in questions:
        text = to_english(q["q"], lang) if to_en else q["q"]
        found = retriever.search(text, k=k)
        ids = [f"{r['act']}-{r['section']}" for r in found["results"]]
        if not q["gold"]:
            abstain_n += 1
            abstain_ok += found["low_confidence"]
            continue
        n += 1
        wrongly_low += found["low_confidence"]
        rank = next((i for i, x in enumerate(ids) if x in q["gold"]), None)
        if rank is not None:
            hits += 1
            rr += 1 / (rank + 1)
        else:
            misses.append((q["id"], text[:70], ids[:3]))
    return {"recall@%d" % k: round(hits / n, 3), "mrr": round(rr / n, 3), "n": n,
            "low_confidence_on_unanswerable": f"{abstain_ok}/{abstain_n}",
            "low_confidence_on_answerable": f"{wrongly_low}/{n}", "misses": misses}


def e2e_scores(pipeline, questions, lang="en", rows_path=None):
    # each answer is saved as soon as it is made, so a crash (e.g. out of memory) can resume
    rows = []
    if rows_path and os.path.exists(rows_path):
        rows = [json.loads(l) for l in open(rows_path, encoding="utf-8") if l.strip()]
    done = {x["id"] for x in rows}
    for q in questions:
        if q["id"] in done:
            continue
        r = pipeline.answer(q["q"], lang)
        cited_ids = [f"{s['act']}-{s['section']}" for i, s in enumerate(r["sources"], 1) if i in r["cited"]]
        rows.append({
            "id": q["id"],
            "answerable": bool(q["gold"]),
            "abstained": r["abstained"],
            "cited_gold": any(c in q["gold"] for c in cited_ids),
            "claims": r["check"]["claims"],
            "supported": r["check"]["supported"],
            "removed": r["check"]["removed"],
            "seconds": r["seconds"],
            "quality": r["translation_quality"],
        })
        if rows_path:
            with open(rows_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rows[-1]) + chr(10))
        print(f"  {q['id']}: abstain={r['abstained']} cited={cited_ids[:3]} "
              f"supported={r['check']['supported']}/{r['check']['claims']} removed={r['check']['removed']} {r['seconds']}s")
    ids = {q["id"] for q in questions}
    rows = [x for x in rows if x["id"] in ids]
    ans = [x for x in rows if x["answerable"]]
    una = [x for x in rows if not x["answerable"]]
    claims = sum(x["claims"] for x in rows)
    return {
        "answered_with_gold_citation": f"{sum(x['cited_gold'] and not x['abstained'] for x in ans)}/{len(ans)}",
        "wrongly_abstained": f"{sum(x['abstained'] for x in ans)}/{len(ans)}",
        "correctly_abstained_unanswerable": f"{sum(x['abstained'] for x in una)}/{len(una)}",
        "supported_claim_rate": round(sum(x["supported"] for x in rows) / max(claims, 1), 3),
        "sentences_removed_by_checker": sum(x["removed"] for x in rows),
        "avg_seconds": round(sum(x["seconds"] for x in rows) / max(len(rows), 1), 1),
        "avg_translation_quality": round(sum(x["quality"] for x in rows) / max(len(rows), 1), 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", default="")
    ap.add_argument("--e2e", action="store_true")
    ap.add_argument("--backend", default="extractive")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--no-glossary", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    retriever = Retriever(use_dense=True, use_rerank=args.rerank, use_glossary=not args.no_glossary)
    report = {"date": time.strftime("%Y-%m-%d %H:%M"), "rerank": args.rerank, "glossary": not args.no_glossary}

    qs = load()
    if args.limit:
        qs = qs[:args.limit] + [q for q in load() if not q["gold"]]
    report["en"] = retrieval_scores(retriever, qs)
    print("[EN] retrieval:", {k: v for k, v in report["en"].items() if k != "misses"})

    for lang in [l for l in args.langs.split(",") if l]:
        tq = translated_questions(lang)
        if args.limit and not lang.endswith("_native"):
            tq = [q for q in tq if q["id"] in {x["id"] for x in qs}]
        report[lang] = retrieval_scores(retriever, tq, to_en=True, lang=lang.split("_")[0])
        print(f"[{lang.upper()}] retrieval:", {k: v for k, v in report[lang].items() if k != "misses"})

    if args.e2e:
        from nyaya.llm import load_backend
        from nyaya.pipeline import NyayaPipeline
        pipe = NyayaPipeline(retriever, load_backend(args.backend))
        report["e2e_en"] = e2e_scores(pipe, qs, rows_path=args.out.replace(".json", "_rows.jsonl") if args.out else None)
        print("[E2E EN]", report["e2e_en"])
        for lang in [l for l in args.langs.split(",") if l]:
            tq = [q for q in translated_questions(lang) if q["id"] in {x["id"] for x in qs}]
            report[f"e2e_{lang}"] = e2e_scores(pipe, tq, lang)
            print(f"[E2E {lang.upper()}]", report[f"e2e_{lang}"])

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print("[INFO] Saved", args.out)


if __name__ == "__main__":
    main()
