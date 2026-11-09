# Nyaya Setu v2: Project Control File

**Read this file before every work session. Update the checklist and decision log as you go.**
It is the single source of truth for what we are building and the rules that keep it honest.
Anyone working on this repo must follow it.

---

## 1. Mission

Help ordinary people in India, with no legal background, understand their legal problem and what to do next.
Ground every answer in the actual text of the law, show the sections, and draft a usable reply document
when the user asks for one. It must be more trustworthy than current commercial legal AI.
(Stanford 2024/25 measured 17–34% hallucination in Lexis+ AI and Westlaw AI.)

**Users:** non-lawyers on phones. Many prefer an Indian language over English.
**Typical moments:** a police notice, an FIR, a landlord dispute, a cheque bounce, a consumer problem, a legal notice received.

## 2. Goals / Non-goals / Anti-goals

**Goals**
- Correct current law: BNS / BNSS / BSA, in force since **1 July 2024**, plus mapping from old IPC / CrPC / IEA sections.
  Offences committed before 1 July 2024 are still tried under the old codes, so both must be answerable.
- Every legal claim cites a retrieved section, and citations are machine-checked before display.
- When the sources do not support an answer, say so plainly and point to free legal aid (NALSA helpline **15100**).
- Draft documents: reply to a legal notice, police complaint, consumer complaint, RTI application, cheque-bounce (s.138 NI Act) notice.
- Multilingual, in two phases (owner's rule):
  - **Phase 1: the current 8 must work accurately first.** English, Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Gujarati.
  - **Phase 2: only after phase 1 passes its checks**, add 3–4 more: Malayalam, Punjabi, Odia, Urdu.
  - Accuracy guards: section numbers, act names and `[Sx]` tags are protected from translation; every
    translated answer gets a back-translation check, and the English original is shown when the check is weak.
- Mobile-first UI that a first-time user understands without help.
- Runs on the free Hugging Face CPU Space. Heavy training happens on Kaggle.

**Non-goals**
- Predicting court outcomes or judges' decisions.
- Replacing a lawyer. The app must say this clearly.
- Full case-law search across millions of judgments (a possible later phase).

**Anti-goals (failure even if it "works")**
- Citing a section that was not retrieved, or that does not exist.
- Quoting IPC numbers for an offence that happened after 1 July 2024 without saying the BNS equivalent.
- Confident advice on topics outside the indexed law.
- Breaking the existing shared link `https://huggingface.co/spaces/kkm121/NyayaSetu`.
- Collecting or storing users' personal data.

## 3. Rules for the agent building this (anti-hallucination for the developer)

1. **Never invent a dataset, model ID, URL, section number or API.** Verify each one exists (HTTP / API call)
   before writing it into code or docs. Record the check in the Data Registry (section 6).
2. **Statute text comes only from official or verifiable sources.** Prefer India Code / Gazette / government PDFs.
   If a third-party copy is used, spot-check at least 5 sections against an official source and record the result.
3. **Never claim something works without running it.** "Done" means the command ran and its output is shown.
4. **Do not push to GitHub or the live HF Space without the owner's explicit OK.** Work on branch `upgrade/nyaya-setu-v2`.
5. **Do not read or print credential files** (`~/.kaggle/*`, HF tokens). Use the CLIs, which read them themselves.
6. **Keep a held-out evaluation set frozen.** Never train on `eval/` questions.
7. **Ship rule for the fine-tuned model (fixed in advance):** use the new model in the app only if, on the
   frozen eval set, it beats the base model on citation accuracy and does not hallucinate more sections.
   Otherwise ship base model + retrieval.
8. When unsure, write the uncertainty into section 8 (Open questions) instead of guessing.
9. **Code style (owner's rule):** keep comments short and plain, like the original `app.py`
   (`# Translation Logic`, `# Inference Generation`). No long docstrings, no jargon in comments.
10. **README (owner's rule):** as good as or better than `kkm121/qr-gen`: badges, contents table, file tree,
    screenshot table, "how it works" tables, verified test output, design decisions. Every claim in it must be
    something we actually ran or checked.

## 4. Rules for the app at runtime (anti-hallucination for the model)

These are enforced in code (`nyaya/verify.py`), not just asked for in the prompt.

1. **Retrieve first, answer second.** The model sees only the retrieved sections, labelled `[S1]..[Sn]`.
2. **Cite or drop.** Every sentence with a legal claim must carry `[Sx]`. Sentences citing an ID that was not
   retrieved are removed.
3. **Section-number check.** Any "Section N of <Act>" in the answer must match a retrieved section.
   Otherwise the sentence is removed and a warning is shown.
4. **Support check.** Each cited sentence must overlap meaningfully with its cited source text.
   Weakly supported sentences are flagged "unverified".
5. **Abstain.** If retrieval confidence is low, or more than half the answer was removed, show a
   "not sure" answer with the relevant sections and the legal-aid pointer instead.
6. **Old vs new law.** If the user mentions IPC / CrPC / IEA sections, show the BNS / BNSS / BSA equivalent
   from the mapping table. If the offence date is before 1 July 2024, explain that the old code applies.
7. **Drafts are templates filled from the user's facts.** Fixed legal structure, with placeholders
   `[TO FILL: ...]` for anything the user did not give. Never invent names, dates or amounts.
8. Every answer ends with a short "This is not legal advice" note and the legal-aid contact.

## 5. Architecture (v2)

```
User (any language)
  → language detect / translate to English for retrieval      nyaya/translate.py
  → query understanding: section refs, act names, dates        nyaya/query.py
  → hybrid retrieval: BM25 + multilingual embeddings → RRF     nyaya/retrieve.py
     + exact section lookup + IPC↔BNS mapping expansion
  → (optional) cross-encoder rerank
  → grounded prompt with [S1..Sn]                               nyaya/prompts.py
  → LLM backend: llama.cpp GGUF (CPU) | transformers (GPU)      nyaya/llm.py
                 | extractive fallback (no LLM)
  → citation + section + support verification, abstain          nyaya/verify.py
  → answer in user language + source cards + confidence
Drafting: intake form → template + LLM fill → verify → DOCX/PDF  nyaya/drafting.py
UI: Gradio, mobile-first, tabs: Ask · Draft · Old→New finder · Help    app.py
Training (Kaggle): grounded SFT data → QLoRA → GGUF            training/
Eval: frozen question set, metrics: section recall, citation   eval/
      precision, hallucinated-section rate, abstain correctness
```

## 6. Data Registry (verify before use)

| Source | What | Status | Check |
|---|---|---|---|
| `data/ipc_dataset.json` (existing) | 27,050 Constitution/IPC Q&A | present | IPC part is pre-2024 law; use only with old-law tag |
| HF `GSMS-B/indian-legal-knowledge-base-json` → `sections.json` | 12,174 sections, 102 acts (BNS, BNSS, BSA, IPC, CrPC, IEA, NI Act, CPA, RTI, Constitution…) | downloaded, CC-BY-4.0 | 8 section texts spot-checked (BNS 103, 318, 152; BNSS 173; BSA 63; NIA 138; CPA 35; RTI 6): all correct. 344 near-empty rows (omitted sections) to filter |
| same repo → `ipc_to_bns`, `crpc_to_bnss`, `iea_to_bsa` (+ reverse) | old↔new section mapping | downloaded, CC-BY-4.0 | 11 spot checks correct: IPC 302→BNS 103, 420→318(4), 498A→85, 376→64, 124A/377/497 deleted; CrPC 154→BNSS 173, 41→35(1), 438→482; IEA 65B→BSA 63 |
| HF `GSMS-B/Indian-Legal-QA-BNS-BNSS-BSA` | 6,354 Q&A tied to BNS/BNSS/BSA sections | downloaded, Apache-2.0 | used for training only, with section ids kept |
| `GSMS-B/.../constitution_of_india_articles.jsonl` | 506 articles | downloaded, CC-BY-4.0 | Article 20 text checked |
| Models verified on HF (exist, licence) | `intfloat/multilingual-e5-small` (MIT), `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (Apache), `google/gemma-4-E2B-it` / `E4B-it` (Apache), `unsloth/gemma-4-E2B-it-GGUF` / `E4B` (Apache), `Qwen/Qwen2.5-3B-Instruct-GGUF`, `unsloth/Qwen3-4B-Instruct-2507-GGUF` (Apache) | checked 2026-11-07 | |

## 7. Checklist

- [x] Research: legal AI SOTA, Indian legal datasets, hallucination studies
- [x] Branch `upgrade/nyaya-setu-v2` created
- [x] Collect and verify statute corpora (102 acts incl. BNS, BNSS, BSA, Constitution, IPC, CrPC, NI Act, CPA, RTI)
- [x] IPC↔BNS, CrPC↔BNSS, IEA↔BSA mapping table, 11 spot checks correct
- [x] Chunked corpus with metadata (`data/corpus/chunks.jsonl`, 16,379 chunks)
- [x] Unit tests: 28 passing (`pytest tests`)
- [x] Frozen eval set: 79 questions (64 answerable, 15 unanswerable; 10 unanswerable added before measuring) + 20 hand-written Hindi questions; every gold section checked to exist
- [x] Hybrid retrieval + exact lookup + mapping expansion + title index + reranker + glossary (recall@5 0.891)
- [x] Prompt templates (answer, abstain, draft) and verifier, with tests
- [x] Drafting module with DOCX/PDF export, with tests
- [x] Training data: 8,158 grounded examples (QA 4,081 · mapping 603 · abstain 414 · v1 3,060)
- [x] Phase 1 languages: locked terms verified in all 8; Hindi UI hand-reviewed; 6 others machine-translated (labelled)
- [x] IndicTrans2 working (pinned env `.venv3`, transformers 4.46.3)
- [x] IndicTrans2 vs NLLB: IndicTrans2 wins (Hindi recall@5 0.90 vs 0.80, ~2x faster, equal meaning); locked terms 56/56 after tail-tag + transliteration fixes
- [x] Base Gemma e2e: 28/35 correct law cited, 2/35 wrong abstain, 10/15 unanswerable declined, 96.4% supported, 37.9 s/answer
- [x] Kaggle v3 training done (498 steps, 4.7 h, val loss 3.32 → 0.30); adapter downloaded. Crashed after saving, in the sample-generation check (apply_chat_template returned a dict) — fixed in the script
- [x] Merge + GGUF on Kaggle CPU (5 runs; fixes: dataset input, torchao, gguf-py only)
- [x] Ship rule applied: fine-tuned 22/35 correct law vs base 28/35, 8 vs 2 wrong 'not sure', 89.5% vs 96.4% supported → **ship base model**. Fine-tune is better only at declining (15/15 vs 10/15) and speed (20 s vs 38 s)
- [ ] Per-language retrieval eval (incl. 20 hand-written Hindi questions)
- [ ] Phase 2 languages (Malayalam, Punjabi, Odia, Urdu), only after phase 1 passes
- [ ] New UI, run locally, all tabs checked in a browser
- [ ] README rewritten (qr-gen standard) with real screenshots and real test output
- [ ] Frozen eval set (`eval/`) and eval script; baseline numbers recorded
- [ ] Training data builder (grounded, cited, with abstain examples)
- [ ] Kaggle QLoRA notebook pushed and run; adapter + GGUF downloaded
- [ ] Ship-rule comparison recorded (section 3, rule 7)
- [ ] Space deploy package prepared; owner approves; pushed; link checked

## 8. Open questions

- Which LLM is best for Indic legal answers at a size the CPU Space can serve (Gemma 4 E2B/E4B vs Qwen 2.5 3B)? Decide by eval.

## 9. Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-07 | Retrieval-grounded design, with fine-tuning as a supporting step | Fine-tuning alone hallucinates; IPC is outdated; RAG plus verification is the strongest evidence-backed approach |
| 2026-11-07 | Scope: criminal (BNS/BNSS/BSA + old codes) and common civil (tenancy, consumer, cheque bounce, RTI) | Owner said "normal people"; my call on the list |
| 2026-11-07 | Keep the same HF Space name so the shared link never changes | Owner's requirement |
| 2026-11-07 | Removed the "Stop Server" button | On a public Space any visitor could shut the app down for everyone |
| 2026-11-07 | Do NOT de-duplicate repeated lines in statute text | Tried it; it deleted legitimately repeated provisos in 204 sections (e.g. BNSS 173). The "duplicates" were from my own debug join of overlapping chunks. Law text must stay exact |
| 2026-11-07 | Translation: Google (gtx endpoint) → local model fallback, with a 10-minute circuit breaker | The `deep-translator` scrape path is blocked by a Google captcha on this network, and gtx rate-limited after ~150 calls. A public app cannot depend on it alone |
| 2026-11-07 | Local translator: NLLB-200-distilled-600M now; IndicTrans2-dist-200M when the owner accepts its gated terms | IndicTrans2 is the research best for Indic (MIT licence) but gated; NLLB is ungated (CC-BY-NC: fine for this non-commercial project) |
| 2026-11-07 | Gemma 4 turn markers are `<\|turn>user` / `<\|turn>model` / `<turn\|>` (rendered from the real tokenizer) | Not Gemma 3's `<start_of_turn>`. Training masks are computed from the template itself, with an assert that labels are not all masked |
| 2026-11-07 | Train and merge with the same model class; assert adapter attaches to every target module | Mismatched class names can make a LoRA merge silently do nothing |
| 2026-11-07 | Ship precomputed embeddings with the app | 16k chunks take ~45 min on a fast desktop CPU; hours on the 2-vCPU Space |
| 2026-11-07 | Retrieval upgrades kept only when measured: title index (+0.125 recall@5), reranker (+0.063), lay-term glossary (+0.094) | Baseline 0.609 → 0.891. Glossary was written after seeing eval misses, so 0.797 (without glossary) is the conservative figure and both are reported |
| 2026-11-07 | Abstain threshold fixed at reranker score −5 BEFORE adding 10 new unanswerable questions | Avoids tuning the threshold on the 5 original examples |
| 2026-11-07 | Unchecked model text is never shown; the UI shows a word count while the model writes | Streaming raw drafts would let a user read or screenshot a claim the checker later removes |
| 2026-11-07 | Hindi interface text reviewed by hand; English UI rewritten without idioms | Machine translation reversed "the law this answer is based on" and used "against (opposing)" for "checked against"; back-translation word overlap still scored it 1.00. Automatic checks cannot certify translation accuracy, so other languages are labelled machine-translated |
| 2026-11-07 | Replaced rank_bm25 with an inverted-index BM25 | Identical scores on test queries, ~50–100× faster per query |
| 2026-11-07 | Local translator auto-selects IndicTrans2 (dist-200M, both directions) when the HF token can download it, else NLLB-200 | Owner accepted the IndicTrans2 terms, but as of 15:05 the `kkm121` token still gets 403 on all 6 IndicTrans2 repos. Code path ready (toolkit shim tested); quality comparison pending access. On the Space it needs an `HF_TOKEN` secret from an authorised account |
| 2026-11-07 | App pinned to transformers 4.46.3 / sentence-transformers 3.3.1 / gradio 6.17.3 (new env `.venv3`); IndicTrans2 code pinned to tested revisions | IndicTrans2's remote code breaks on transformers 5.22 in 4 places (onnx import, tokenizer init, tie_weights, _tie_or_clone_weights). Patched 3, stopped at the 4th instead of stacking hacks. The app never needed transformers 5 (Gemma runs in llama.cpp). In the pinned env IndicTrans2 loads with no patches; all 30 tests pass. Revisions pinned because the Hub re-downloaded new remote code mid-session |
| 2026-11-07 | Translator layout fix: a list marker must be followed by a space; headings translated without their colon | `**In short:**` was being read as a bullet, and IndicTrans2 turns ':' into a visarga (ः) |
| 2026-11-07 | Ship the base Gemma 4 E2B, not the fine-tune | Ship rule (set before training) failed: fewer correct citations, more wrong abstains, lower support. Fine-tune over-abstains; next try needs fewer NOT_IN_SOURCES examples and fuller answers |
| 2026-11-07 | Kaggle: `machine_shape: NvidiaL4` gives T4×2 for normal notebooks; T4 needs fp16 + GradScaler; skip `prepare_model_for_kbit_training` (casts Gemma 4 per-layer embeddings to fp32 → OOM); compute logits only for answer tokens (262k vocab) | Kaggle runs v1 and v2 failed on these; v3 includes all fixes |
