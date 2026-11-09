# Document Drafting
# Six documents in the standard Indian format (legal notice / reply / police complaint /
# consumer complaint / RTI). Every field is checked by nyaya/forms.py first; the legal wording
# comes from fixed templates, and the person's own facts fill the numbered paragraphs.
# Nothing is invented: anything missing stops the document with a clear message.

import os
import re
import tempfile
from datetime import timedelta

from . import forms as F
from .prompts import DRAFT_SYSTEM_PROMPT, DRAFT_TEMPLATE

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

RELATIONS = ["S/o", "D/o", "W/o", "C/o"]
DAYS = ["7", "15", "30"]

# Field Lists
# (key, kind, required). Labels live in FORM_TEXT below (key "f_<key>"), so they can be translated.
PERSON = [("s_name", "name", True), ("s_rel", "relation", False), ("s_relname", "name", False),
          ("s_age", "age", False), ("s_address", "address", True), ("s_phone", "phone", False),
          ("s_email", "email", False)]
OTHER = [("r_name", "name", True), ("r_rel", "relation", False), ("r_relname", "name", False),
         ("r_address", "address", True)]

DOC_TYPES = {
    "police_complaint": {
        "fields": [("s_name", "name", True), ("s_rel", "relation", False), ("s_relname", "name", False),
                   ("s_age", "age", False), ("s_address", "address", True), ("s_phone", "phone", True),
                   ("s_email", "email", False),
                   ("station", "place", True), ("district", "place", True),
                   ("offence", "select", True), ("incident_date", "date", True), ("incident_time", "time", False),
                   ("incident_place", "place", True), ("accused", "short", False), ("witnesses", "short", False),
                   ("facts", "text", True), ("evidence", "multi", False), ("place", "place", True)],
        "options": {"offence": ["theft", "cheating", "threat", "assault", "harassment", "cyber", "missing", "other"],
                    "evidence": ["photos", "videos", "screenshots", "medical", "bills", "cctv"]},
        "law": [("BNSS", "173")],
    },
    "reply_notice": {
        "fields": PERSON + [("n_from", "name", True), ("n_from_address", "address", True),
                            ("n_client", "name", False), ("n_date", "date", True), ("n_received", "date", False),
                            ("n_ref", "ref", False), ("facts", "text", True), ("reliefs", "multi", True),
                            ("other_relief", "short", False), ("days", "select", True), ("place", "place", True)],
        "options": {"reliefs": ["withdraw", "no_proceedings", "stop_contact", "apologise"], "days": DAYS},
        "law": [],
    },
    "cheque_notice": {
        "fields": PERSON + OTHER + [("cheque_no", "cheque", True), ("cheque_date", "date", True),
                                    ("bank", "place", True), ("amount", "amount", True),
                                    ("presented_date", "date", False), ("return_date", "date", True),
                                    ("reason", "select", True), ("basis", "select", True),
                                    ("facts", "text", True), ("place", "place", True)],
        "options": {"reason": ["insufficient", "exceeds", "closed", "stopped", "other_reason"],
                    "basis": ["loan", "goods", "services", "rent", "other_basis"]},
        "law": [("NIA", "138"), ("NIA", "142")],
    },
    "consumer_complaint": {
        "fields": PERSON + [("op_name", "place", True), ("op_address", "address", True),
                            ("district", "place", True), ("state", "place", True),
                            ("purchase_date", "date", True), ("product", "short", True),
                            ("amount", "amount", True), ("bill_no", "ref", False), ("facts", "text", True),
                            ("prior", "short", False), ("reliefs", "multi", True),
                            ("comp_amount", "amount", False), ("cost_amount", "amount", False),
                            ("place", "place", True)],
        "options": {"reliefs": ["refund", "replace", "repair", "compensation", "costs"]},
        "law": [("CPA", "35"), ("CPA", "34"), ("CPA", "69")],
    },
    "rti_application": {
        "fields": [("s_name", "name", True), ("s_address", "address", True), ("s_phone", "phone", False),
                   ("s_email", "email", False), ("level", "select", True), ("authority", "place", True),
                   ("authority_address", "address", True), ("subject", "short", True),
                   ("period", "period", True), ("questions", "lines", True), ("mode", "select", True),
                   ("fee", "select", True), ("fee_ref", "ref", False), ("place", "place", True)],
        "options": {"level": ["central", "state"], "mode": ["post", "email", "inspection"],
                    "fee": ["ipo", "dd", "stamp", "online", "bpl"]},
        "law": [("RTI", "6"), ("RTI", "7"), ("RTI", "3")],
    },
    "deposit_notice": {
        "fields": PERSON + OTHER + [("property", "address", True), ("tenancy_start", "date", True),
                                    ("vacated_on", "date", True), ("amount", "amount", True),
                                    ("deduction", "amount", False), ("facts", "text", False),
                                    ("days", "select", True), ("interest", "select", True),
                                    ("place", "place", True)],
        "options": {"days": DAYS, "interest": ["0", "6", "9", "12", "18"]},
        "law": [],
    },
}

# English text for every label, option and message used by the forms (translated in ui_text)
FORM_TEXT = {
    # document names
    "d_police_complaint": "Police complaint (request to register an FIR)",
    "d_reply_notice": "Reply to a legal notice",
    "d_cheque_notice": "Cheque bounce notice (Section 138, NI Act)",
    "d_consumer_complaint": "Consumer complaint (District Consumer Commission)",
    "d_rti_application": "RTI application (Right to Information)",
    "d_deposit_notice": "Notice for refund of rent deposit",
    # field labels
    "f_s_name": "Your full name", "f_s_rel": "Son / daughter / wife of", "f_s_relname": "Father's or husband's name",
    "f_s_age": "Your age (years)", "f_s_address": "Your full address with PIN code",
    "f_s_phone": "Your mobile number", "f_s_email": "Your email",
    "f_r_name": "Their full name", "f_r_rel": "Their son / daughter / wife of",
    "f_r_relname": "Their father's or husband's name", "f_r_address": "Their full address with PIN code",
    "f_station": "Police station name", "f_district": "District", "f_offence": "What kind of incident?",
    "f_incident_date": "Date of the incident", "f_incident_time": "Time of the incident (HH:MM)",
    "f_incident_place": "Place of the incident", "f_accused": "Who did it (name and description, if known)",
    "f_witnesses": "Witnesses (names, if any)", "f_facts": "What happened? Write the facts in your own words",
    "f_evidence": "Evidence you have", "f_place": "Your town or city (for the signature)",
    "f_n_from": "Who sent you the notice? (person or advocate)",
    "f_n_from_address": "Their address with PIN code",
    "f_n_client": "If an advocate sent it: on whose behalf?", "f_n_date": "Date written on their notice",
    "f_n_received": "Date you received it", "f_n_ref": "Their notice reference number (if any)",
    "f_reliefs": "What do you want them to do?", "f_other_relief": "Anything else you want them to do",
    "f_days": "Time to give them (days)",
    "f_cheque_no": "Cheque number (6 digits)", "f_cheque_date": "Date written on the cheque",
    "f_bank": "Bank and branch", "f_amount": "Amount in rupees",
    "f_presented_date": "Date you deposited the cheque", "f_return_date": "Date of the bank's return memo",
    "f_reason": "Reason written on the return memo", "f_basis": "Why was the cheque given to you?",
    "f_op_name": "Seller or company name", "f_op_address": "Seller or company address with PIN code",
    "f_state": "State", "f_purchase_date": "Date of purchase or service",
    "f_product": "Product or service", "f_bill_no": "Bill, invoice or order number",
    "f_prior": "What you already did (calls, emails, visits)",
    "f_comp_amount": "Compensation you claim (rupees)", "f_cost_amount": "Cost of this case you claim (rupees)",
    "f_level": "Central or State government office?", "f_authority": "Government office or department",
    "f_authority_address": "Office address with PIN code", "f_subject": "Subject of the information",
    "f_period": "Time period (for example 01/04/2024 to 31/03/2025)",
    "f_questions": "Information you want (one question per line)", "f_mode": "How you want to receive it",
    "f_fee": "How you paid the fee", "f_fee_ref": "Postal order / DD / receipt number",
    "f_property": "Address of the rented house with PIN code", "f_tenancy_start": "Date the tenancy started",
    "f_vacated_on": "Date you left and returned the keys", "f_deduction": "Amount you agree can be deducted",
    "f_interest": "Interest to claim (% per year)",
    # options
    "o_S/o": "S/o (son of)", "o_D/o": "D/o (daughter of)", "o_W/o": "W/o (wife of)", "o_C/o": "C/o (care of)",
    "o_theft": "Theft", "o_cheating": "Cheating or fraud", "o_threat": "Threat or intimidation",
    "o_assault": "Assault or hurt", "o_harassment": "Harassment of a woman", "o_cyber": "Online or cyber fraud",
    "o_missing": "Missing person", "o_other": "Other",
    "o_photos": "Photos", "o_videos": "Videos", "o_screenshots": "Screenshots or messages",
    "o_medical": "Medical report", "o_bills": "Bills or receipts", "o_cctv": "CCTV footage",
    "o_withdraw": "Withdraw the notice", "o_no_proceedings": "Not start false legal proceedings against me",
    "o_stop_contact": "Stop threatening or contacting me about this", "o_apologise": "Give an unconditional apology",
    "o_7": "7 days", "o_15": "15 days", "o_30": "30 days",
    "o_insufficient": "Funds insufficient", "o_exceeds": "Exceeds arrangement", "o_closed": "Account closed",
    "o_stopped": "Payment stopped by drawer", "o_other_reason": "Other reason",
    "o_loan": "Repayment of a loan", "o_goods": "Payment for goods", "o_services": "Payment for services",
    "o_rent": "Payment of rent", "o_other_basis": "Other legal debt",
    "o_refund": "Refund of the amount paid", "o_replace": "Replacement", "o_repair": "Free repair",
    "o_compensation": "Compensation for harassment", "o_costs": "Cost of this case",
    "o_central": "Central government", "o_state": "State government",
    "o_post": "Copies by post", "o_email": "By email", "o_inspection": "Inspection of records",
    "o_ipo": "Indian Postal Order", "o_dd": "Demand draft", "o_stamp": "Court fee stamp",
    "o_online": "Paid online", "o_bpl": "BPL card holder (no fee)",
    "o_0": "No interest", "o_6": "6%", "o_9": "9%", "o_12": "12%", "o_18": "18%",
    # messages
    "err_required": "This is required.", "err_name": "Write a real name using letters (at least 3).",
    "err_name_digits": "A name cannot contain numbers.",
    "err_fake": "This looks like test or placeholder text. Write the real details.",
    "err_place": "Write the real name (at least 3 letters).",
    "err_address": "Write the full address: house, street, area and town.",
    "err_pin": "The address must include the 6-digit PIN code.",
    "err_phone": "Write a 10-digit Indian mobile number.", "err_email": "Write a valid email address.",
    "err_date": "Pick a real date.", "err_future": "This date cannot be in the future.",
    "err_old": "This date is too old.", "err_amount": "Write the amount in numbers only (for example 50000).",
    "err_amount_range": "The amount must be more than zero.", "err_age": "Write an age between 18 and 110.",
    "err_cheque_no": "A cheque number has exactly 6 digits.",
    "err_ref": "Use only letters, numbers, / - and . here.",
    "err_facts_short": "Explain more: write at least 2 or 3 full sentences.",
    "err_facts_bad": "This does not read like real sentences. Write what happened in your own words.",
    "err_question": "Each question must be a clear sentence.", "err_too_many": "Ask at most 10 questions.",
    "err_choose": "Choose at least one option.", "err_time": "Write the time as HH:MM (for example 18:30).",
    "err_short": "Write a little more (at least 10 letters).",
    "err_period": "Write the period with dates or years, for example 01/04/2024 to 31/03/2025.",
    "err_order_received": "You cannot receive the notice before its date.",
    "err_order_cheque": "The return memo date cannot be before the cheque date.",
    "err_order_presented": "The deposit date must be between the cheque date and the return memo date.",
    "err_order_vacated": "You cannot leave the house before the tenancy started.",
    "err_deduction": "The deduction cannot be more than the deposit.",
    "err_relname_needed": "Write the father's or husband's name too.",
    "err_fee_ref": "Write the postal order, DD or receipt number.",
    "err_138_late": ("A Section 138 notice must be sent within 30 days of the bank's return memo. This memo is "
                     "{days} days old. Talk to a lawyer or free legal aid (15100) about other ways to recover the money."),
    "warn_cheque_old": ("The cheque was presented more than 3 months after its date. A cheque is valid for 3 months "
                        "from its date; check this with a lawyer before sending."),
    "warn_limitation": ("This purchase is more than 2 years old. Section 69 allows 2 years; the Commission may accept "
                        "a later complaint only if you show a good reason for the delay."),
    "sec_you": "Your details", "sec_them": "The other side", "sec_details": "Details",
    "ph_facts": "What happened, when, where, who was involved, and any loss. Write only true facts.",
    "errors_title": "Please fix these before the document can be made:",
    "doc_lang_label": "Document language",
    "doc_lang_note": ("The English copy is the one to sign and send. The copy in your language is machine translated "
                      "to help you understand it; read it carefully before using it."),
    "ai_polish": "Improve my wording with AI (slower)",
    "facts_translated": "Your facts were translated into English for the English copy. Check that paragraph carefully.",
}

LABELS = {k: v for k, v in FORM_TEXT.items()}


def label(key):
    return LABELS.get(key, key)


# Checking a Form
CHECKERS = {
    "name": F.check_name, "place": F.check_place, "address": F.check_address, "phone": F.check_phone,
    "email": F.check_email, "amount": F.check_amount, "cheque": F.check_cheque_no, "ref": F.check_ref,
    "lines": F.check_lines, "period": F.check_period,
}


def check_short(v, required):
    v = F.clean(v, 300)
    if not v:
        return v, "err_required" if required else None
    if len(F.letters(v)) < 10 or F.looks_fake(v):
        return v, "err_short"
    return v, None


def check_time(v, required):
    v = F.clean(v, 10)
    if not v:
        return v, "err_required" if required else None
    m = re.fullmatch(r"([01]?\d|2[0-3])[:.]([0-5]\d)", v)
    return (f"{int(m.group(1)):02d}:{m.group(2)}", None) if m else (v, "err_time")


def validate(doc_type, raw):
    """Returns (clean values, errors {field: key}, warnings [text])."""
    spec = DOC_TYPES[doc_type]
    opts = spec.get("options", {})
    vals, errs, warns = {}, {}, []
    for key, kind, req in spec["fields"]:
        v = raw.get(key)
        if kind == "date":
            out, err = F.check_date(v, required=req)
        elif kind == "age":
            out, err = F.check_int(v, 18, 110, required=req)
        elif kind == "relation":
            out, err = F.check_choice(v, RELATIONS, required=req)
        elif kind == "select":
            out, err = F.check_choice(v, opts[key], required=req)
        elif kind == "multi":
            out, err = F.check_choice(v, opts[key], required=req, multi=True)
        elif kind == "text":
            out, err = F.check_text(v, required=req)
        elif kind == "short":
            out, err = check_short(v, req)
        elif kind == "time":
            out, err = check_time(v, req)
        else:
            out, err = CHECKERS[kind](v, required=req)
        vals[key] = out
        if err:
            errs[key] = err

    # fields that only make sense together
    for who in ("s", "r"):
        if vals.get(f"{who}_rel") and not vals.get(f"{who}_relname") and f"{who}_relname" not in errs:
            errs[f"{who}_relname"] = "err_relname_needed"

    d = vals.get
    if doc_type == "reply_notice" and d("n_received") and d("n_date") and d("n_received") < d("n_date"):
        errs["n_received"] = "err_order_received"
    if doc_type == "cheque_notice" and d("cheque_date") and d("return_date"):
        if d("return_date") < d("cheque_date"):
            errs["return_date"] = "err_order_cheque"
        elif "return_date" not in errs:
            age = (F.today() - d("return_date")).days
            if age > 30:
                errs["return_date"] = ("err_138_late", {"days": age})
            presented = d("presented_date") or d("return_date")
            if presented - d("cheque_date") > timedelta(days=92):
                warns.append(label("warn_cheque_old"))
        if d("presented_date") and not (d("cheque_date") <= d("presented_date") <= d("return_date")):
            errs["presented_date"] = "err_order_presented"
    if doc_type == "deposit_notice" and d("tenancy_start") and d("vacated_on") and d("vacated_on") < d("tenancy_start"):
        errs["vacated_on"] = "err_order_vacated"
    if doc_type == "deposit_notice" and d("deduction") and d("amount") and d("deduction") > d("amount"):
        errs["deduction"] = "err_deduction"
    if doc_type == "consumer_complaint" and d("purchase_date") and (F.today() - d("purchase_date")).days > 730:
        warns.append(label("warn_limitation"))
    if doc_type == "consumer_complaint":
        if "compensation" in (d("reliefs") or []) and not d("comp_amount") and "comp_amount" not in errs:
            errs["comp_amount"] = "err_required"
        if "costs" in (d("reliefs") or []) and not d("cost_amount") and "cost_amount" not in errs:
            errs["cost_amount"] = "err_required"
    if doc_type == "rti_application" and d("fee") in ("ipo", "dd", "stamp") and not d("fee_ref") and "fee_ref" not in errs:
        errs["fee_ref"] = "err_fee_ref"
    return vals, errs, warns


def error_lines(errs, tr=lambda k: label(k)):
    out = []
    for key, e in errs.items():
        if isinstance(e, tuple):
            msg = tr(e[0]).format(**e[1])
        else:
            msg = tr(e)
        name = tr("f_" + key).rstrip(" *").rstrip("?:")
        out.append(f"{name}: {msg}")
    return out


# Turning Facts into Numbered Paragraphs
def sentences(text):
    text = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?।])\s+", text)
    return [p for p in parts if p.strip()]


def tidy_sentence(s):
    s = s.strip()
    s = re.sub(r"\bi\b", "I", s)                     # "i" -> "I"
    if s and s[-1] not in ".!?।":
        s += "."
    return s[0].upper() + s[1:] if s else s


def fact_paragraphs(text, english=True):
    # two sentences per paragraph; English paragraphs start with "That" (Indian drafting style)
    sents = [tidy_sentence(s) for s in sentences(text)]
    paras = [" ".join(sents[i:i + 2]) for i in range(0, len(sents), 2)]
    if not english:
        return paras
    out = []
    for p in paras:
        first = p.split(" ", 1)[0]
        keep = first in ("I", "I'm", "I've") or (len(first) > 1 and first[1:].lower() != first[1:])  # names, acronyms
        out.append("That " + (p if keep else p[0].lower() + p[1:]))
    return out


# Optional AI Wording (checked so it adds nothing new)
def polish_facts(facts, doc_title, backend):
    if not backend or getattr(backend, "name", "") == "extractive":
        return facts
    try:
        msgs = [{"role": "system", "content": DRAFT_SYSTEM_PROMPT},
                {"role": "user", "content": DRAFT_TEMPLATE.format(doc_type=doc_title, what="Statement of facts",
                                                                  facts=facts)}]
        out = (backend.chat(msgs, max_tokens=500, temperature=0.1) or "").strip()
    except Exception as e:
        print(f"[WARNING] Draft polishing failed: {e}")
        return facts
    return out if out and adds_nothing_new(facts, out) else facts


def adds_nothing_new(facts, text):
    # numbers and capitalised names in the new text must already be in the person's facts
    nums = set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", facts))
    names = set(re.findall(r"\b[A-Z][a-z]{2,}\b", text)) - set(re.findall(r"\b[A-Z][a-z]{2,}\b", facts))
    common = {"The", "This", "That", "These", "They", "There", "When", "After", "Before", "Despite", "Since",
              "However", "Further", "Also", "On", "In", "At", "As", "Thereafter", "Subsequently", "Rs",
              "Sir", "Madam", "Yours", "Moreover", "Accordingly", "Hence", "Therefore", "Although",
              "Police", "Station", "Bank", "Court", "Commission", "Notice", "Due", "During",
              "Upon", "Until", "With", "Without", "Even", "Only", "Then", "Thus", "Later", "Earlier",
              "January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
              "Saturday", "Sunday", "India", "Indian", "Please", "Kindly", "My", "Our", "His", "Her", "Their"}
    return not nums and not (names - common)


# Building the Document
# Blocks: (kind, content). «» marks values typed by the person: they are never translated.
def q(v):
    return f"«{v}»" if v else ""


def who(prefix, v):
    # "Ravi Kumar, S/o Mohan Kumar, aged about 34 years, residing at ..."
    parts = [q(v[f"{prefix}_name"])]
    if v.get(f"{prefix}_rel") and v.get(f"{prefix}_relname"):
        parts.append(f"{v[f'{prefix}_rel']} {q(v[f'{prefix}_relname'])}")
    if v.get(f"{prefix}_age"):
        parts.append(f"aged about {v[f'{prefix}_age']} years")
    parts.append(f"residing at {q(v[f'{prefix}_address'])}")
    return ", ".join(parts)


def split_address(address):
    # "7, Court Road, Egmore, Chennai 600008" -> ["7, Court Road,", "Egmore, Chennai 600008"]
    parts = [x.strip() for x in address.split(",") if x.strip()]
    lines, cur = [], ""
    for p in parts:
        cur = f"{cur}, {p}" if cur else p
        if len(cur) >= 18:
            lines.append(cur)
            cur = ""
    if cur:
        if lines and len(cur) < 10:
            lines[-1] += ", " + cur
        else:
            lines.append(cur)
    return lines


def address_lines(name, rel, relname, address):
    lines = [q(name) + ","]
    if rel and relname:
        lines.append(f"{rel} {q(relname)},")
    lines += [q(x) + "," for x in split_address(address)]
    lines[-1] = lines[-1].rstrip(",") + "."
    return lines


def signature(v, place, today, label_text="Yours faithfully,"):
    lines = [label_text, "", "(Signature)", q(v["s_name"])]
    if v.get("s_phone"):
        lines.append(f"Mobile: {q(v['s_phone'])}")
    return [("placedate", (q(place), F.fmt_date(today))), ("sign", lines)]


def join_list(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


RELIEF_TEXT = {
    "withdraw": "withdraw your said notice",
    "no_proceedings": "refrain from initiating any false or frivolous legal proceedings against me",
    "stop_contact": "stop threatening or contacting me in this matter",
    "apologise": "tender an unconditional apology",
}
OFFENCE_TEXT = {
    "theft": "theft", "cheating": "cheating and fraud", "threat": "criminal intimidation (threats)",
    "assault": "assault and causing hurt", "harassment": "harassment of a woman", "cyber": "online / cyber fraud",
    "missing": "a missing person", "other": "the incident described below",
}
REASON_TEXT = {"insufficient": "Funds Insufficient", "exceeds": "Exceeds Arrangement", "closed": "Account Closed",
               "stopped": "Payment Stopped by Drawer", "other_reason": "Dishonoured"}
BASIS_TEXT = {"loan": "repayment of a loan given by me to you", "goods": "payment for goods supplied by me to you",
              "services": "payment for services rendered by me to you", "rent": "payment of rent due to me",
              "other_basis": "discharge of a legally enforceable debt owed by you to me"}
EVIDENCE_TEXT = {"photos": "photographs", "videos": "videos", "screenshots": "screenshots / messages",
                 "medical": "medical report", "bills": "bills / receipts", "cctv": "CCTV footage"}
MODE_TEXT = {"post": "certified copies by post at my address given above",
             "email": "by email at the address given above", "inspection": "inspection of the relevant records"}
FEE_TEXT = {"ipo": "Indian Postal Order", "dd": "Demand Draft", "stamp": "Court Fee Stamp", "online": "online payment"}


def build_document(doc_type, v, facts_en, today=None):
    """v: clean values from validate(); facts_en: the facts in English."""
    today = today or F.today()
    blocks, n = [], [0]
    add = blocks.append

    def num(text):
        n[0] += 1
        add(("num", (n[0], text)))

    facts = fact_paragraphs(facts_en) if facts_en else []

    def fact(text):
        n[0] += 1
        add(("num", (n[0], text, "fact")))

    if doc_type == "reply_notice":
        add(("dispatch", "BY REGISTERED POST A.D. / SPEED POST"))
        add(("date", f"Date: {F.fmt_date(today)}"))
        add(("title", "REPLY TO LEGAL NOTICE"))
        add(("lines", ["To,"] + address_lines(v["n_from"], None, None, v["n_from_address"])))
        ref = f" bearing Ref. No. {q(v['n_ref'])}" if v.get("n_ref") else ""
        add(("subject", f"Subject: Reply to your Legal Notice dated {F.fmt_date(v['n_date'])}{ref}."))
        add(("para", "Sir/Madam,"))
        got = f", received by me on {F.fmt_date(v['n_received'])}" if v.get("n_received") else ""
        client = f", issued on behalf of {q(v['n_client'])}" if v.get("n_client") else ""
        add(("para", f"I, {who('s', v)}, am in receipt of your legal notice dated {F.fmt_date(v['n_date'])}"
                     f"{client}{got}. I reply to the same as follows:"))
        num("That the contents of your notice are false and misleading, and are denied in their entirety, except "
            "what is specifically admitted in this reply. Nothing in your notice shall be deemed to be admitted "
            "by me for want of a specific denial.")
        for p in facts:
            fact(p)
        asks = [RELIEF_TEXT[r] for r in v["reliefs"]]
        if v.get("other_relief"):
            asks.append(q(v["other_relief"].rstrip(".")))
        num(f"That in view of the above, you are hereby called upon to {join_list(asks)}, within {v['days']} days "
            f"of the receipt of this reply.")
        num("That this reply is sent without prejudice to all my rights and remedies under law, all of which are "
            "expressly reserved.")
        num("That a copy of this reply has been retained by me for record and further action.")
        blocks += signature(v, v["place"], today)

    elif doc_type == "cheque_notice":
        add(("dispatch", "BY REGISTERED POST A.D. / SPEED POST"))
        add(("date", f"Date: {F.fmt_date(today)}"))
        add(("title", "LEGAL NOTICE UNDER SECTION 138 OF THE NEGOTIABLE INSTRUMENTS ACT, 1881"))
        add(("lines", ["To,"] + address_lines(v["r_name"], v.get("r_rel"), v.get("r_relname"), v["r_address"])))
        add(("subject", f"Subject: Demand notice for dishonour of Cheque No. {q(v['cheque_no'])} dated "
                        f"{F.fmt_date(v['cheque_date'])} for {q(F.money(v['amount']))}."))
        add(("para", "Sir/Madam,"))
        add(("para", f"I, {who('s', v)}, hereby serve you with this notice as follows:"))
        num(f"That you owed me a legally enforceable debt towards {BASIS_TEXT[v['basis']]}.")
        for p in facts:
            fact(p)
        num(f"That towards the discharge of the said debt, you issued Cheque No. {q(v['cheque_no'])} dated "
            f"{F.fmt_date(v['cheque_date'])} for {q(F.money(v['amount']))}, drawn on {q(v['bank'])}, in my favour.")
        when = f" on {F.fmt_date(v['presented_date'])}" if v.get("presented_date") else ""
        remark = q('"' + REASON_TEXT[v["reason"]] + '"')      # the bank's words, kept exactly
        num(f"That I presented the said cheque for payment{when}, and it was returned unpaid by the bank with the "
            f"remark {remark} vide return memo dated {F.fmt_date(v['return_date'])}.")
        num("That this notice is issued within thirty days of the receipt of information from the bank regarding "
            "the return of the cheque as unpaid, as required by Section 138 of the Negotiable Instruments Act, 1881.")
        num(f"That I hereby call upon you to pay the said amount of {q(F.money(v['amount']))} within fifteen (15) "
            f"days of the receipt of this notice.")
        num("That if you fail to make the payment within the said period, I shall be constrained to file a complaint "
            "against you under Section 138 read with Section 142 of the Negotiable Instruments Act, 1881, entirely "
            "at your risk as to costs and consequences.")
        num("That a copy of this notice has been retained by me for record and further action.")
        blocks += signature(v, v["place"], today)

    elif doc_type == "deposit_notice":
        add(("dispatch", "BY REGISTERED POST A.D. / SPEED POST"))
        add(("date", f"Date: {F.fmt_date(today)}"))
        add(("title", "LEGAL NOTICE FOR REFUND OF SECURITY DEPOSIT"))
        add(("lines", ["To,"] + address_lines(v["r_name"], v.get("r_rel"), v.get("r_relname"), v["r_address"])))
        due = v["amount"] - (v.get("deduction") or 0)
        add(("subject", f"Subject: Refund of security deposit of {q(F.money(due))}."))
        add(("para", "Sir/Madam,"))
        add(("para", f"I, {who('s', v)}, hereby serve you with this notice as follows:"))
        num(f"That I was your tenant at the premises situated at {q(v['property'])} from "
            f"{F.fmt_date(v['tenancy_start'])}.")
        num(f"That at the start of the tenancy, I paid you a refundable security deposit of {q(F.money(v['amount']))}.")
        num(f"That I vacated the said premises and handed over its vacant and peaceful possession, along with the "
            f"keys, to you on {F.fmt_date(v['vacated_on'])}.")
        if v.get("deduction"):
            num(f"That I agree to a deduction of {q(F.money(v['deduction']))} from the deposit, and the balance of "
                f"{q(F.money(due))} is payable to me.")
        for p in facts:
            fact(p)
        interest = (f", together with interest at the rate of {v['interest']}% per annum from "
                    f"{F.fmt_date(v['vacated_on'])} till the date of payment" if v["interest"] != "0" else "")
        num(f"That I hereby call upon you to refund the sum of {q(F.money(due))}{interest}, within {v['days']} days "
            f"of the receipt of this notice.")
        num("That if you fail to do so, I shall be constrained to initiate appropriate legal proceedings against you "
            "for recovery of the said amount, entirely at your risk as to costs and consequences.")
        num("That a copy of this notice has been retained by me for record and further action.")
        blocks += signature(v, v["place"], today)

    elif doc_type == "police_complaint":
        add(("lines", ["To,", "The Station House Officer,", f"{q(v['station'])} Police Station,",
                       f"{q(v['district'])}."]))
        add(("date", f"Date: {F.fmt_date(today)}"))
        add(("subject", f"Subject: Complaint regarding {OFFENCE_TEXT[v['offence']]} and request to register an FIR "
                        f"under Section 173 of the Bharatiya Nagarik Suraksha Sanhita, 2023."))
        add(("para", "Respected Sir/Madam,"))
        phone = f", Mobile: {q(v['s_phone'])}" if v.get("s_phone") else ""
        add(("para", f"I, {who('s', v)}{phone}, respectfully submit as follows:"))
        at = f" at about {v['incident_time']} hours" if v.get("incident_time") else ""
        num(f"That on {F.fmt_date(v['incident_date'])}{at}, at {q(v['incident_place'])}, the following incident "
            f"took place.")
        for p in facts:
            fact(p)
        num(f"That the person(s) responsible: {q(v['accused']) if v.get('accused') else 'not known to me at present'}.")
        if v.get("witnesses"):
            num(f"That the incident was witnessed by: {q(v['witnesses'])}.")
        if v.get("evidence"):
            num(f"That I have the following evidence, which I am ready to produce: "
                f"{join_list([EVIDENCE_TEXT[e] for e in v['evidence']])}.")
        add(("para", "It is therefore requested that you may kindly:"))
        add(("list", ["register an FIR on the above information and investigate the matter in accordance with law;",
                      "give me a copy of the information as recorded, free of cost, as provided under "
                      "Section 173(2) of the Bharatiya Nagarik Suraksha Sanhita, 2023; and",
                      "take all necessary action against the person(s) responsible."]))
        add(("para", "I declare that the facts stated above are true and correct to the best of my knowledge and belief."))
        blocks += signature(v, v["place"], today)
        if v.get("evidence"):
            add(("lines", ["Enclosures: copies of " + join_list([EVIDENCE_TEXT[e] for e in v["evidence"]]) + "."]))

    elif doc_type == "consumer_complaint":
        add(("cause", f"BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION, "
                      f"{q(v['district'].upper())}, {q(v['state'].upper())}"))
        add(("center", f"Consumer Complaint No. ________ of {today.year}"))
        add(("para", "IN THE MATTER OF:"))
        add(("party", (who("s", v), "... Complainant")))
        add(("center", "Versus"))
        add(("party", (f"{q(v['op_name'])}, {q(v['op_address'])}", "... Opposite Party")))
        add(("title", "COMPLAINT UNDER SECTION 35 OF THE CONSUMER PROTECTION ACT, 2019"))
        add(("para", "MOST RESPECTFULLY SHOWETH:"))
        num("That the Complainant is a consumer who bought goods / availed services from the Opposite Party for "
            "consideration.")
        bill = f" vide Bill / Invoice No. {q(v['bill_no'])}" if v.get("bill_no") else ""
        num(f"That on {F.fmt_date(v['purchase_date'])}, the Complainant purchased / availed {q(v['product'])} from "
            f"the Opposite Party for {q(F.money(v['amount']))}{bill}.")
        for p in facts:
            fact(p)
        if v.get("prior"):
            num(f"That the Complainant approached the Opposite Party to resolve the matter as follows: "
                f"{q(v['prior'].rstrip('.'))}. However, the Opposite Party failed to resolve it.")
        num("That the above acts of the Opposite Party amount to a defect in the goods and / or deficiency in "
            "service.")
        if (today - v["purchase_date"]).days <= 730:
            num("That the cause of action arose on " + F.fmt_date(v["purchase_date"]) + " and this complaint is filed "
                "within two years of it, as required by Section 69 of the Consumer Protection Act, 2019.")
        else:
            num("That this complaint is filed after two years from the cause of action; the Complainant is filing a "
                "separate application explaining the sufficient cause for the delay, under Section 69(2) of the "
                "Consumer Protection Act, 2019.")
        num("That this Hon'ble Commission has jurisdiction to entertain this complaint under Section 34 of the "
            "Consumer Protection Act, 2019, as the Opposite Party resides or carries on business, or the cause of "
            "action arose, within its local limits.")
        add(("heading", "PRAYER"))
        add(("para", "It is, therefore, most respectfully prayed that this Hon'ble Commission may be pleased to direct "
                     "the Opposite Party to:"))
        prayers = []
        r = v["reliefs"]
        if "refund" in r:
            prayers.append(f"refund {q(F.money(v['amount']))} paid by the Complainant;")
        if "replace" in r:
            prayers.append(f"replace the defective {q(v['product'])} with a new one free of cost;")
        if "repair" in r:
            prayers.append(f"repair the {q(v['product'])} free of cost;")
        if "compensation" in r:
            prayers.append(f"pay {q(F.money(v['comp_amount']))} as compensation for the mental agony and "
                           f"harassment caused;")
        if "costs" in r:
            prayers.append(f"pay {q(F.money(v['cost_amount']))} towards the cost of this complaint;")
        prayers.append("pass any other order that this Hon'ble Commission deems fit in the interest of justice.")
        add(("list", prayers))
        blocks += signature(v, v["place"], today, label_text="Complainant")
        add(("heading", "VERIFICATION"))
        add(("para", f"I, {q(v['s_name'])}, the Complainant above named, do hereby verify that the contents of "
                     f"paragraphs 1 to {n[0]} above are true and correct to the best of my knowledge and belief, and "
                     f"nothing material has been concealed therein. Verified at {q(v['place'])} on "
                     f"{F.fmt_date(today)}."))
        add(("sign", ["Complainant"]))

    elif doc_type == "rti_application":
        level = "Central" if v["level"] == "central" else "State"
        add(("lines", ["To,", f"The {level} Public Information Officer,", f"{q(v['authority'])},"]
                      + [q(x) + "," for x in split_address(v["authority_address"])]))
        blocks[-1] = ("lines", blocks[-1][1][:-1] + [blocks[-1][1][-1].rstrip(",") + "."])
        add(("date", f"Date: {F.fmt_date(today)}"))
        add(("subject", "Subject: Application for information under Section 6(1) of the Right to Information Act, 2005."))
        add(("para", "Sir/Madam,"))
        add(("para", "I request you to provide the following information under the Right to Information Act, 2005:"))
        num(f"Name of the applicant: {q(v['s_name'])}")
        num(f"Address: {q(v['s_address'])}")
        contact = ", ".join(x for x in [v.get("s_phone") and f"Mobile: {q(v['s_phone'])}",
                                        v.get("s_email") and f"Email: {q(v['s_email'])}"] if x)
        if contact:
            num(f"Contact: {contact}")
        num(f"Subject matter of the information: {q(v['subject'])}")
        num(f"Period to which the information relates: {q(v['period'])}")
        num("Information required:")
        add(("list", [q(x) for x in v["questions"]]))
        num(f"Mode of receiving the information: {MODE_TEXT[v['mode']]}.")
        if v["fee"] == "bpl":
            num("Application fee: I belong to the Below Poverty Line (BPL) category, and a copy of my BPL proof is "
                "attached. No fee is chargeable from me as per the proviso to Section 7(5) of the Right to "
                "Information Act, 2005.")
        else:
            ref = f" No. {q(v['fee_ref'])}" if v.get("fee_ref") else ""
            num(f"Application fee: The prescribed fee has been paid by {FEE_TEXT[v['fee']]}{ref}.")
        num("I state that I am a citizen of India.")
        num("As per Section 6(2) of the Right to Information Act, 2005, I am not required to give any reason for "
            "requesting this information.")
        blocks += signature(v, v["place"], today)
        if v["fee"] == "bpl":
            add(("lines", ["Enclosure: copy of BPL proof."]))
    return blocks


TITLES = {
    "police_complaint": "Police_Complaint", "reply_notice": "Reply_to_Legal_Notice",
    "cheque_notice": "Cheque_Bounce_Notice_Sec138", "consumer_complaint": "Consumer_Complaint",
    "rti_application": "RTI_Application", "deposit_notice": "Deposit_Refund_Notice",
}

# Tips shown next to the document (not part of it)
TIPS = {
    "police_complaint": ("Take two copies to the police station. Ask for a receipt or diary number on your copy. If "
                         "the police refuse to register the FIR, Section 173(4) of the BNSS lets you send this "
                         "complaint in writing by post to the Superintendent of Police."),
    "reply_notice": "Send it by Registered Post A.D. or Speed Post and keep the postal receipt and the A.D. card.",
    "cheque_notice": ("Send it by Registered Post A.D. or Speed Post within 30 days of the return memo. If they do "
                      "not pay within 15 days of receiving it, the complaint must be filed within one month after "
                      "that (Section 142). Keep the cheque, the return memo and the postal receipts."),
    "consumer_complaint": ("You can file online on the e-Daakhil portal. Attach copies of the bill, warranty, photos "
                           "and your messages with the seller, and the prescribed fee. The Commission may ask for an "
                           "affidavit."),
    "rti_application": "Keep a copy and the postal receipt. If you get no reply in 30 days, you can file a first appeal.",
    "deposit_notice": "Send it by Registered Post A.D. or Speed Post and keep the rent agreement and payment proofs.",
}


# Fixed letter words, written by hand (machine translation got these wrong: "To," became
# "for that", "Yours faithfully" became "with my honesty", "Ref. No." became "no")
LETTER_WORDS = {
    "hi": {"To,": "सेवा में,", "Sir/Madam,": "महोदय/महोदया,", "Respected Sir/Madam,": "आदरणीय महोदय/महोदया,",
           "Yours faithfully,": "भवदीय,", "(Signature)": "(हस्ताक्षर)", "Date:": "दिनांक:", "Subject:": "विषय:",
           "Place:": "स्थान:", "Mobile:": "मोबाइल:", "Complainant": "शिकायतकर्ता", "Enclosures:": "संलग्नक:",
           "Enclosure:": "संलग्नक:", "Versus": "बनाम"},
    "mr": {"To,": "प्रति,", "Sir/Madam,": "महोदय/महोदया,", "Respected Sir/Madam,": "आदरणीय महोदय/महोदया,",
           "Yours faithfully,": "आपला विश्वासू,", "(Signature)": "(स्वाक्षरी)", "Date:": "दिनांक:", "Subject:": "विषय:",
           "Place:": "ठिकाण:", "Mobile:": "मोबाईल:", "Complainant": "तक्रारदार", "Enclosures:": "सोबत:",
           "Enclosure:": "सोबत:", "Versus": "विरुद्ध"},
    "ta": {"To,": "பெறுநர்,", "Sir/Madam,": "ஐயா/அம்மா,", "Respected Sir/Madam,": "மதிப்பிற்குரிய ஐயா/அம்மா,",
           "Yours faithfully,": "தங்கள் உண்மையுள்ள,", "(Signature)": "(கையொப்பம்)", "Date:": "தேதி:",
           "Subject:": "பொருள்:", "Place:": "இடம்:", "Mobile:": "கைபேசி:", "Complainant": "புகார்தாரர்",
           "Enclosures:": "இணைப்புகள்:", "Enclosure:": "இணைப்பு:", "Versus": "எதிர்"},
    "te": {"To,": "గ్రహీత,", "Sir/Madam,": "అయ్యా/అమ్మా,", "Respected Sir/Madam,": "గౌరవనీయులైన అయ్యా/అమ్మా,",
           "Yours faithfully,": "ఇట్లు, తమ విధేయుడు,", "(Signature)": "(సంతకం)", "Date:": "తేదీ:",
           "Subject:": "విషయం:", "Place:": "స్థలం:", "Mobile:": "మొబైల్:", "Complainant": "ఫిర్యాదుదారు",
           "Enclosures:": "జతపరచినవి:", "Enclosure:": "జతపరచినది:", "Versus": "వర్సెస్"},
    "kn": {"To,": "ಗೆ,", "Sir/Madam,": "ಮಾನ್ಯರೇ,", "Respected Sir/Madam,": "ಮಾನ್ಯರೇ,",
           "Yours faithfully,": "ಇಂತಿ ತಮ್ಮ ವಿಶ್ವಾಸಿ,", "(Signature)": "(ಸಹಿ)", "Date:": "ದಿನಾಂಕ:",
           "Subject:": "ವಿಷಯ:", "Place:": "ಸ್ಥಳ:", "Mobile:": "ಮೊಬೈಲ್:", "Complainant": "ದೂರುದಾರರು",
           "Enclosures:": "ಲಗತ್ತುಗಳು:", "Enclosure:": "ಲಗತ್ತು:", "Versus": "ವಿರುದ್ಧ"},
    "bn": {"To,": "প্রতি,", "Sir/Madam,": "মহাশয়/মহাশয়া,", "Respected Sir/Madam,": "মাননীয় মহাশয়/মহাশয়া,",
           "Yours faithfully,": "বিনীত,", "(Signature)": "(স্বাক্ষর)", "Date:": "তারিখ:", "Subject:": "বিষয়:",
           "Place:": "স্থান:", "Mobile:": "মোবাইল:", "Complainant": "অভিযোগকারী", "Enclosures:": "সংযুক্তি:",
           "Enclosure:": "সংযুক্তি:", "Versus": "বনাম"},
    "gu": {"To,": "પ્રતિ,", "Sir/Madam,": "માનનીય સાહેબ/બહેન,", "Respected Sir/Madam,": "આદરણીય સાહેબ/બહેન,",
           "Yours faithfully,": "આપનો વિશ્વાસુ,", "(Signature)": "(સહી)", "Date:": "તારીખ:", "Subject:": "વિષય:",
           "Place:": "સ્થળ:", "Mobile:": "મોબાઇલ:", "Complainant": "ફરિયાદી", "Enclosures:": "બિડાણ:",
           "Enclosure:": "બિડાણ:", "Versus": "વિરુદ્ધ"},
}


def letter_word(text, lang):
    # exact word ("To,") or a "Label: value" line; returns None if it is not a fixed letter word
    words = LETTER_WORDS.get(lang, {})
    t = text.strip()
    if t in words:
        return words[t]
    for en, native in words.items():
        # short "Label: value" lines only; a subject line is translated separately
        if en.endswith(":") and en != "Subject:" and t.startswith(en):
            return native + t[len(en):]
    return None


# Translated Copy
def translate_blocks(blocks, lang, facts_native=None):
    """Same document in another language. «» values stay exactly as typed; if the facts were written in
    that language, the person's own words are used instead of a machine round-trip."""
    if lang == "en":
        return blocks
    from .translate import translate

    def tr(text):
        if not text or not text.strip():
            return text
        fixed = letter_word(text, lang)
        if fixed is not None:
            return fixed
        # "Subject: ..." keeps the hand-written label and translates the rest
        for label_en in ("Subject:",):
            if text.startswith(label_en):
                return letter_word(label_en, lang) + " " + translate(text[len(label_en):].strip(), lang, "en")
        return translate(text, lang, "en")

    native = fact_paragraphs(facts_native, english=False) if facts_native else None
    out, fi = [], 0
    for kind, c in blocks:
        if kind in ("lines", "sign", "list"):
            out.append((kind, [tr(x) for x in c]))
        elif kind == "num":
            if len(c) > 2 and c[2] == "fact" and native:
                text = native[fi] if fi < len(native) else ""
                fi += 1
                if text:
                    out.append((kind, (c[0], text, "fact")))
                continue
            out.append((kind, (c[0], tr(c[1])) + tuple(c[2:])))
        elif kind == "placedate":
            out.append((kind, (c[0], c[1], letter_word("Place:", lang) or "Place:", letter_word("Date:", lang) or "Date:")))
        elif kind == "dispatch":
            out.append((kind, c))           # postal instruction: India Post uses it in English
        elif kind == "party":
            out.append((kind, (tr(c[0]), tr(c[1]))))
        else:
            out.append((kind, tr(c)))
    if native and fi < len(native):
        # more native paragraphs than English ones: append the rest after the last fact
        last = max(i for i, (k, c) in enumerate(out) if k == "num" and len(c) > 2 and c[2] == "fact")
        for extra in native[fi:]:
            out.insert(last + 1, ("num", (0, extra, "fact")))
            last += 1
    # renumber
    k = 0
    final = []
    for kind, c in out:
        if kind == "num":
            k += 1
            final.append((kind, (k, c[1]) + tuple(c[2:])))
        else:
            final.append((kind, c))
    return final


# Output Formats
def strip_marks(text):
    return text.replace("«", "").replace("»", "")


def plain_blocks(blocks):
    def s(x):
        return strip_marks(x) if isinstance(x, str) else x
    out = []
    for kind, c in blocks:
        if kind in ("lines", "sign", "list"):
            out.append((kind, [strip_marks(x) for x in c]))
        elif kind == "num":
            out.append((kind, (c[0], strip_marks(c[1])) + tuple(c[2:])))
        elif kind in ("placedate", "party"):
            out.append((kind, tuple(strip_marks(x) for x in c)))
        else:
            out.append((kind, s(c)))
    return out


def to_markdown(blocks):
    # preview only; everything the person typed is escaped
    b = plain_blocks(blocks)
    out = []
    for kind, c in b:
        if kind == "dispatch":
            out.append(f"**{F.safe(c)}**")
        elif kind == "date":
            out.append(f"<div style='text-align:right'>{F.safe(c)}</div>")
        elif kind in ("title", "cause", "heading"):
            out.append(f"<div style='text-align:center'><b><u>{F.safe(c)}</u></b></div>")
        elif kind == "center":
            out.append(f"<div style='text-align:center'>{F.safe(c)}</div>")
        elif kind == "lines":
            out.append("  \n".join(F.safe(x) for x in c))
        elif kind == "subject":
            out.append(f"**{F.safe(c)}**")
        elif kind == "num":
            out.append(f"{c[0]}\\. {F.safe(c[1])}")
        elif kind == "list":
            out.append("\n".join(f"   ({chr(97 + i)}) {F.safe(x)}" for i, x in enumerate(c)))
        elif kind == "party":
            out.append(f"{F.safe(c[0])}  \n<div style='text-align:right'>{F.safe(c[1])}</div>")
        elif kind == "placedate":
            pl, dl = (c[2], c[3]) if len(c) > 3 else ("Place:", "Date:")
            out.append(f"{F.safe(pl)} {F.safe(c[0])}  \n{F.safe(dl)} {F.safe(c[1])}")
        elif kind == "sign":
            out.append("<div style='text-align:right'>" + "<br>".join(F.safe(x) for x in c) + "</div>")
        else:
            out.append(F.safe(c))
        out.append("")
    return "\n".join(out)


def to_docx(blocks, path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    d = Document()
    for s in d.sections:
        s.top_margin = s.bottom_margin = Cm(2.5)
        s.left_margin = s.right_margin = Cm(2.5)
    st = d.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(12)
    st.paragraph_format.space_after = Pt(6)
    J, C, R, L = (WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.RIGHT,
                  WD_ALIGN_PARAGRAPH.LEFT)

    def para(text, align=L, bold=False, underline=False, indent=None):
        p = d.add_paragraph()
        r = p.add_run(text)
        r.bold, r.underline = bold, underline
        p.alignment = align
        if indent is not None:
            p.paragraph_format.left_indent = Cm(indent)
            p.paragraph_format.first_line_indent = Cm(-0.75)
        return p

    for kind, c in plain_blocks(blocks):
        if kind == "dispatch":
            para(c, bold=True)
        elif kind == "date":
            para(c, align=R)
        elif kind in ("title", "cause", "heading"):
            para(c, align=C, bold=True, underline=True)
        elif kind == "center":
            para(c, align=C)
        elif kind == "lines":
            p = para("\n".join(c))
        elif kind == "subject":
            para(c, bold=True, align=J)
        elif kind == "num":
            para(f"{c[0]}.\t{c[1]}", align=J, indent=0.75)
        elif kind == "list":
            for i, x in enumerate(c):
                para(f"({chr(97 + i)})\t{x}", align=J, indent=1.5)
        elif kind == "party":
            para(c[0], align=J)
            para(c[1], align=R, bold=True)
        elif kind == "placedate":
            pl, dl = (c[2], c[3]) if len(c) > 3 else ("Place:", "Date:")
            para(f"{pl} {c[0]}\n{dl} {c[1]}")
        elif kind == "sign":
            para("\n".join(c), align=R)
        else:
            para(c, align=J)
    d.save(path)
    return path


# (font family, Unicode range, HarfBuzz script, language) for documents in Indian scripts.
# Each font is Noto Sans Latin merged with the script (scripts/build_fonts.py), so a whole
# document uses one font and the script is set explicitly: mixed lines like "புகார் Section 35"
# shaped wrongly when the shaper had to guess.
SCRIPT_FONTS = [("NyayaDevanagari", (0x0900, 0x097F), "deva", "HIN"), ("NyayaBengali", (0x0980, 0x09FF), "beng", "BEN"),
                ("NyayaGujarati", (0x0A80, 0x0AFF), "gujr", "GUJ"), ("NyayaTamil", (0x0B80, 0x0BFF), "taml", "TAM"),
                ("NyayaTelugu", (0x0C00, 0x0C7F), "telu", "TEL"), ("NyayaKannada", (0x0C80, 0x0CFF), "knda", "KAN")]


def to_pdf(blocks, path):
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_margins(25, 22, 25)
    pdf.set_auto_page_break(True, 22)
    pdf.add_page()
    # one font for the whole document: Noto Serif for English, a merged Latin + script font otherwise
    text_all = str(plain_blocks(blocks))
    counts = [(sum(1 for ch in text_all if lo <= ord(ch) <= hi), fam, script, lang)
              for fam, (lo, hi), script, lang in SCRIPT_FONTS]
    n, fam, script, lang = max(counts)
    family = fam if n else "NotoSerif"
    for style, w in (("", "Regular"), ("B", "Bold")):
        pdf.add_font("Serif", style, os.path.join(FONT_DIR, f"{family}-{w}.ttf"))
    if n:
        pdf.set_text_shaping(True, script=script, language=lang)   # joins Indian-script letters correctly
    width = pdf.w - pdf.l_margin - pdf.r_margin

    def shaping(text):
        pass

    def hanging(label_text, text, indent, label_w=9):
        # number and text together; if the paragraph does not fit, start it on a new page
        shaping(text)
        pdf.set_font("Serif", "", 11.5)
        h = pdf.multi_cell(width - indent - label_w, 6.2, text, align="J", dry_run=True, output="HEIGHT")
        if pdf.get_y() + min(h, 3 * 6.2) > pdf.page_break_trigger:
            pdf.add_page()
        y = pdf.get_y()
        pdf.set_x(pdf.l_margin + indent)
        pdf.cell(label_w, 6.2, label_text)
        pdf.set_xy(pdf.l_margin + indent + label_w, y)
        pdf.multi_cell(width - indent - label_w, 6.2, text, align="J", new_x="LMARGIN", new_y="NEXT")

    def cell(text, align="L", style="", size=11.5, gap=2.2, indent=0):
        shaping(text)
        pdf.set_font("Serif", style, size)
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(width - indent, 6.2, text, align=align, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(gap)

    for kind, c in plain_blocks(blocks):
        if kind == "dispatch":
            cell(c, style="B", size=10.5)
        elif kind == "date":
            cell(c, align="R")
        elif kind in ("title", "cause", "heading"):
            shaping(c)
            pdf.set_font("Serif", "BU", 12)
            pdf.multi_cell(width, 6.5, c, align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        elif kind == "center":
            cell(c, align="C")
        elif kind == "lines":
            cell("\n".join(c))
        elif kind == "subject":
            cell(c, style="B", align="J")
        elif kind == "num":
            hanging(f"{c[0]}.", c[1], 0)
            pdf.ln(2.2)
        elif kind == "list":
            for i, x in enumerate(c):
                hanging(f"({chr(97 + i)})", x, 9)
                pdf.ln(1.5)
        elif kind == "party":
            cell(c[0], align="J", gap=0.5)
            cell(c[1], align="R", style="B")
        elif kind == "placedate":
            pl, dl = (c[2], c[3]) if len(c) > 3 else ("Place:", "Date:")
            cell(f"{pl} {c[0]}\n{dl} {c[1]}", gap=0)
        elif kind == "sign":
            if pdf.get_y() + 6.2 * len(c) > pdf.page_break_trigger:
                pdf.add_page()
            cell("\n".join(c), align="R")
        else:
            cell(c, align="J")
    pdf.output(path)
    return path


def save_files(blocks, name, folder=None):
    folder = folder or tempfile.mkdtemp()
    base = os.path.join(folder, name)
    return [to_docx(blocks, base + ".docx"), to_pdf(blocks, base + ".pdf")]
