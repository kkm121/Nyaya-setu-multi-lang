# Drafting tests: every document builds from valid input, and bad or hostile input is refused.
# No internet or model needed.

import os
from datetime import timedelta

import pytest

from nyaya import drafting as D
from nyaya import forms as F
from tests.sample_forms import SAMPLES, d

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def build(doc_type, raw):
    v, errs, warns = D.validate(doc_type, raw)
    assert not errs, D.error_lines(errs)
    return D.build_document(doc_type, v, v.get("facts") or "")


# Valid documents
@pytest.mark.parametrize("doc_type", list(DOC_TYPES := D.DOC_TYPES))
def test_every_document_builds_in_all_formats(doc_type, tmp_path):
    blocks = build(doc_type, SAMPLES[doc_type])
    md = D.to_markdown(blocks)
    assert "Ravi Kumar" in md and "«" not in md and "TO FILL" not in md
    docx, pdf = D.save_files(blocks, "t", str(tmp_path))
    assert os.path.getsize(docx) > 5000 and os.path.getsize(pdf) > 5000


def test_reply_notice_has_legal_structure():
    md = D.to_markdown(build("reply_notice", SAMPLES["reply_notice"]))
    for part in ["BY REGISTERED POST A.D.", "REPLY TO LEGAL NOTICE", "To,", "Subject: Reply to your Legal Notice",
                 "S/o Mohan Kumar", "aged about 34 years", "denied in their entirety", "without prejudice",
                 "copy of this reply has been retained", "Place: Chennai", "Yours faithfully"]:
        assert part in md, part
    assert "That I posted a YouTube review" in md          # facts become numbered "That ..." paragraphs


def test_cheque_notice_amount_in_words():
    md = D.to_markdown(build("cheque_notice", SAMPLES["cheque_notice"]))
    assert "Rs. 1,50,000/- (Rupees One Lakh Fifty Thousand only)" in md
    assert "fifteen (15) days" in md and "Section 138" in md


def test_consumer_complaint_court_format():
    md = D.to_markdown(build("consumer_complaint", SAMPLES["consumer_complaint"]))
    for part in ["BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION", "... Complainant", "Versus",
                 "... Opposite Party", "MOST RESPECTFULLY SHOWETH", "PRAYER", "VERIFICATION", "Section 34", "Section 69"]:
        assert part in md, part


def test_rti_bpl_has_no_fee_ref_needed():
    raw = dict(SAMPLES["rti_application"], fee="bpl", fee_ref="")
    md = D.to_markdown(build("rti_application", raw))
    assert "Below Poverty Line" in md and "Section 7(5)" in md


# Bad input is refused
BAD_NAMES = ["", "jk", "asd", "aaaa", "sdfgh", "R4vi", "Ravi@", "<script>alert(1)</script>", "test", "12345", "x" * 200]


@pytest.mark.parametrize("bad", BAD_NAMES)
def test_bad_names_refused(bad):
    _, errs, _ = D.validate("reply_notice", dict(SAMPLES["reply_notice"], s_name=bad))
    assert "s_name" in errs


@pytest.mark.parametrize("bad", ["suwan", "asd", "Chennai", "12, Gandhi Street, Adyar, Chennai",
                                 "Gandhi Street 12345", "aaaa bbbb cccc 600020"])
def test_bad_addresses_refused(bad):
    _, errs, _ = D.validate("reply_notice", dict(SAMPLES["reply_notice"], s_address=bad))
    assert "s_address" in errs


@pytest.mark.parametrize("bad", ["19.02.", "31/02/2025", "2025-13-01", "tomorrow", "00/00/0000"])
def test_bad_dates_refused(bad):
    _, errs, _ = D.validate("reply_notice", dict(SAMPLES["reply_notice"], n_date=bad))
    assert "n_date" in errs


def test_future_date_refused():
    future = (F.today() + timedelta(days=3)).isoformat()
    _, errs, _ = D.validate("police_complaint", dict(SAMPLES["police_complaint"], incident_date=future))
    assert errs.get("incident_date") == "err_future"


@pytest.mark.parametrize("bad", ["", "asd asd", "sdfg hjkl qwrt zxcv bnmm lkjh gfds poiu ytre wqas dfgh jklm zxcv bnmm",
                                 "<b><i></i></b>", "1234567890 1234567890 1234567890 1234567890 1234567890 1234567890"])
def test_bad_facts_refused(bad):
    _, errs, _ = D.validate("police_complaint", dict(SAMPLES["police_complaint"], facts=bad))
    assert "facts" in errs


@pytest.mark.parametrize("field,bad", [("amount", "-500"), ("amount", "abc"), ("amount", "0"), ("amount", "1e9"),
                                       ("cheque_no", "12345"), ("cheque_no", "ABCDEF"), ("s_phone", "12345"),
                                       ("s_phone", "5876543210"), ("s_email", "ravi@"), ("s_age", "7"),
                                       ("s_age", "200")])
def test_bad_numbers_refused(field, bad):
    _, errs, _ = D.validate("cheque_notice", dict(SAMPLES["cheque_notice"], **{field: bad}))
    assert field in errs


def test_html_and_markdown_cannot_inject():
    raw = dict(SAMPLES["police_complaint"],
               facts="My phone was stolen <img src=x onerror=alert(1)> at the bus stand by **two men** on a bike. "
                     "They ran away [click](http://evil.example) and I could not catch them at all.")
    v, errs, _ = D.validate("police_complaint", raw)
    assert not errs
    md = D.to_markdown(D.build_document("police_complaint", v, v["facts"]))
    assert "<img" not in md and "onerror" not in md
    assert "\\*\\*two men\\*\\*" in md and "\\[click\\]" in md       # shown as text, not formatting


# Rules between fields
def test_received_before_notice_date_refused():
    _, errs, _ = D.validate("reply_notice", dict(SAMPLES["reply_notice"], n_date=d(5), n_received=d(9)))
    assert errs.get("n_received") == "err_order_received"


def test_cheque_rules():
    _, errs, _ = D.validate("cheque_notice", dict(SAMPLES["cheque_notice"], cheque_date=d(5), return_date=d(10)))
    assert errs.get("return_date") == "err_order_cheque"
    _, errs, _ = D.validate("cheque_notice", dict(SAMPLES["cheque_notice"], cheque_date=d(80), presented_date=d(50),
                                                  return_date=d(45)))
    assert errs["return_date"][0] == "err_138_late"            # more than 30 days: no Section 138 notice
    _, errs, warns = D.validate("cheque_notice", dict(SAMPLES["cheque_notice"], cheque_date=d(130),
                                                      presented_date=d(15), return_date=d(12)))
    assert not errs and warns                                   # cheque older than 3 months: warning


def test_relation_needs_a_name():
    _, errs, _ = D.validate("reply_notice", dict(SAMPLES["reply_notice"], s_relname=""))
    assert errs.get("s_relname") == "err_relname_needed"


def test_deposit_rules():
    _, errs, _ = D.validate("deposit_notice", dict(SAMPLES["deposit_notice"], deduction="70000"))
    assert errs.get("deduction") == "err_deduction"
    _, errs, _ = D.validate("deposit_notice", dict(SAMPLES["deposit_notice"], tenancy_start=d(10), vacated_on=d(40)))
    assert errs.get("vacated_on") == "err_order_vacated"


def test_consumer_amounts_needed_for_chosen_reliefs():
    _, errs, _ = D.validate("consumer_complaint", dict(SAMPLES["consumer_complaint"], comp_amount=""))
    assert errs.get("comp_amount") == "err_required"


def test_rti_fee_number_needed_for_postal_order():
    _, errs, _ = D.validate("rti_application", dict(SAMPLES["rti_application"], fee_ref=""))
    assert errs.get("fee_ref") == "err_fee_ref"


def test_options_cannot_be_forged():
    _, errs, _ = D.validate("reply_notice", dict(SAMPLES["reply_notice"], reliefs=["pay me 1 crore"], days="999"))
    assert "reliefs" in errs and "days" in errs


# Indian languages
def test_indian_script_names_and_facts_accepted(tmp_path):
    raw = dict(SAMPLES["reply_notice"], s_name="ரவி குமார்", s_relname="மோகன் குமார்",
               facts="எனது யூடியூப் சேனலில் ஒரு பொருளைப் பற்றி நேர்மையான விமர்சன வீடியோ வெளியிட்டேன். "
                     "அந்த வீடியோவில் எந்தப் பொய்யான தகவலும் இல்லை.")
    v, errs, _ = D.validate("reply_notice", raw)
    assert not errs, D.error_lines(errs)
    blocks = D.build_document("reply_notice", v, "I posted an honest review video. There is no false information.")
    _, pdf = D.save_files(blocks, "ta", str(tmp_path))
    assert os.path.getsize(pdf) > 5000


def test_letter_words_are_hand_written():
    assert D.letter_word("To,", "hi") == "सेवा में,"
    assert D.letter_word("Yours faithfully,", "hi") == "भवदीय,"
    assert D.letter_word("Date: 08.11.2026", "ta") == "தேதி: 08.11.2026"
    assert D.letter_word("Something else", "ta") is None


@pytest.mark.parametrize("text,kept", [
    ("LEGAL NOTICE UNDER SECTION 138 OF THE NEGOTIABLE INSTRUMENTS ACT, 1881",
     ["SECTION 138", "NEGOTIABLE INSTRUMENTS ACT, 1881"]),
    ("BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION, CHENNAI",
     ["DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION"]),
    ("Demand notice for dishonour of Cheque No. 004512", ["dishonour", "Cheque No."]),
    ("Ravi Kumar, S/o Mohan Kumar", ["S/o"]),
    ("To the Station House Officer and the Superintendent of Police", ["Station House Officer", "Superintendent of Police"]),
])
def test_legal_names_never_translated(text, kept):
    from nyaya.translate import lock
    _, saved = lock(text)
    for k in kept:
        assert k in saved, k


def test_pdf_mixed_script_lines_all_render(tmp_path):
    import pymupdf
    blocks = [("para", "நான் இங்கு வசிக்கிறேன்"), ("party", ("QuickMart Electronics, Chennai 600002", "... எதிர் கட்சி")),
              ("num", (1, "புகார் Section 35 of the Act", "fact")), ("para", "Plain English line")]
    path = D.to_pdf(blocks, str(tmp_path / "m.pdf"))
    text = pymupdf.open(path)[0].get_text()
    for must in ["QuickMart Electronics, Chennai 600002", "Section 35 of the Act", "Plain English line"]:
        assert must in text, must          # a font fallback bug once blanked or garbled these lines


def test_amount_words():
    assert F.money(150000) == "Rs. 1,50,000/- (Rupees One Lakh Fifty Thousand only)"
    assert F.money(10000000) == "Rs. 1,00,00,000/- (Rupees One Crore only)"
    assert F.money(99.5) == "Rs. 99.50 (Rupees Ninety Nine and Fifty Paise only)"


def test_dates_use_india_time():
    assert F.IST.utcoffset(None) == timedelta(hours=5, minutes=30)
