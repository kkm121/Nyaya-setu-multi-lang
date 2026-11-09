# Nyaya Setu - merge the trained LoRA into Gemma 4 E2B and export GGUF (Kaggle, CPU only)
# Input : output of the training notebook (nyaya-lora/)
# Output: nyaya-gemma4-e2b-Q4_K_M.gguf for the CPU Space

import glob
import json
import os
import subprocess
import sys
import time

T0 = time.time()
BASE = "google/gemma-4-E2B-it"
OUT = "/kaggle/working"


def log(msg):
    print(f"[{time.time() - T0:7.0f}s] {msg}", flush=True)


def sh(cmd):
    log("$ " + cmd)
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(r.stdout[-3000:], r.stderr[-3000:], flush=True)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {cmd}")


sh(f"{sys.executable} -m pip install -q -U transformers peft accelerate")
# the CPU image has an old torchao that new peft refuses; it is not used here
sh(f"{sys.executable} -m pip uninstall -y -q torchao")

import torch
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoTokenizer

# Find the adapter (follow linked input folders; unzip if the upload arrived as a zip)
def find_adapter():
    for root, _, files in os.walk("/kaggle/input", followlinks=True):
        log(f"input: {root} {files[:8]}")
        if "adapter_config.json" in files and "adapter_model.safetensors" in files:
            return root
        for f in files:
            if f.endswith(".zip"):
                sh(f"mkdir -p /tmp/adapter && cd /tmp/adapter && unzip -o '{os.path.join(root, f)}'")
    for root, _, files in os.walk("/tmp/adapter"):
        if "adapter_config.json" in files:
            return root
    return None


adapter_dir = find_adapter()
assert adapter_dir, "nyaya-lora adapter not found in /kaggle/input"
log(f"adapter: {adapter_dir}")

# Merge (same model class as training, so adapter names match)
full = AutoModelForImageTextToText.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="cpu")
peft_full = PeftModel.from_pretrained(full, adapter_dir)
n_lora = sum(1 for n, _ in peft_full.named_modules() if n.endswith("lora_A"))
assert n_lora == 205, f"adapter attached to {n_lora} modules, expected 205"
log(f"adapter attached to {n_lora} modules")
merged = peft_full.merge_and_unload()

merged_dir = "/tmp/nyaya-merged"
merged.save_pretrained(merged_dir, safe_serialization=True)
AutoTokenizer.from_pretrained(BASE).save_pretrained(merged_dir)
from huggingface_hub import hf_hub_download
for f in ["processor_config.json", "chat_template.jinja", "preprocessor_config.json"]:
    try:
        sh(f"cp {hf_hub_download(BASE, f)} {merged_dir}/")
    except Exception:
        pass
del full, peft_full, merged
log("merged model saved")

# GGUF export
sh("git clone --depth 1 https://github.com/ggml-org/llama.cpp /tmp/llama.cpp")
# only the gguf writer: llama.cpp's requirements file would downgrade transformers, which then cannot read the Gemma 4 tokenizer
sh(f"{sys.executable} -m pip install -q /tmp/llama.cpp/gguf-py sentencepiece protobuf")
sh(f"{sys.executable} /tmp/llama.cpp/convert_hf_to_gguf.py {merged_dir} --outtype bf16 --outfile /tmp/nyaya-bf16.gguf")
sh("cmake -S /tmp/llama.cpp -B /tmp/llama.cpp/build -DGGML_CUDA=OFF -DLLAMA_CURL=OFF && "
   "cmake --build /tmp/llama.cpp/build --target llama-quantize -j 4")
sh(f"/tmp/llama.cpp/build/bin/llama-quantize /tmp/nyaya-bf16.gguf {OUT}/nyaya-gemma4-e2b-Q4_K_M.gguf Q4_K_M")
sh(f"ls -la {OUT}")
json.dump({"base": BASE, "adapter_modules": n_lora, "minutes": round((time.time() - T0) / 60)},
          open(f"{OUT}/merge_info.json", "w"), indent=1)
log("DONE")
