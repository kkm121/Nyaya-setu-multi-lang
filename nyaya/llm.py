# Model Backends
# llamacpp  : runs a GGUF model on CPU (used on the free Hugging Face Space)
# api       : Hugging Face Inference API (needs HF_TOKEN)
# extractive: no model, builds the answer straight from the law text

import os
import re

DEFAULT_REPO = os.environ.get("NYAYA_LLM_REPO", "unsloth/gemma-4-E2B-it-GGUF")
DEFAULT_FILE = os.environ.get("NYAYA_LLM_FILE", "gemma-4-E2B-it-Q4_K_M.gguf")
API_MODEL = os.environ.get("NYAYA_API_MODEL", "google/gemma-4-26B-A4B-it")


def usable_cpus():
    # os.cpu_count() reports the whole host inside containers (e.g. a 2-vCPU Hugging Face Space);
    # too many threads on 2 cores makes the model crawl, so read the container's real CPU limit
    if os.environ.get("NYAYA_THREADS"):
        return max(1, int(os.environ["NYAYA_THREADS"]))
    n = os.cpu_count() or 2
    try:
        n = min(n, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        pass
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()[:2]   # cgroup v2
        if quota != "max":
            n = min(n, max(1, int(int(quota) / int(period))))
    except (OSError, ValueError):
        try:   # cgroup v1
            quota = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
            period = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
            if quota > 0:
                n = min(n, max(1, quota // period))
        except (OSError, ValueError):
            pass
    return max(1, n)


class LlamaCppBackend:
    name = "llamacpp"

    def __init__(self, repo=DEFAULT_REPO, filename=DEFAULT_FILE, n_ctx=4096):
        from llama_cpp import Llama
        local = os.environ.get("NYAYA_LLM_PATH")
        threads = usable_cpus()
        print(f"[INFO] CPU threads for the model: {threads} (os.cpu_count() = {os.cpu_count()})")
        # Gemma 4 has a 262k-word vocabulary; a 256 batch keeps the score buffer at 256 MB instead of 512 MB
        opts = dict(n_ctx=n_ctx, n_batch=int(os.environ.get("NYAYA_N_BATCH", "256")), n_threads=threads, verbose=False)
        if local and os.path.exists(local):
            self.llm = Llama(model_path=local, **opts)
            self.label = os.path.basename(local)
        else:
            self.llm = Llama.from_pretrained(repo_id=repo, filename=filename, **opts)
            self.label = f"{repo}/{filename}"
        # reuse the work done on the same system prompt between questions
        from llama_cpp import LlamaRAMCache
        self.llm.set_cache(LlamaRAMCache(capacity_bytes=1 << 30))

    def chat(self, messages, max_tokens=500, temperature=0.1, stream=False):
        out = self.llm.create_chat_completion(messages=messages, max_tokens=max_tokens,
                                              temperature=temperature, top_p=0.9, stream=stream)
        if not stream:
            return out["choices"][0]["message"]["content"]
        return (c["choices"][0]["delta"].get("content", "") for c in out)


class ApiBackend:
    name = "api"

    def __init__(self, model=API_MODEL):
        from huggingface_hub import InferenceClient
        self.client = InferenceClient(model=model, token=os.environ.get("HF_TOKEN"))
        self.label = model

    def chat(self, messages, max_tokens=500, temperature=0.1, stream=False):
        if not stream:
            r = self.client.chat_completion(messages=messages, max_tokens=max_tokens, temperature=temperature)
            return r.choices[0].message.content
        r = self.client.chat_completion(messages=messages, max_tokens=max_tokens,
                                        temperature=temperature, stream=True)
        return (c.choices[0].delta.content or "" for c in r)


class ExtractiveBackend:
    name = "extractive"
    label = "extractive (no model)"

    def chat(self, messages, max_tokens=0, temperature=0, stream=False):
        return None  # pipeline builds the answer itself


def first_sentences(text, n=2, limit=320):
    text = re.sub(r"^\s*\d+[A-Z]?\.\s*[^—]{0,150}—", "", text.strip())   # drop "103. Title.—"
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.;:])\s+", text)
    out = " ".join(parts[:n])
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + " ..."


def extractive_answer(results, notes):
    if not results:
        return "NOT_IN_SOURCES"
    top = results[0]
    pos = {(r["act"], str(r["section"]).upper()): i for i, r in enumerate(results, 1)}
    # «...» marks official law text: it is shown in English and never machine translated
    # name the top two matches: a fast answer has no model to choose between close sections
    short = (f"**In short:** The laws that best match your question are {top['act_label']} {top['unit']} "
             f"{top['section']} «({top['title']})» [S1]")
    if len(results) > 1:
        second = results[1]
        short += (f" and {second['act_label']} {second['unit']} {second['section']} «({second['title']})» [S2]")
    short += "."
    # old -> new questions: lead with the matching section
    for n in notes:
        t = pos.get((n["to_act"], str(n["to_section"] or "").upper()))
        if t:
            new = results[t - 1]
            short = (f"**In short:** The matching section is {new['act_label']} {new['unit']} {new['section']} "
                     f"«({new['title']})» [S{t}].")
            break
    lines = [short, "", "**What the law says (official text):**"]
    for i, r in enumerate(results[:4], 1):
        lines.append(f"- {r['act_label']} {r['unit']} {r['section']} «({r['title']}): {first_sentences(r['text'])}» [S{i}]")
    tagged = []
    for n in notes[:3]:
        t = pos.get((n["to_act"], str(n["to_section"] or "").upper()))
        if t:
            tagged.append(f"- «{n['note']}» [S{t}]")
    if tagged:
        lines += ["", "**Old and new law:**"] + tagged
    lines += ["", "**What you can do now:**",
              "- Read the sections below in full and keep copies of all your documents.",
              "- Call the free legal aid helpline 15100 or visit your District Legal Services Authority."]
    return "\n".join(lines)


def load_backend(kind=None):
    kind = kind or os.environ.get("NYAYA_BACKEND", "llamacpp")
    try:
        if kind == "api" and os.environ.get("HF_TOKEN"):
            return ApiBackend()
        if kind == "llamacpp":
            return LlamaCppBackend()
    except Exception as e:
        print(f"[WARNING] Could not load {kind} backend: {e}. Using extractive mode.")
    return ExtractiveBackend()
