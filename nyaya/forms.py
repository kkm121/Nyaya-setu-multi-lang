# Form Checking
# Every value typed into a document form is cleaned and checked here before it is used.
# Rules are strict on purpose: a legal document with a fake name, a wrong date or a broken
# amount can hurt the person sending it.

import html
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))   # India has no daylight saving


def today():
    return datetime.now(IST).date()


# Cleaning
def clean(value, max_len=4000):
    if value is None:
        return ""
    text = str(value)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"<[^>]*>", " ", text)                       # no HTML
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:max_len]


def letters(text):
    # letters plus vowel signs: Indian scripts write vowels as marks (ி, ा), which are part of the word
    return [ch for ch in text if unicodedata.category(ch)[0] in "LM"]


def safe(text):
    # for showing user text inside markdown: no HTML, no markdown tricks
    text = html.escape(text, quote=False)
    return re.sub(r"([\\`*_\[\]#|~])", r"\\\1", text)


# Spotting keyboard mash and placeholder text
MASH = {"asd", "asdf", "asdfg", "qwe", "qwer", "qwerty", "zxc", "zxcv", "jkl", "hjkl", "abc", "abcd", "xyz",
        "test", "testing", "sample", "dummy", "na", "n/a", "nil", "none", "null", "xxx", "aaa", "abc xyz",
        "lorem", "ipsum", "fake", "hello", "hi", "ok", "name", "address", "my name", "your name", "jk", "kk"}


def looks_fake(text):
    low = text.lower().strip(" .,-")
    if low in MASH:
        return True
    if re.search(r"([^\W\d_])\1{3,}", low):                # aaaa (letters only: PIN 600008 is fine)
        return True
    latin = [w for w in re.findall(r"[a-z]+", low) if len(w) > 3]
    # long Latin words with no vowels are not names or words (e.g. "sdfgh", "qwrt")
    if latin and sum(1 for w in latin if not re.search(r"[aeiouy]", w)) / len(latin) > 0.5:
        return True
    return False


# Field Checks (each returns (clean value, error key or None))
def check_name(v, required=True):
    v = clean(v, 80)
    if not v:
        return v, "err_required" if required else None
    if re.search(r"\d", v):
        return v, "err_name_digits"
    # letters of any script, their vowel signs (marks), spaces and . ' - only
    ok = all(unicodedata.category(ch)[0] in "LM" or ch in " .'-" for ch in v)
    if len(letters(v)) < 3 or not ok or not unicodedata.category(v[0]).startswith("L"):
        return v, "err_name"
    if looks_fake(v):
        return v, "err_fake"
    return v, None


def check_place(v, required=True):
    # police station, district, city, bank name
    v = clean(v, 80)
    if not v:
        return v, "err_required" if required else None
    if len(letters(v)) < 3 or looks_fake(v):
        return v, "err_place"
    return v, None


def check_address(v, required=True):
    v = clean(v, 300)
    if not v:
        return v, "err_required" if required else None
    if len(v) < 15 or len(letters(v)) < 8 or looks_fake(v):
        return v, "err_address"
    if not re.search(r"(?<!\d)[1-9]\d{2}\s?\d{3}(?!\d)", v):
        return v, "err_pin"
    return v, None


def check_phone(v, required=False):
    v = clean(v, 20)
    if not v:
        return v, "err_required" if required else None
    digits = re.sub(r"[\s\-]", "", v)
    digits = re.sub(r"^(\+91|0091|91|0)(?=[6-9]\d{9}$)", "", digits)
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        return v, "err_phone"
    return digits[:5] + " " + digits[5:], None


def check_email(v, required=False):
    v = clean(v, 120)
    if not v:
        return v, "err_required" if required else None
    if not re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", v):
        return v, "err_email"
    return v, None


def parse_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v, IST).date()
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = clean(v, 40)
    # a date picker may send "2026-11-08 00:00:00"; keep only the date part
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T]\d{2}:\d{2}", s)
    if m:
        s = m.group(1)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def check_date(v, required=True, not_future=True, earliest=date(1950, 1, 1)):
    if v is None or v == "":
        return None, "err_required" if required else None
    d = parse_date(v)
    if d is None:
        return None, "err_date"
    if not_future and d > today():
        return d, "err_future"
    if d < earliest:
        return d, "err_old"
    return d, None


def check_amount(v, required=True, max_value=10 ** 10):
    s = clean(v, 30).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    if not s:
        return None, "err_required" if required else None
    if not re.fullmatch(r"\d+(\.\d{1,2})?", s):
        return None, "err_amount"
    a = float(s)
    if a <= 0 or a > max_value:
        return None, "err_amount_range"
    return a, None


def check_int(v, lo, hi, required=False, err="err_age"):
    s = clean(v, 10)
    if not s:
        return None, "err_required" if required else None
    if not re.fullmatch(r"\d{1,3}", s) or not (lo <= int(s) <= hi):
        return None, err
    return int(s), None


def check_cheque_no(v, required=True):
    s = clean(v, 12).replace(" ", "")
    if not s:
        return s, "err_required" if required else None
    if not re.fullmatch(r"\d{6}", s):
        return s, "err_cheque_no"
    return s, None


def check_ref(v, required=False):
    s = clean(v, 40)
    if not s:
        return s, "err_required" if required else None
    if not re.fullmatch(r"[\w./\-() ]{1,40}", s):
        return s, "err_ref"
    return s, None


def check_text(v, required=True, min_chars=60, min_words=10, max_len=4000):
    v = clean(v, max_len)
    if not v:
        return v, "err_required" if required else None
    words = re.findall(r"\w+", v)
    if len(v) < min_chars or len(words) < min_words:
        return v, "err_facts_short"
    if looks_fake(v) or len(letters(v)) / max(len(v), 1) < 0.5:
        return v, "err_facts_bad"
    # mostly Latin text: most words should look like words
    latin = [w.lower() for w in words if re.fullmatch(r"[A-Za-z]{4,}", w)]
    if len(latin) >= 6 and sum(1 for w in latin if re.search(r"[aeiouy]", w)) / len(latin) < 0.7:
        return v, "err_facts_bad"
    return v, None


def check_period(v, required=True):
    # "01/04/2024 to 31/03/2025", "2023-24", "last three years"
    v = clean(v, 80)
    if not v:
        return v, "err_required" if required else None
    if len(v) < 4 or not (re.search(r"\d{2,4}", v) or len(letters(v)) >= 6) or looks_fake(v):
        return v, "err_period"
    return v, None


def check_lines(v, required=True, max_items=10):
    # RTI questions: one per line
    items = [clean(x, 500) for x in str(v or "").split("\n")]
    items = [re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", x) for x in items if x.strip()]
    if not items:
        return [], "err_required" if required else None
    if len(items) > max_items:
        return items, "err_too_many"
    for x in items:
        if len(x) < 10 or len(letters(x)) < 6 or looks_fake(x):
            return items, "err_question"
    return items, None


def check_choice(v, options, required=True, multi=False):
    if multi:
        vals = [x for x in (v or []) if x in options]
        if required and not vals:
            return vals, "err_choose"
        return vals, None
    if v in options:
        return v, None
    return None, "err_choose" if required else None


# Indian number words (for "Rs. 1,50,000/- (Rupees One Lakh Fifty Thousand only)")
ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
        "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n):
    return ONES[n] if n < 20 else (TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else ""))


def _three(n):
    h, r = divmod(n, 100)
    return ((ONES[h] + " Hundred" + (" " if r else "")) if h else "") + (_two(r) if r else "")


def words_in(n):
    n = int(n)
    if n == 0:
        return "Zero"
    parts = []
    for div, name in ((10 ** 7, "Crore"), (10 ** 5, "Lakh"), (1000, "Thousand")):
        if n >= div:
            q, n = divmod(n, div)
            parts.append((words_in(q) if q >= 100 and name == "Crore" else _two(q) if q < 100 else _three(q)) + " " + name)
    if n:
        parts.append(_three(n))
    return " ".join(parts)


def indian_commas(n):
    s = f"{int(n)}"
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head)
    return head + "," + tail


def money(a):
    rupees = int(round(a * 100)) // 100
    paise = int(round(a * 100)) % 100
    text = f"Rs. {indian_commas(rupees)}"
    text += f".{paise:02d}" if paise else "/-"
    words = f"Rupees {words_in(rupees)}" + (f" and {_two(paise)} Paise" if paise else "") + " only"
    return f"{text} ({words})"


def fmt_date(d):
    return d.strftime("%d.%m.%Y") if d else ""
