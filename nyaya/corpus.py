# Corpus Builder
# Turns the raw law sections into clean, searchable chunks.

import json
import os
import re

from .acts import ACTS, OLD_TO_NEW, act_label, act_name

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
CORPUS_PATH = os.path.join(ROOT, "data", "corpus", "chunks.jsonl")
MAPPING_PATH = os.path.join(ROOT, "data", "corpus", "mapping.json")

MAX_CHARS = 1800   # long sections are split into parts
OVERLAP = 200


# Text Cleaning
def clean_text(text):
    text = text.replace("�", "—").replace(" ", " ")
    text = re.sub(r"(?<![\w(])\d{1,2}\[", "", text)   # amendment marks like 1[
    text = re.sub(r"\d?\*\*\*", "", text)               # omitted-text marks
    text = text.replace("]", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_long(text):
    if len(text) <= MAX_CHARS:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(start + MAX_CHARS, len(text))
        # try to end at a sentence or sub-section break
        if end < len(text):
            cut = max(text.rfind(". ", start, end), text.rfind("\n", start, end), text.rfind(" (", start, end))
            if cut > start + MAX_CHARS // 2:
                end = cut + 1
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - OVERLAP
    return parts


def is_empty(text):
    t = text.strip().lower()
    return len(t) < 25 or t in {"omitted.", "[omitted.]", "repealed."}


# Build Chunks
def build_chunks():
    sections = json.load(open(os.path.join(RAW_DIR, "sections.json"), encoding="utf-8"))
    chunks = []
    for s in sections:
        code = s["act_code"]
        if code not in ACTS:
            continue
        text = clean_text(s.get("text", ""))
        if is_empty(text):
            continue
        num = str(s["section_number"]).strip()
        title = clean_text(s.get("section_title", "")).rstrip(".")
        unit = "Article" if code == "COI" else "Section"
        parts = split_long(text)
        for i, part in enumerate(parts):
            chunks.append({
                "id": f"{code}-{num}" + (f"#{i + 1}" if len(parts) > 1 else ""),
                "act": code,
                "act_name": act_name(code),
                "act_label": act_label(code),
                "unit": unit,
                "section": num,
                "title": title,
                "chapter": clean_text(s.get("chapter_title", "") or ""),
                "part": i + 1,
                "parts": len(parts),
                "text": part,
                "repealed": code in OLD_TO_NEW,
            })
    return chunks


# Old <-> New Mapping
MAP_FILES = {
    ("IPC", "BNS"): "ipc_to_bns.json",
    ("CRPC", "BNSS"): "crpc_to_bnss.json",
    ("IEA", "BSA"): "iea_to_bsa.json",
    ("BNS", "IPC"): "bns_to_ipc.json",
    ("BNSS", "CRPC"): "bnss_to_crpc.json",
    ("BSA", "IEA"): "bsa_to_iea.json",
}


def build_mapping():
    mapping = {}
    for (src, dst), fname in MAP_FILES.items():
        rows = json.load(open(os.path.join(RAW_DIR, fname), encoding="utf-8"))
        for r in rows:
            key = f"{src}-{str(r['lookup_key']).upper()}"
            t = r.get("target") or {}
            mapping.setdefault(key, []).append({
                "to_act": dst,
                "to_section": t.get("section"),
                "to_sub": t.get("sub_section"),
                "to_title": t.get("title"),
                "status": r.get("status"),
                "note": clean_text(r.get("mapping_statement", "")),
            })
    return mapping


def save_all():
    os.makedirs(os.path.dirname(CORPUS_PATH), exist_ok=True)
    chunks = build_chunks()
    with open(CORPUS_PATH, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    mapping = build_mapping()
    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False)
    return len(chunks), len(mapping)


def load_chunks(path=CORPUS_PATH):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_mapping(path=MAPPING_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    n, m = save_all()
    print(f"[INFO] Saved {n} chunks and {m} mapping keys")
