# Builds nyaya/ui_text.json: interface text in every supported language,
# with a back-translation score for each line so weak ones can be reviewed.
# Saves after each language, and skips languages already done.

import json
import os
import sys
import time

from nyaya.translate import ENGINE, EXTRA_LANGUAGES, LANGUAGES, translate
from nyaya.ui_text import EN, EXAMPLES_FOR_TRANSLATION, REVIEWED, UI_PATH


def score(a, b):
    x, y = set(a.lower().split()), set(b.lower().split())
    return len(x & y) / max(len(x | y), 1)


def main():
    langs = dict(LANGUAGES)
    if "--extra" in sys.argv:
        langs.update(EXTRA_LANGUAGES)
    out = {}
    if os.path.exists(UI_PATH):
        out = json.load(open(UI_PATH, encoding="utf-8"))
    for name, code in langs.items():
        if code == "en" or code in REVIEWED:
            continue
        old = out.get(code, {})
        text, checks = dict(old.get("text", {})), dict(old.get("back_translation", {}))
        missing = [k for k in EN if k not in text]
        if not missing and old.get("examples") and "--examples" not in sys.argv:
            continue
        # only translate keys that are new since the last run
        for k in missing:
            v = EN[k]
            text[k] = translate(v, code, "en")
            time.sleep(0 if ENGINE == "local" else 1.0)
            back = translate(text[k], "en", code)
            checks[k] = round(score(v, back), 2)
            time.sleep(0 if ENGINE == "local" else 1.0)
        ex = old.get("examples") or []
        if not ex or "--examples" in sys.argv:
            ex = []
            for e in EXAMPLES_FOR_TRANSLATION:
                ex.append(translate(e, code, "en"))
                time.sleep(0 if ENGINE == "local" else 1.0)
        out[code] = {"name": name, "text": text, "examples": ex, "back_translation": checks,
                     "avg_back_translation": round(sum(checks.values()) / len(checks), 3)}
        print(f"[INFO] {name}: avg back-translation word overlap {out[code]['avg_back_translation']}", flush=True)
        with open(UI_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    print("[INFO] Saved", UI_PATH)


if __name__ == "__main__":
    main()
