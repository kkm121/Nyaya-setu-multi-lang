# Builds the PDF fonts in nyaya/fonts/: Noto Sans (Latin) merged with each Indian script.
# One font per document avoids a font-fallback bug where English lines next to Indian-script
# lines came out blank or garbled. All Noto fonts are under the SIL Open Font License (OFL.txt).
#   python -m scripts.build_fonts

import os

import requests
from fontTools.merge import Merger

DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nyaya", "fonts")
SRC = "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/{fam}/hinted/ttf/{fam}-{w}.ttf"
SCRIPTS = ["Devanagari", "Bengali", "Gujarati", "Tamil", "Telugu", "Kannada"]


def fetch(fam, w):
    path = os.path.join(DIR, f"{fam}-{w}.ttf")
    if not os.path.exists(path):
        r = requests.get(SRC.format(fam=fam, w=w), timeout=60)
        r.raise_for_status()
        open(path, "wb").write(r.content)
    return path


def main():
    os.makedirs(DIR, exist_ok=True)
    for w in ("Regular", "Bold"):
        fetch("NotoSerif", w)
        latin = fetch("NotoSans", w)
        for script in SCRIPTS:
            indic = fetch(f"NotoSans{script}", w)
            out = os.path.join(DIR, f"Nyaya{script}-{w}.ttf")
            Merger().merge([latin, indic]).save(out)
            print(f"[INFO] {os.path.basename(out)} ({os.path.getsize(out) // 1024} KB)")
    # the merged files replace the separate ones
    for script in SCRIPTS:
        for w in ("Regular", "Bold"):
            p = os.path.join(DIR, f"NotoSans{script}-{w}.ttf")
            if os.path.exists(p):
                os.remove(p)
    for w in ("Regular", "Bold"):
        p = os.path.join(DIR, f"NotoSans-{w}.ttf")
        if os.path.exists(p):
            os.remove(p)


if __name__ == "__main__":
    main()
