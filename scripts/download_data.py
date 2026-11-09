# Downloads the raw law data into data/raw/
# Sources (checked 2026-11-07, see PROJECT_CONTROL.md section 6):
#   GSMS-B/indian-legal-knowledge-base-json  (CC BY 4.0)
#   GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA       (Apache 2.0, used for training only)

import os

import requests

from nyaya.corpus import RAW_DIR

KB = "https://huggingface.co/datasets/GSMS-B/indian-legal-knowledge-base-json/resolve/main/"
QA = "https://huggingface.co/datasets/GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA/resolve/main/"

FILES = {
    "sections.json": KB + "sections.json",
    "ipc_to_bns.json": KB + "raw_acts/ipc_to_bns.json",
    "bns_to_ipc.json": KB + "raw_acts/bns_to_ipc.json",
    "crpc_to_bnss.json": KB + "raw_acts/crpc_to_bnss.json",
    "bnss_to_crpc.json": KB + "raw_acts/bnss_to_crpc.json",
    "iea_to_bsa.json": KB + "raw_acts/iea_to_bsa.json",
    "bsa_to_iea.json": KB + "raw_acts/bsa_to_iea.json",
    "constitution_of_india_articles.jsonl": KB + "raw_acts/constitution_of_india_articles.jsonl",
    "legal_qa_bns_bnss_bsa.jsonl": QA + "bns_bnss_bsa_combined_legal_qa.jsonl",
}


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    for name, url in FILES.items():
        path = os.path.join(RAW_DIR, name)
        if os.path.exists(path):
            print(f"[INFO] {name} already present")
            continue
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"[INFO] Downloaded {name} ({len(r.content) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
