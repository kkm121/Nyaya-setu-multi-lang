# Translation Logic
# Legal terms, section numbers and [S1] tags are locked before translating,
# so they come back exactly the same. A back-translation check scores quality.

import os
import re
import time
from functools import lru_cache

import requests
from deep_translator import GoogleTranslator

# Phase 1: the original 8 languages
LANGUAGES = {
    "English": "en", "Hindi": "hi", "Tamil": "ta", "Telugu": "te",
    "Kannada": "kn", "Bengali": "bn", "Marathi": "mr", "Gujarati": "gu",
}
# Phase 2: added only after phase 1 passes its checks
EXTRA_LANGUAGES = {"Malayalam": "ml", "Punjabi": "pa", "Odia": "or", "Urdu": "ur"}

NATIVE_NAMES = {
    "en": "English", "hi": "हिन्दी", "ta": "தமிழ்", "te": "తెలుగు", "kn": "ಕನ್ನಡ", "bn": "বাংলা",
    "mr": "मराठी", "gu": "ગુજરાતી", "ml": "മലയാളം", "pa": "ਪੰਜਾਬੀ", "or": "ଓଡ଼ିଆ", "ur": "اردو",
}

# Things that must never be translated
PROTECT = re.compile(
    r"«[^»]*»"                                             # official law text (kept in English)
    r"|\[S\d+\]"                                          # source tags
    r"|\[TO FILL[^\]]*\]"                                  # drafting placeholders
    r"|\b(?:BNSS|BNS|BSA|IPC|CrPC|CRPC|NI Act|RTI Act|IT Act|DV Act|FIR|NALSA)\b"  # act names
    r"|(?i:\b(?:Section|Article|Sections|Articles)\s+\d{1,3}[A-Z]{0,2}(?:\(\d+\))?)"   # section refs
    r"|\b15100\b"                                          # legal aid number
    r"|\b(?:Ref|Cheque|Invoice|Order)?\.?\s?No\.(?=\s)"           # "Ref. No." is not the word "no"
    r"|:(?=\s|$)"                                          # colons (some models turn them into ः or ஃ)
    r"|\{\w+\}"                                            # {days} placeholders in messages
    # official names and legal terms stay in English (machine translation turned the "Negotiable
    # Instruments Act" into the "Illegal Instructions Act" and "dishonour" into "insult")
    # (?i: ...) = also in CAPITAL headings, e.g. "NEGOTIABLE INSTRUMENTS ACT, 1881"
    r"|(?i:\b(?:Bharatiya Nyaya Sanhita|Bharatiya Nagarik Suraksha Sanhita|Bharatiya Sakshya Adhiniyam"
    r"|Negotiable Instruments Act|Consumer Protection Act|Right to Information Act|Indian Penal Code"
    r"|Code of Criminal Procedure|Indian Evidence Act|Legal Services Authorities Act)(?:,\s*\d{4})?)"
    r"|(?i:\b(?:District Consumer Disputes Redressal Commission|Station House Officer|Superintendent of Police"
    r"|(?:Central |State )?Public Information Officer|Below Poverty Line \(BPL\)))"
    r"|(?i:\bdishonou?r(?:ed)?\b)"
    r"|\b[SDWC]/o\b"
)

MAX_CHUNK = 4500


def lock(text):
    saved = []

    def keep(m):
        saved.append(m.group(0))
        return f" ZX{len(saved) - 1}QX "

    return PROTECT.sub(keep, text), saved


def unlock(text, saved):
    # 1. turn every placeholder into a marker (spaces only: line breaks around it are kept)
    def mark(m):
        i = int(m.group(1))
        return f" \x00{i}\x00 " if i < len(saved) else m.group(0)
    text = re.sub(r"[ \t]*ZX\s*(\d+)\s*QX[ \t]*", mark, text, flags=re.IGNORECASE)
    # some models spell the placeholder in the local script (e.g. "জেডএক্স1কিউএক্স") but keep the number;
    # a word with letters on both sides of a number is never normal text, so restore it
    text = re.sub(r"(?<!\S)[^\s\d.,;:!?।()\[\]\x00]{2,}(\d+)[^\s\d.,;:!?।()\[\]\x00]{2,}", mark, text)
    # 2. tidy spacing of the translated text only
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" ([.,:;!?।])", r"\1", text)
    text = re.sub(r"(?m)^ +| +$", "", text)
    # 3. put the protected text back exactly as it was
    return re.sub(r"\x00(\d+)\x00", lambda m: saved[int(m.group(1))], text).strip()


def split_chunks(text):
    chunks, buf = [], ""
    for para in text.split("\n"):
        if len(buf) + len(para) + 1 > MAX_CHUNK and buf:
            chunks.append(buf)
            buf = ""
        buf = (buf + "\n" + para) if buf else para
    if buf:
        chunks.append(buf)
    return chunks


GTX_URL = "https://translate.googleapis.com/translate_a/single"


@lru_cache(maxsize=2048)
def _google(text, source, target):
    # direct endpoint first (with retries), the deep-translator library as backup
    for wait in (0, 2, 5, 12):
        time.sleep(wait)
        try:
            r = requests.post(GTX_URL, params={"client": "gtx", "sl": source, "tl": target, "dt": "t"},
                              data={"q": text}, timeout=20)
            if r.status_code == 429:
                continue
            r.raise_for_status()
            return "".join(seg[0] for seg in r.json()[0] if seg and seg[0])
        except requests.RequestException:
            continue
    return GoogleTranslator(source=source, target=target).translate(text) or ""


# Local Translator (works offline, never rate limited)
# IndicTrans2 is used when the account has access to it, otherwise NLLB-200.
FLORES = {"en": "eng_Latn", "hi": "hin_Deva", "ta": "tam_Taml", "te": "tel_Telu", "kn": "kan_Knda",
          "bn": "ben_Beng", "mr": "mar_Deva", "gu": "guj_Gujr", "ml": "mal_Mlym", "pa": "pan_Guru",
          "or": "ory_Orya", "ur": "urd_Arab"}
# "auto" uses IndicTrans2 when the account can download it, otherwise NLLB-200
LOCAL_MODEL = os.environ.get("NYAYA_MT_MODEL", "auto")
NLLB = "facebook/nllb-200-distilled-600M"
IT2_EN_INDIC = "ai4bharat/indictrans2-en-indic-dist-200M"
IT2_INDIC_EN = "ai4bharat/indictrans2-indic-en-dist-200M"
# IndicTrans2 runs its own code from the Hub; pin the exact versions that were tested
REVISIONS = {IT2_EN_INDIC: "2cfd0a20057756d756bf3e53528f492afc52f91a",
             IT2_INDIC_EN: "d66a2122ad6d28184f3dc3797b652bd80ae3f65f"}
_local = {}


def _indictrans2_available():
    try:
        from huggingface_hub import hf_hub_download
        hf_hub_download(IT2_EN_INDIC, "config.json")
        hf_hub_download(IT2_INDIC_EN, "config.json")
        return True
    except Exception:
        return False


def local_engine():
    if "engine" not in _local:
        want = LOCAL_MODEL
        if want == "auto":
            want = "indictrans2" if _indictrans2_available() else NLLB
        _local["engine"] = want
        print(f"[INFO] Local translator: {want}")
    return _local["engine"]


def _onnx_stub():
    # IndicTrans2's config imports transformers.onnx (removed in new transformers).
    # Those classes are only for ONNX export, never for translation, so empty stand-ins are enough.
    import sys
    import types
    try:
        import transformers.onnx  # noqa: F401
        return
    except ImportError:
        pass

    class OnnxConfig:
        default_fixed_batch = 2
        default_fixed_sequence = 8

        def __init__(self, *args, **kwargs):
            pass

    class OnnxSeq2SeqConfigWithPast(OnnxConfig):
        pass

    onnx = types.ModuleType("transformers.onnx")
    onnx.OnnxConfig, onnx.OnnxSeq2SeqConfigWithPast = OnnxConfig, OnnxSeq2SeqConfigWithPast
    utils = types.ModuleType("transformers.onnx.utils")
    utils.compute_effective_axis_dimension = lambda dimension, fixed_dimension, num_token_to_add=0: (
        fixed_dimension if dimension <= 0 else dimension) - num_token_to_add
    onnx.utils = utils
    sys.modules["transformers.onnx"] = onnx
    sys.modules["transformers.onnx.utils"] = utils


def _load_tokenizer(name, trust):
    import sys
    from transformers import AutoTokenizer
    try:
        return AutoTokenizer.from_pretrained(name, trust_remote_code=trust, revision=REVISIONS.get(name))
    except AttributeError:
        # IndicTrans2's tokenizer sets special tokens before the base class makes its token store
        # (fine in old transformers, an error in new ones). Give it an empty store first.
        for mod_name, mod in list(sys.modules.items()):
            cls = getattr(mod, "IndicTransTokenizer", None)
            if mod_name.endswith("tokenization_indictrans") and cls and not getattr(cls, "_nyaya_patched", False):
                orig = cls.__init__

                def init(self, *a, _orig=orig, **k):
                    object.__setattr__(self, "_special_tokens_map", {})
                    _orig(self, *a, **k)

                cls.__init__ = init
                cls._nyaya_patched = True
        return AutoTokenizer.from_pretrained(name, trust_remote_code=trust, revision=REVISIONS.get(name))


def _load_model(name, trust):
    from transformers import AutoModelForSeq2SeqLM
    return AutoModelForSeq2SeqLM.from_pretrained(name, trust_remote_code=trust, revision=REVISIONS.get(name)).eval()


def _load(name, trust=False):
    if trust:
        _onnx_stub()
    if name not in _local:
        _local[name] = (_load_tokenizer(name, trust), _load_model(name, trust))
    return _local[name]


def _indic_processor():
    if "ip" not in _local:
        # IndicTransToolkit still imports names that newer transformers moved; point them to the new place
        import transformers.tokenization_utils as tu
        import transformers.tokenization_utils_base as tb
        for n in ("PreTrainedTokenizerBase", "BatchEncoding", "PaddingStrategy"):
            if not hasattr(tu, n) and hasattr(tb, n):
                setattr(tu, n, getattr(tb, n))
        from IndicTransToolkit.processor import IndicProcessor
        _local["ip"] = IndicProcessor(inference=True)
    return _local["ip"]


def translate_sentences(sents, source, target):
    import torch
    src, tgt = FLORES[source], FLORES[target]
    out = []
    if local_engine() == "indictrans2":
        ip = _indic_processor()
        tok, m = _load(IT2_EN_INDIC if source == "en" else IT2_INDIC_EN, trust=True)
        for i in range(0, len(sents), 16):
            batch = ip.preprocess_batch(sents[i:i + 16], src_lang=src, tgt_lang=tgt)
            enc = tok(batch, return_tensors="pt", padding="longest", truncation=True, max_length=256)
            with torch.no_grad():
                gen = m.generate(**enc, max_new_tokens=256, num_beams=1, use_cache=True)
            dec = tok.batch_decode(gen, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            out += ip.postprocess_batch(dec, lang=tgt)
        return out
    tok, m = _load(local_engine())
    tok.src_lang = src
    for i in range(0, len(sents), 16):
        enc = tok(sents[i:i + 16], return_tensors="pt", padding=True, truncation=True, max_length=256)
        with torch.no_grad():
            gen = m.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids(tgt),
                             max_new_tokens=256, num_beams=1)
        out += tok.batch_decode(gen, skip_special_tokens=True)
    return out


# a list marker needs a space after it, so "**heading**" is not read as a bullet
TAIL = re.compile(r"((?:\s*ZX\d+QX)+)\s*([.!?।]?)\s*$")
LINE_PREFIX = re.compile(r"^\s*(?:(?:[-*•>]|\d+[.)])\s+)?")


def _local_translate(text, source, target):
    source = source if source != "auto" else "en"
    lines = text.split("\n")
    # split every line into: list marker, optional **heading**, sentences
    pieces, plan, tails = [], [], []
    for line in lines:
        prefix = LINE_PREFIX.match(line).group(0)
        body = line[len(prefix):]
        head = re.match(r"^\*\*([^*]+)\*\*\s*", body)
        idx_head = None
        colon = ""
        if head:
            idx_head = len(pieces)
            # translate the heading without its colon (IndicTrans2 turns ":" into a visarga)
            text_head = head.group(1).rstrip()
            if text_head.endswith(":"):
                text_head, colon = text_head[:-1], ":"
            pieces.append(text_head)
            body = body[head.end():]
        sents = [s for s in re.split(r"(?<=[.!?।])\s+", body) if s.strip()]
        # placeholders at the end of a sentence (usually [S1] tags) skip the model and are put back after
        for k, sent in enumerate(sents):
            m = TAIL.search(sent)
            tails.append((m.group(1).strip(), m.group(2)) if m and sent[:m.start()].strip() else None)
            if tails[-1]:
                sents[k] = sent[:m.start()] + m.group(2)
        idx = list(range(len(pieces), len(pieces) + len(sents)))
        pieces += sents
        plan.append((prefix, idx_head, idx, colon))
    if not pieces:
        return text
    # pieces that are only placeholders and punctuation have nothing to translate
    real = [i for i, x in enumerate(pieces) if re.sub(r"ZX\d+QX|[\s\W\d]", "", x)]
    done = list(pieces)
    for i, out in zip(real, translate_sentences([pieces[i] for i in real], source, target) if real else []):
        done[i] = out
    # re-attach the end-of-sentence placeholders
    sent_ids = [i for _, idx_head, idx, _ in plan for i in idx]
    for i, tail in zip(sent_ids, tails):
        if tail:
            body = done[i].strip()
            end = body[-1] if body and body[-1] in ".!?।" else tail[1]
            done[i] = body.rstrip(".!?।").rstrip() + " " + tail[0] + end
    result = []
    for line, (prefix, idx_head, idx, colon) in zip(lines, plan):
        if idx_head is None and not idx:
            result.append(line)
            continue
        # trim spaces so markdown bold (**...**) still works
        head = f"**{done[idx_head].strip().rstrip('.?।:ः ')}{colon}** " if idx_head is not None else ""
        result.append(prefix + head + " ".join(done[i].strip() for i in idx))
    return "\n".join(result)


ENGINE = os.environ.get("NYAYA_MT", "auto")   # auto | google | local
_google_down = {"until": 0.0}


def translate(text, target, source="auto"):
    if not text.strip() or target == source:
        return text
    locked, saved = lock(text)
    if ENGINE != "local" and time.time() > _google_down["until"]:
        try:
            out = [_google(chunk, source, target) for chunk in split_chunks(locked)]
            return unlock("\n".join(out), saved)
        except Exception as e:
            if ENGINE == "google":
                raise
            # skip the online service for 10 minutes after a failure
            _google_down["until"] = time.time() + 600
            print(f"[WARNING] Online translation failed ({type(e).__name__}); using local translator")
    if source == "auto":
        source = "en" if target != "en" else (detect_script(text) or "hi")
    return unlock(_local_translate(locked, source, target), saved)


def detect_script(text):
    # guess the language from its script (for the offline path)
    ranges = {"hi": (0x0900, 0x097F), "bn": (0x0980, 0x09FF), "pa": (0x0A00, 0x0A7F), "gu": (0x0A80, 0x0AFF),
              "or": (0x0B00, 0x0B7F), "ta": (0x0B80, 0x0BFF), "te": (0x0C00, 0x0C7F), "kn": (0x0C80, 0x0CFF),
              "ml": (0x0D00, 0x0D7F), "ur": (0x0600, 0x06FF)}
    counts = {k: sum(1 for ch in text if a <= ord(ch) <= b) for k, (a, b) in ranges.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] else None


def detect_language(text):
    try:
        r = requests.post(GTX_URL, params={"client": "gtx", "sl": "auto", "tl": "en", "dt": "t"},
                          data={"q": text[:500]}, timeout=10)
        return r.json()[2]
    except Exception:
        return None


def to_english(text, lang="auto"):
    try:
        return translate(text, "en", lang if lang != "en" else "auto")
    except Exception as e:
        print(f"[WARNING] Input translation failed: {e}")
        return text


def from_english(text, target):
    if target == "en":
        return text, 1.0
    try:
        out = translate(text, target, "en")
    except Exception as e:
        print(f"[WARNING] Output translation failed: {e}")
        return text, 0.0
    return fix_bold(out), 1.0 if protected_ok(text, out) else 0.5


def fix_bold(text):
    # translators sometimes write "** heading **"; markdown only makes "**heading**" bold
    return re.sub(r"\*\*[ \t]*([^*\n]+?)[ \t]*\*\*", r"**\1**", text)


def protected_ok(original, translated):
    # all locked items must survive translation
    want = sorted(m.group(0) for m in PROTECT.finditer(original))
    got = sorted(m.group(0) for m in PROTECT.finditer(translated))
    return want == got


def back_translation_score(original_en, translated, embedder, lang="auto"):
    # translate back to English and compare meaning with the original
    try:
        back = translate(translated, "en", lang)
    except Exception:
        return 0.0
    if embedder is None:
        a, b = set(original_en.lower().split()), set(back.lower().split())
        return len(a & b) / max(len(a | b), 1)
    v = embedder.encode(["query: " + original_en, "query: " + back], normalize_embeddings=True)
    return float(v[0] @ v[1])
