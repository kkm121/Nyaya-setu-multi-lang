# Nyaya Setu - Gemma 4 QLoRA fine-tune (Kaggle GPU)
# Input : Kaggle dataset with sft.jsonl (built by training/build_sft_data.py)
# Output: LoRA adapter + merged GGUF (Q4_K_M) for the CPU Space

import glob
import json
import math
import os
import random
import re
import subprocess
import sys
import time

T0 = time.time()
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


def log(msg):
    print(f"[{time.time() - T0:7.0f}s] {msg}", flush=True)


def sh(cmd):
    log("$ " + cmd)
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(r.stdout[-3000:], r.stderr[-3000:], flush=True)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {cmd}")


# Setup
sh(f"{sys.executable} -m pip install -q -U transformers peft bitsandbytes accelerate")

import torch
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                          get_cosine_schedule_with_warmup)

BASE = os.environ.get("NYAYA_BASE", "google/gemma-4-E2B-it")
OUT = "/kaggle/working"
MAX_LEN = 1536
EPOCHS = 1
LR = 2e-4
BATCH = 1      # Gemma 4 has a 262k-token vocabulary, so the output layer is large
ACCUM = 16
SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)

# GPU check
assert torch.cuda.is_available(), "No GPU - turn on a GPU accelerator"
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    log(f"GPU {i}: {p.name} {p.total_memory / 1e9:.1f} GB")
# T4 reports bf16 as "supported" but has no real bf16 units; use it only on Ampere (8.x) or newer
BF16 = torch.cuda.get_device_capability(0)[0] >= 8
DTYPE = torch.bfloat16 if BF16 else torch.float16
log(f"dtype: {DTYPE}")

# Data
files = glob.glob("/kaggle/input/**/sft.jsonl", recursive=True)
assert files, "sft.jsonl not found in /kaggle/input"
rows = [json.loads(l) for l in open(files[0], encoding="utf-8")]
random.shuffle(rows)
n_val = max(50, len(rows) // 40)
val_rows, train_rows = rows[:n_val], rows[n_val:]
log(f"examples: train={len(train_rows)} val={len(val_rows)}")

tok = AutoTokenizer.from_pretrained(BASE)
tok.padding_side = "right"
if tok.pad_token is None:
    tok.pad_token = tok.eos_token


def encode(ex):
    msgs = ex["messages"]
    full = tok.apply_chat_template(msgs, tokenize=False)
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    assert full.startswith(prompt), "chat template: prompt is not a prefix of the full text"
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    f_ids = tok(full, add_special_tokens=False)["input_ids"]
    if len(f_ids) > MAX_LEN:
        # cut the sources in the middle of the prompt, keep the answer whole
        ans = f_ids[len(p_ids):]
        keep = MAX_LEN - len(ans)
        if keep < 256:
            return None
        p_ids = p_ids[:keep - 64] + p_ids[-64:]
        f_ids = p_ids + ans
    labels = [-100] * len(p_ids) + f_ids[len(p_ids):]
    return {"input_ids": f_ids, "labels": labels}


train = [e for e in map(encode, train_rows) if e]
val = [e for e in map(encode, val_rows) if e]
n_lab = sum(sum(1 for x in e["labels"] if x != -100) for e in train[:200])
assert n_lab > 0, "all labels are masked - check the chat template"
log(f"encoded: train={len(train)} val={len(val)}; answer tokens in first 200 = {n_lab}")
log(f"avg length = {sum(len(e['input_ids']) for e in train) / len(train):.0f} tokens")


def batches(data, size, shuffle):
    idx = list(range(len(data)))
    if shuffle:
        random.shuffle(idx)
    for i in range(0, len(idx), size):
        chunk = [data[j] for j in idx[i:i + size]]
        n = max(len(c["input_ids"]) for c in chunk)
        ids = torch.full((len(chunk), n), tok.pad_token_id)
        lab = torch.full((len(chunk), n), -100)
        att = torch.zeros((len(chunk), n), dtype=torch.long)
        for k, c in enumerate(chunk):
            L = len(c["input_ids"])
            ids[k, :L] = torch.tensor(c["input_ids"])
            lab[k, :L] = torch.tensor(c["labels"])
            att[k, :L] = 1
        yield ids, lab, att


# Model (4-bit)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=DTYPE, bnb_4bit_use_double_quant=True)
from transformers import AutoModelForImageTextToText

# same model class for training and merging, so adapter names always match
MODEL_CLASS = AutoModelForImageTextToText
try:
    model = MODEL_CLASS.from_pretrained(BASE, quantization_config=bnb, torch_dtype=DTYPE,
                                        device_map={"": 0}, attn_implementation="eager")
except Exception as e:
    log(f"ImageTextToText load failed ({e}); using CausalLM")
    MODEL_CLASS = AutoModelForCausalLM
    model = MODEL_CLASS.from_pretrained(BASE, quantization_config=bnb, torch_dtype=DTYPE,
                                        device_map={"": 0}, attn_implementation="eager")
log(f"model class: {MODEL_CLASS.__name__}")
log(f"GPU memory after load: {torch.cuda.memory_allocated(0) / 1e9:.1f} GB")
# prepare_model_for_kbit_training casts every non-4-bit weight to fp32; Gemma 4's large
# per-layer embeddings then need ~9 GB more and run out of memory on a T4. Do the needed parts by hand.
model.config.use_cache = False
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
model.enable_input_require_grads()

# LoRA only on the language layers (never vision / audio towers)
names = [n for n, _ in model.named_modules()]
lang_re = r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$"
if not any(re.match(lang_re, n) for n in names):
    lang_re = r"^(?!.*(vision|audio)).*layers\.\d+\.(self_attn|mlp)\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$"
targets = [n for n in names if re.match(lang_re, n)]
assert targets, "no LoRA target modules matched"
assert not any(("vision" in n or "audio" in n) for n in targets), "vision/audio layer in targets"
log(f"LoRA targets: {len(targets)} modules, e.g. {targets[:2]}")

model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                                         target_modules=lang_re, task_type="CAUSAL_LM"))
model.print_trainable_parameters()
# LoRA weights train in fp32 for stability (they are small)
for n, p in model.named_parameters():
    if p.requires_grad:
        p.data = p.data.float()
log(f"GPU memory with LoRA: {torch.cuda.memory_allocated(0) / 1e9:.1f} GB")

# Training
opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR, weight_decay=0.01)
steps = math.ceil(len(train) / (BATCH * ACCUM)) * EPOCHS
sched = get_cosine_schedule_with_warmup(opt, max(10, steps // 30), steps)
log(f"optimizer steps: {steps}")


def answer_loss(ids, lab, att):
    # answer tokens are at the end, so only compute logits there (the 262k vocabulary is huge)
    n_ans = int((lab[0] != -100).sum())
    keep = n_ans + 1
    try:
        out = model(input_ids=ids.cuda(), attention_mask=att.cuda(), logits_to_keep=keep)
        logits = out.logits[:, -keep:-1, :].float()
    except TypeError:
        out = model(input_ids=ids.cuda(), attention_mask=att.cuda())
        logits = out.logits[:, -keep:-1, :].float()
    target = lab[:, -n_ans:].cuda()
    return torch.nn.functional.cross_entropy(logits.reshape(-1, logits.size(-1)), target.reshape(-1), ignore_index=-100)


@torch.no_grad()
def eval_loss(limit=100):
    model.eval()
    tot, n = 0.0, 0
    for ids, lab, att in batches(val[:limit], BATCH, False):
        tot += answer_loss(ids, lab, att).item()
        n += 1
    model.train()
    return tot / max(n, 1)


t_eval = time.time()
log(f"val loss before training: {eval_loss():.4f} ({time.time() - t_eval:.0f}s)")
log(f"peak GPU memory in eval: {torch.cuda.max_memory_allocated(0) / 1e9:.1f} GB")
model.train()
# fp16 needs loss scaling so small gradients do not become zero
scaler = torch.amp.GradScaler("cuda", enabled=not BF16)
step, run = 0, []
for epoch in range(EPOCHS):
    for b, (ids, lab, att) in enumerate(batches(train, BATCH, True)):
        loss = answer_loss(ids, lab, att)
        scaler.scale(loss / ACCUM).backward()
        run.append(loss.item())
        if (b + 1) % ACCUM == 0:
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            opt.zero_grad()
            if step == 0:
                log(f"peak GPU memory: {torch.cuda.max_memory_allocated(0) / 1e9:.1f} GB")
            step += 1
            if step % 10 == 0:
                log(f"step {step}/{steps} loss {sum(run[-ACCUM * 10:]) / len(run[-ACCUM * 10:]):.4f}")
            if step % 100 == 0:
                log(f"val loss: {eval_loss():.4f}")
            if time.time() - T0 > 9.5 * 3600:
                log("time budget reached, stopping early")
                break

final_val = eval_loss(len(val))
log(f"peak GPU memory during training: {torch.cuda.max_memory_allocated(0) / 1e9:.1f} GB")
log(f"val loss after training: {final_val:.4f}")
adapter_dir = f"{OUT}/nyaya-lora"
model.save_pretrained(adapter_dir)
tok.save_pretrained(adapter_dir)
log("saved adapter")

# Quick generation check
model.eval()
sample = val_rows[0]["messages"][:-1]
ids = tok.apply_chat_template(sample, add_generation_prompt=True, return_tensors="pt", return_dict=False)
if not torch.is_tensor(ids):   # newer transformers may still return a dict
    ids = ids["input_ids"]
ids = ids.cuda()
with torch.no_grad():
    gen = model.generate(ids, max_new_tokens=300, do_sample=False)
log("SAMPLE OUTPUT:\n" + tok.decode(gen[0][ids.shape[1]:], skip_special_tokens=True))
log("EXPECTED:\n" + val_rows[0]["messages"][-1]["content"])

# Merge into the full model and export GGUF
del model
torch.cuda.empty_cache()
from peft import PeftModel

full = MODEL_CLASS.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="cpu")
peft_full = PeftModel.from_pretrained(full, adapter_dir)
n_lora = sum(1 for n, _ in peft_full.named_modules() if n.endswith("lora_A"))
assert n_lora == len(targets), f"adapter attached to {n_lora} modules, expected {len(targets)}"
log(f"adapter attached to {n_lora} modules")
merged = peft_full.merge_and_unload()
merged_dir = "/tmp/nyaya-merged"
merged.save_pretrained(merged_dir, safe_serialization=True)
tok.save_pretrained(merged_dir)
for f in ["processor_config.json", "chat_template.jinja", "preprocessor_config.json"]:
    try:
        from huggingface_hub import hf_hub_download
        p = hf_hub_download(BASE, f)
        sh(f"cp {p} {merged_dir}/")
    except Exception:
        pass
del full, merged
log("merged model saved")

sh("git clone --depth 1 https://github.com/ggml-org/llama.cpp /tmp/llama.cpp")
sh(f"{sys.executable} -m pip install -q -r /tmp/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt")
sh(f"{sys.executable} /tmp/llama.cpp/convert_hf_to_gguf.py {merged_dir} --outtype bf16 --outfile /tmp/nyaya-bf16.gguf")
sh("cmake -S /tmp/llama.cpp -B /tmp/llama.cpp/build -DGGML_CUDA=OFF -DLLAMA_CURL=OFF && "
   "cmake --build /tmp/llama.cpp/build --target llama-quantize -j 4")
sh(f"/tmp/llama.cpp/build/bin/llama-quantize /tmp/nyaya-bf16.gguf {OUT}/nyaya-gemma4-e2b-Q4_K_M.gguf Q4_K_M")
sh(f"ls -la {OUT}")

json.dump({"base": BASE, "train": len(train), "val": len(val), "steps": steps, "val_loss": final_val,
           "minutes": round((time.time() - T0) / 60)}, open(f"{OUT}/run_info.json", "w"), indent=1)
log("DONE")
