# Builds the Hugging Face Space folder (space_build/) from this repo.
# Upload happens only with --push, and only to the same Space so the shared link never changes.
#   python -m scripts.build_space            build folder only
#   python -m scripts.build_space --push     build and upload to kkm121/NyayaSetu

import os
import shutil
import sys

from nyaya.corpus import ROOT

SPACE_ID = "kkm121/NyayaSetu"
OUT = os.path.join(ROOT, "space_build")
LLM_REPO = os.environ.get("NYAYA_LLM_REPO", "unsloth/gemma-4-E2B-it-GGUF")
LLM_FILE = os.environ.get("NYAYA_LLM_FILE", "gemma-4-E2B-it-Q4_K_M.gguf")

SPACE_README = f"""---
title: NyayaSetu
emoji: ⚖️
colorFrom: indigo
colorTo: yellow
sdk: gradio
sdk_version: 6.17.3
python_version: "3.11"
app_file: app.py
pinned: false
license: apache-2.0
short_description: Free legal help in 8 Indian languages, citations checked
preload_from_hub:
  - {LLM_REPO} {LLM_FILE}
  - intfloat/multilingual-e5-small
  - cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
  - facebook/nllb-200-distilled-600M
---

# ⚖️ Nyaya Setu

Free legal help for everyone in India, in your language. Every answer cites the exact law it comes from,
and every statement is checked against that law before you see it.

Source code: https://github.com/kkm121/Nyaya-setu-multi-lang

*This is legal information, not legal advice. Free legal aid: call 15100.*
"""

FILES = ["app.py", "requirements.txt"]
DIRS = ["nyaya"]
DATA = ["data/corpus/chunks.jsonl", "data/corpus/mapping.json",
        "data/index/embeddings.npy", "data/index/corpus_key.txt",
        "data/index/title_embeddings.npy", "data/index/title_key.txt"]   # nyaya/ui_text.json comes with the nyaya folder


def build():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for f in FILES + DATA:
        src = os.path.join(ROOT, f)
        assert os.path.exists(src), f"missing {f} - build the corpus and index first"
        dst = os.path.join(OUT, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    for d in DIRS:
        shutil.copytree(os.path.join(ROOT, d), os.path.join(OUT, d),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(SPACE_README)
    size = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fns in os.walk(OUT) for fn in fns)
    print(f"[INFO] Space folder ready: {OUT} ({size / 1e6:.1f} MB)")


def push():
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_folder(folder_path=OUT, repo_id=SPACE_ID, repo_type="space",
                      commit_message="Nyaya Setu v2: grounded answers, checked citations, drafting, 8 languages")
    api.add_space_variable(SPACE_ID, "NYAYA_LLM_REPO", LLM_REPO)
    api.add_space_variable(SPACE_ID, "NYAYA_LLM_FILE", LLM_FILE)
    api.add_space_variable(SPACE_ID, "HOST", "0.0.0.0")
    print(f"[SUCCESS] Pushed to https://huggingface.co/spaces/{SPACE_ID}")


if __name__ == "__main__":
    build()
    if "--push" in sys.argv:
        push()
