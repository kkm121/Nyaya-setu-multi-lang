# Answer Checking
# Every legal sentence must cite a real source, name only retrieved sections,
# and actually match the text of the source it cites.

import re

from .retrieve import tokenize

CITE = re.compile(r"\[S(\d+)\]")
SECTION_MENTION = re.compile(r"\b(?:sections?|articles?|s\.)\s*(\d{1,3}[A-Z]{0,2})(?:\s*\(\d+\))?", re.IGNORECASE)
LEGAL_WORDS = re.compile(
    r"\b(section|article|act|sanhita|adhiniyam|code|punish|imprison|fine|bail|offence|offense|court|"
    r"magistrate|police|arrest|liable|shall|right|law|penalty|jail|years?|complaint|notice|commission)\b",
    re.IGNORECASE)
MIN_OVERLAP = 0.30


def split_sentences(text):
    # keep line structure (headings and bullets), split long lines into sentences
    out = []
    for line in text.split("\n"):
        # bullets are one claim each, so they are never split
        if not line.strip() or re.match(r"^\s*([-*•]|\d+[.)])\s", line):
            out.append(line)
            continue
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z*\-ऀ-෿])", line)
        out.extend(parts)
    return out


NUM_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
             "eight": "8", "nine": "9", "ten": "10", "fifteen": "15", "twenty": "20", "thirty": "30",
             "sixty": "60", "ninety": "90", "hundred": "100", "twice": "2x", "double": "2x", "thrice": "3x"}


def numbers_in(text):
    text = CITE.sub("", text)
    text = SECTION_MENTION.sub("", text)
    nums = set(re.findall(r"\b\d+\b", text))
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in NUM_WORDS:
            nums.add(NUM_WORDS[w])
    return nums


def numbers_match(sentence, source_text):
    # every number in the sentence must also be in the source
    missing = numbers_in(sentence) - numbers_in(source_text)
    return sorted(missing)


# plain linking words that do not carry legal meaning
FILLER = set("most relevant here law laws says say short what you your can could also this these those "
             "means mean about there their they will would should must case cases".split())


def source_text(r):
    return f"{r.get('act_label', '')} {r.get('act_name', '')} {r.get('unit', '')} {r['section']} {r['title']} {r['text']}"


def overlap(sentence, source):
    s = set(tokenize(CITE.sub("", sentence))) - FILLER
    if not s:
        return 1.0
    src = set(tokenize(source))
    return len(s & src) / len(s)


def allowed_sections(results, notes):
    allowed = {str(r["section"]).upper() for r in results}
    for n in notes:
        if n.get("to_section"):
            allowed.add(str(n["to_section"]).upper())
    # sections quoted inside the source text are fine too (e.g. "section 64")
    for r in results:
        allowed.update(m.upper() for m in SECTION_MENTION.findall(r["text"]))
    return allowed


def verify_answer(answer, results, notes, question=""):
    n = len(results)
    allowed = allowed_sections(results, notes)
    allowed.update(m.upper() for m in SECTION_MENTION.findall(question))
    kept, report = [], []
    claims = supported = removed = 0

    for sent in split_sentences(answer):
        if not sent.strip():
            kept.append(sent)
            continue
        is_heading = sent.strip().startswith("**") and sent.strip().endswith(":**")
        cites = [int(x) for x in CITE.findall(sent)]
        bad = [c for c in cites if c < 1 or c > n]
        good = [c for c in cites if 1 <= c <= n]
        mentions = [m.upper() for m in SECTION_MENTION.findall(sent)]
        unknown = [m for m in mentions if m not in allowed]
        legal = bool(LEGAL_WORDS.search(sent)) and not is_heading

        # 1. drop sentences that name a section we never retrieved
        if unknown:
            removed += 1
            report.append({"text": sent, "status": "removed", "why": f"mentions section {', '.join(unknown)} not in sources"})
            continue

        # 2. remove citation tags that point to nothing
        for b in bad:
            sent = sent.replace(f"[S{b}]", "")

        if good:
            claims += 1
            src = " ".join(source_text(results[c - 1]) for c in good)
            best = max(overlap(sent, source_text(results[c - 1])) for c in good)
            # mapping notes come from the official concordance table, so they count as a source too
            wrong_nums = numbers_match(sent, src + " " + " ".join(n.get("note", "") for n in notes))
            if wrong_nums:
                report.append({"text": sent, "status": "weak", "why": f"number {', '.join(wrong_nums)} not in source"})
                sent = sent + " ⚠️"
            elif best >= MIN_OVERLAP:
                supported += 1
                report.append({"text": sent, "status": "supported", "score": round(best, 2)})
            else:
                report.append({"text": sent, "status": "weak", "score": round(best, 2)})
                sent = sent + " ⚠️"
        elif legal and (mentions or bad or numbers_in(sent)):
            # a legal claim with no valid source
            removed += 1
            report.append({"text": sent, "status": "removed", "why": "legal claim without a valid source"})
            continue
        kept.append(sent)

    clean = "\n".join(_rejoin(kept)).strip()
    return {
        "answer": clean,
        "claims": claims,
        "supported": supported,
        "removed": removed,
        "report": report,
        "abstain": should_abstain(answer, claims, supported, removed),
    }


def _rejoin(parts):
    # put sentences from the same line back together
    lines, buf = [], []
    for p in parts:
        if not p.strip():
            if buf:
                lines.append(" ".join(buf))
                buf = []
            lines.append("")
        elif p.lstrip().startswith(("-", "*", "•")) or re.match(r"^\s*\d+[.)]", p):
            if buf:
                lines.append(" ".join(buf))
            buf = [p]
        else:
            buf.append(p.strip())
    if buf:
        lines.append(" ".join(buf))
    return lines


def should_abstain(raw, claims, supported, removed):
    if "NOT_IN_SOURCES" in raw:
        return True
    if claims == 0:
        return True
    if removed > claims:
        return True
    return supported / max(claims, 1) < 0.5


def used_sources(answer, n):
    return sorted({int(x) for x in CITE.findall(answer) if 1 <= int(x) <= n})
