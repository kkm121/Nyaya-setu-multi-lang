# Training Data Builder
# Makes grounded examples in the exact format the app uses:
# system prompt + numbered sources + question  ->  cited answer (or NOT_IN_SOURCES)

import json
import os
import random
import re

from nyaya.corpus import ROOT, RAW_DIR
from nyaya.prompts import SYSTEM_PROMPT, build_messages
from nyaya.retrieve import Retriever, tokenize
from nyaya.verify import numbers_match, overlap

OUT = os.path.join(ROOT, "data", "train", "sft.jsonl")
EVAL_Q = os.path.join(ROOT, "eval", "questions.jsonl")
N_SOURCES = 4
random.seed(42)

NEXT_STEPS = {
    "BNS": ["Write down what happened, with dates, while you remember it.",
            "You can report it at the nearest police station.",
            "Call the free legal aid helpline 15100 for help from a lawyer."],
    "BNSS": ["Keep copies of every paper the police or court gives you.",
             "Ask a lawyer to check the exact time limits in your case.",
             "Call the free legal aid helpline 15100 if you cannot afford a lawyer."],
    "BSA": ["Keep the original record or device safely; do not edit it.",
            "Make copies and note the date and source of each piece of evidence.",
            "Discuss with your lawyer how to present it in court."],
    "IPC": ["Check the date of the event: the old law applies only to events before 1 July 2024.",
            "Ask a lawyer to confirm the matching new section if your case is recent.",
            "Call the free legal aid helpline 15100 for help."],
}


def tag_answer(answer, tag):
    # swap the dataset's own source note for our [S#] tag
    answer = re.sub(r"\[Source:[^\]]*\]", "", answer).strip()
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    if not sents:
        return None
    short = sents[0].rstrip(".") + f". {tag}"
    bullets = [f"- {s.rstrip('.')}. {tag}" for s in sents[1:4]]
    return short, bullets


def format_answer(short, bullets, steps):
    out = [f"**In short:** {short}"]
    if bullets:
        out += ["", "**What the law says:**"] + bullets
    out += ["", "**What you can do now:**"] + [f"- {s}" for s in steps]
    return "\n".join(out)


def pick_sources(retriever, question, gold_idx, exclude_acts=()):
    # gold section + nearby distractors, in random order
    scores = retriever.bm25.get_scores(tokenize(question))
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    picked, seen = [], {(retriever.chunks[i]["act"], retriever.chunks[i]["section"]) for i in gold_idx}
    for i in order:
        c = retriever.chunks[i]
        key = (c["act"], c["section"])
        if key in seen or c["act"] in exclude_acts:
            continue
        seen.add(key)
        picked.append(i)
        if len(picked) >= N_SOURCES - len(gold_idx):
            break
    items = [(i, True) for i in gold_idx] + [(i, False) for i in picked]
    random.shuffle(items)
    return items


def example(retriever, question, items, answer_fn, notes=(), period=None):
    results = [dict(retriever.chunks[i]) for i, _ in items]
    gold_pos = [n for n, (_, g) in enumerate(items, 1) if g]
    answer = answer_fn(gold_pos)
    if answer is None:
        return None
    msgs = build_messages(question, results, list(notes), period)
    return {"messages": msgs + [{"role": "assistant", "content": answer}]}


def grounded(answer_text, source_text, min_overlap=0.30):
    # keep only answers that really come from the section text
    clean = re.sub(r"\[Source:[^\]]*\]", "", answer_text)
    return overlap(clean, source_text) >= min_overlap and not numbers_match(clean, source_text)


def main():
    r = Retriever(use_dense=False)
    eval_qs = [json.loads(l)["q"].lower() for l in open(EVAL_Q, encoding="utf-8")]
    eval_tokens = [set(tokenize(q)) for q in eval_qs]

    def near_eval(q):
        t = set(tokenize(q))
        return any(len(t & e) / max(len(t | e), 1) > 0.6 for e in eval_tokens)

    rows, stats = [], {"qa": 0, "qa_dropped": 0, "mapping": 0, "abstain": 0, "near_eval_dropped": 0}

    # 1. BNS / BNSS / BSA question-answer pairs
    for line in open(os.path.join(RAW_DIR, "legal_qa_bns_bnss_bsa.jsonl"), encoding="utf-8"):
        q = json.loads(line)
        act = q["act"].split()[0]
        gold = r.lookup(act, q["section_number"])
        if not gold:
            stats["qa_dropped"] += 1
            continue
        src_text = " ".join(r.chunks[i]["text"] for i in gold)
        if not grounded(q["answer"], src_text):
            stats["qa_dropped"] += 1
            continue
        if near_eval(q["question"]):
            stats["near_eval_dropped"] += 1
            continue
        gold = gold[:1] if len(gold) == 1 else [max(gold, key=lambda i: overlap(q["answer"], r.chunks[i]["text"]))]
        items = pick_sources(r, q["question"], gold)
        steps = random.sample(NEXT_STEPS[act], k=min(2, len(NEXT_STEPS[act])))

        def ans(gp, q=q, steps=steps):
            t = tag_answer(q["answer"], f"[S{gp[0]}]")
            return format_answer(t[0], t[1], steps) if t else None

        ex = example(r, q["question"], items, ans)
        if ex:
            rows.append(ex)
            stats["qa"] += 1

        # 2. same question with the right section hidden -> must say NOT_IN_SOURCES
        if random.random() < 0.10:
            items = pick_sources(r, q["question"], [], exclude_acts=(act,))
            ex = example(r, q["question"], items, lambda gp: "NOT_IN_SOURCES")
            if ex:
                rows.append(ex)
                stats["abstain"] += 1

    # 3. old law -> new law questions from the mapping table
    templates = ["What is {old} {num} called under the new law?",
                 "{old} section {num} is now which section?",
                 "My case was filed under {old} {num}. What is the new section?"]
    for key, maps in r.mapping.items():
        old, num = key.split("-", 1)
        if old not in ("IPC", "CRPC", "IEA") or random.random() > 0.55:
            continue
        old_label = {"IPC": "IPC", "CRPC": "CrPC", "IEA": "Evidence Act"}[old]
        question = random.choice(templates).format(old=old_label, num=num)
        if near_eval(question):
            stats["near_eval_dropped"] += 1
            continue
        old_ids = r.lookup(old, num)[:1]
        new_ids = [r.lookup(m["to_act"], m["to_section"])[:1] for m in maps if m["to_section"]]
        new_ids = [x[0] for x in new_ids if x][:2]
        if not old_ids:
            continue
        items = [(i, True) for i in old_ids + new_ids]
        random.shuffle(items)
        results = [r.chunks[i] for i, _ in items]

        def ans(gp, maps=maps, results=results, old_label=old_label, num=num, old=old):
            pos = {(c["act"], c["section"]): n for n, c in enumerate(results, 1)}
            o = pos[(old, r.chunks[old_ids[0]]["section"])]
            m = maps[0]
            if m["status"] == "Deleted" or not m["to_section"]:
                return (f"**In short:** {old_label} Section {num} has no matching section in the new law; it was dropped [S{o}].\n\n"
                        f"**What the law says:**\n- {m['note']} [S{o}]\n\n**What you can do now:**\n"
                        "- For events before 1 July 2024, the old section can still apply.\n- Ask a lawyer how this affects your case.")
            t = pos.get((m["to_act"], str(m["to_section"]).upper()))
            if t is None:
                return None
            new_label = {"BNS": "BNS", "BNSS": "BNSS", "BSA": "BSA"}[m["to_act"]]
            sec = m["to_sub"] if m.get("to_sub") and str(m["to_sub"]).startswith(str(m["to_section"])) else m["to_section"]
            return (f"**In short:** {old_label} Section {num} now corresponds to {new_label} Section {sec} [S{t}].\n\n"
                    f"**What the law says:**\n- The old section was \"{r.chunks[old_ids[0]]['title']}\" [S{o}].\n"
                    f"- The new section is \"{m['to_title']}\" [S{t}].\n\n**What you can do now:**\n"
                    "- Events before 1 July 2024 are still dealt with under the old law.\n"
                    "- For events on or after 1 July 2024, the new section applies.")

        ex = example(r, question, items, ans, notes=maps[:2])
        if ex:
            rows.append(ex)
            stats["mapping"] += 1

    # 4. v1 data (Constitution / IPC Q&A): kept only if search finds a section that clearly supports it
    v1_path = os.path.join(ROOT, "data", "ipc_dataset.json")
    if os.path.exists(v1_path):
        v1 = json.load(open(v1_path, encoding="utf-8"))
        random.shuffle(v1)
        stats["v1"] = stats["v1_dropped"] = 0
        for d in v1[:7000]:
            question = re.sub(r"^Indian Legal Query:\s*", "", d["instruction"]).strip()
            answer = d["output"].strip()
            if len(answer) < 40 or len(answer) > 900 or near_eval(question):
                continue
            scores = r.bm25.get_scores(tokenize(question + " " + answer))
            best = int(scores.argmax())
            c = r.chunks[best]
            if c["act"] not in ("COI", "IPC", "CRPC", "IEA") or not grounded(answer, c["text"] + " " + c["title"], 0.5):
                stats["v1_dropped"] += 1
                continue
            items = pick_sources(r, question, [best])
            steps = (["Free legal aid is available on 15100."] if c["act"] == "COI"
                     else random.sample(NEXT_STEPS.get(c["act"], NEXT_STEPS["IPC"]), 2))

            def ans(gp, answer=answer, steps=steps):
                t = tag_answer(answer, f"[S{gp[0]}]")
                return format_answer(t[0], t[1], steps) if t else None

            ex = example(r, question, items, ans)
            if ex:
                rows.append(ex)
                stats["v1"] += 1

    random.shuffle(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("[INFO] Saved", len(rows), "examples to", OUT)
    print("[INFO]", stats)


if __name__ == "__main__":
    main()
