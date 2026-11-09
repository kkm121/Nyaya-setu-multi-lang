# Query Understanding
# Finds section numbers, act names and dates in a question.

import re
from datetime import date

from .acts import NEW_LAW_START

# Words people use for each act (lower case)
ACT_ALIASES = {
    "BNS": ["bns", "bharatiya nyaya sanhita", "nyaya sanhita"],
    "BNSS": ["bnss", "bharatiya nagarik suraksha sanhita", "nagarik suraksha sanhita"],
    "BSA": ["bsa", "bharatiya sakshya adhiniyam", "sakshya adhiniyam"],
    "IPC": ["ipc", "i.p.c", "indian penal code", "penal code"],
    "CRPC": ["crpc", "cr.p.c", "cr. p. c", "code of criminal procedure", "criminal procedure code"],
    "IEA": ["evidence act", "indian evidence act", "iea"],
    "COI": ["constitution", "article"],
    "NIA": ["ni act", "n.i. act", "negotiable instruments", "cheque", "cheques", "cheque bounce", "cheque bounced", "bounced cheque",
            "cheque dishonour", "cheque dishonoured", "dishonour of cheque", "cheque return", "cheque returned"],
    "CPA": ["consumer protection act", "consumer act", "cpa 2019"],
    "RTI": ["rti", "right to information"],
    "IT_ACT": ["it act", "information technology act"],
    "DV": ["domestic violence act", "dv act", "pwdva"],
    "HMA": ["hindu marriage act", "hma"],
    "MVA": ["motor vehicles act", "mv act"],
    "TPA": ["transfer of property act", "tp act"],
    "DPA": ["dowry prohibition act"],
    "POCSO": ["pocso"],
    "POSH": ["posh act", "sexual harassment of women at workplace"],
    "SCST": ["sc/st act", "atrocities act", "sc st act"],
    "CPC": ["cpc", "code of civil procedure", "civil procedure code"],
    "ICA": ["contract act", "indian contract act"],
    "LA": ["limitation act"],
    "MWPSC": ["senior citizens act", "maintenance of parents"],
    "NDPS": ["ndps"],
    "RERA": ["rera"],
    "DPDPA": ["dpdp", "data protection act"],
}

# "section 302", "sec. 302", "s. 302", "u/s 302", "धारा 302", "article 21"
SECTION_WORDS = r"(?:sections?|secs?\.?|s\.|u/s|under section|dhara|धारा|कलम|பிரிவு|సెక్షన్|ವಿಭಾಗ|ধারা|કલમ|articles?|art\.)"
NUM = r"(\d{1,3}[A-Z]{0,2})"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


# Everyday words -> the words the law uses (added to the search, never shown as law)
LAY_TERMS = {
    r"\bfir\b|first information report|police complaint": "information relating to commission of cognizable offence officer in charge of police station",
    r"\bzero fir\b": "information cognizable offence irrespective of area where offence is committed",
    r"anticipatory bail|bail before arrest|fear (of )?(being )?arrest|apprehend\w* arrest": "direction for grant of bail to person apprehending arrest",
    r"\bbail\b": "bail bailable offence release on bail",
    r"\bstole|\bstolen|\bsteal|\bthief|\bpickpocket": "theft dishonestly taking movable property",
    r"\bsnatch\w*": "snatching theft suddenly or quickly or forcibly seizes",
    r"\bslap\w*|\bbeat\w*|\bhit me|\bpunch\w*|\battack\w*": "voluntarily causing hurt",
    r"threaten\w*|\bthreat\b|intimidat\w*": "criminal intimidation threat injury",
    r"broke into|break into|burglar\w*|house ?break\w*": "house-breaking house-trespass",
    r"cheat\w*|fraud\w*|\bscam\w*|duped|conned": "cheating dishonestly inducing deliver property",
    # fake job offers: "took money from me ... promised me a job ... disappeared"
    r"(took|taken|collected|paid)\b.{0,30}\bmoney\b.{0,80}\b(job|visa|admission|loan)\b|promis\w*\b.{0,20}\bjob\b":
        "cheating dishonestly inducing deliver property",
    # words may sit apart: "the cheque my friend gave me bounced"
    r"cheque\b.{0,60}\b(bounc\w*|return\w*|dishonou?r\w*)|bounced cheque": "dishonour of cheque for insufficiency of funds",
    r"defam\w*|false stor\w*|reputation|insult\w* me": "defamation harm reputation imputation",
    r"stalk\w*|follow\w* me": "stalking follows woman contact",
    r"\bdowry\b": "dowry demand cruelty by husband or relative",
    # translators sometimes turn "beats me" into "kills me" or "hits me", and "protection order" into "security order"
    r"husband\b.{0,20}\b(beats?|hits?|kills?|assaults?|tortures?|abuses?) me|wife beat\w*|domestic violence|beats me|"
    r"(protection|security|safety|defen[cs]e) order": "domestic violence protection order cruelty aggrieved person Magistrate",
    r"\bdivorce\b": "dissolution of marriage decree of divorce grounds",
    r"maintenance|does not give money|not paying (for )?(me|us|the children)": "order for maintenance of wives children and parents",
    r"\bhacked\b|\bhack\w*|identity theft|fake profile": "identity theft computer resource password electronic signature",
    r"\botp\b|bank fraud call|online fraud|upi fraud": "cheating by personation using computer resource",
    r"drunk driv\w*|drink(ing)? and driv\w*": "driving by a drunken person alcohol",
    r"without (a )?(driving )?licen[cs]e": "necessity for driving licence",
    r"hit and run|ran away after (the )?accident|driver ran away": "causing death by negligence escapes",
    r"defective|stopped working|refund|replace\w*|deficien\w* in service": "consumer complaint defect deficiency District Commission",
    r"\brti\b": "right to information request public information officer",
    r"\blegal aid\b|free lawyer": "legal services entitlement criteria",
    r"tenan\w*|landlord|rent\w*": "lease of immovable property notice tenant lessor lessee",
    r"whatsapp|screenshot|email evidence|electronic evidence|cctv": "electronic record admissibility",
    r"confession": "confession to police officer",
    r"arrest\w* without (a )?warrant": "police may arrest without warrant",
    r"\bkidnap\w*": "kidnapping abduction",
    r"sexual(ly)? harass\w*|eve[- ]teas\w*|touched me": "sexual harassment physical contact advances",
    r"\bextort\w*|\bhafta\b|demanding money": "extortion fear of injury deliver property",
    r"\bsuicide\b": "abetment of suicide",
    r"\bcaste\b": "scheduled castes scheduled tribes atrocities",
}


# American spellings (often produced by translators) -> the spelling Indian law uses
SPELLING = [
    (r"\boffense(s)?\b", r"offence\1"), (r"\bdefense(s)?\b", r"defence\1"),
    (r"\blicense(s|d)?\b", r"licence\1"), (r"\blabor\b", "labour"), (r"\bjudgment\b", "judgement"),
]
CHEQUE_CONTEXT = re.compile(r"bounce|bank|dishono|payment|paid|account|issued|gave|given|signed|amount", re.IGNORECASE)


def normalize(text):
    for pattern, repl in SPELLING:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    # "check" means a cheque only when money is being talked about
    if CHEQUE_CONTEXT.search(text):
        text = re.sub(r"\bchecks?\b", lambda m: "cheques" if m.group(0).lower().endswith("s") else "cheque",
                      text, flags=re.IGNORECASE)
    return text


def expand_lay_terms(text):
    low = text.lower()
    extra = [legal for pattern, legal in LAY_TERMS.items() if re.search(pattern, low)]
    return " ".join(extra)


def find_acts(text):
    low = " " + text.lower() + " "
    found = []
    for code, words in ACT_ALIASES.items():
        for w in words:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
                found.append(code)
                break
    # "article" alone means the constitution only when no other act is named
    if "COI" in found and len(found) > 1 and "constitution" not in low:
        found.remove("COI")
    return found


def find_section_refs(text):
    """Returns list of (act or None, section number)."""
    refs = []
    acts_pattern = "|".join(sorted({re.escape(w) for ws in ACT_ALIASES.values() for w in ws}, key=len, reverse=True))

    # "section 302 of IPC" / "section 302 IPC"
    for m in re.finditer(SECTION_WORDS + r"\s*" + NUM + r"(?:\s*\(\d+\))?\s*(?:of\s+(?:the\s+)?)?(" + acts_pattern + r")?",
                         text, flags=re.IGNORECASE):
        word = m.group(0).lower()
        act = _alias_to_code(m.group(2)) if m.group(2) else None
        if act is None and word.startswith(("art", "article")):
            act = "COI"
        refs.append((act, m.group(1).upper()))

    # "IPC 302" / "302 IPC" / "498A IPC"
    for m in re.finditer(r"(?<![\w.])(" + acts_pattern + r")\s*" + NUM + r"(?![\w])", text, flags=re.IGNORECASE):
        refs.append((_alias_to_code(m.group(1)), m.group(2).upper()))
    for m in re.finditer(r"(?<![\w.])" + NUM + r"\s*(?:of\s+)?(" + acts_pattern + r")(?![a-z])", text, flags=re.IGNORECASE):
        refs.append((_alias_to_code(m.group(2)), m.group(1).upper()))

    # keep order, drop repeats; prefer refs that name an act
    seen, out = set(), []
    for act, num in refs:
        if (act, num) in seen:
            continue
        seen.add((act, num))
        out.append((act, num))
    named = {n for a, n in out if a}
    return [(a, n) for a, n in out if a or n not in named]


def _alias_to_code(word):
    w = word.lower().strip()
    for code, words in ACT_ALIASES.items():
        if w in words:
            return code
    return None


def find_dates(text):
    dates = []
    for d, m, y in re.findall(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", text):
        try:
            dates.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for mon, y in re.findall(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s+(\d{4})\b", text, flags=re.IGNORECASE):
        dates.append(date(int(y), MONTHS[mon.lower()], 1))
    if not dates:
        for y in re.findall(r"\b(20[0-3]\d|19\d\d)\b", text):
            dates.append(date(int(y), 1, 1) if int(y) != 2024 else None)
    return [d for d in dates if d]


def law_period(text):
    """'old' if the event is before 1 July 2024, 'new' if after, None if unknown."""
    dates = find_dates(text)
    if not dates:
        return None
    start = date.fromisoformat(NEW_LAW_START)
    if all(d < start for d in dates):
        return "old"
    if all(d >= start for d in dates):
        return "new"
    return None


def analyse(text):
    return {
        "acts": find_acts(text),
        "refs": find_section_refs(text),
        "period": law_period(text),
        "legal_terms": expand_lay_terms(text),
    }
