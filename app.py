# Nyaya Setu v2 - Web App
# Features: grounded answers with checked citations, 8 languages, document drafting,
# old -> new law finder. Runs on CPU (free Hugging Face Space) or locally.

import html
import os
import re

import gradio as gr

from nyaya.acts import OLD_TO_NEW, act_label
import tempfile

from nyaya import drafting as D
from nyaya.drafting import DOC_TYPES, RELATIONS
from nyaya.llm import load_backend
from nyaya.pipeline import NyayaPipeline
from nyaya.retrieve import Retriever
from nyaya.translate import LANGUAGES, NATIVE_NAMES, from_english, to_english
from nyaya.ui_text import examples, t

# Engine Initialization
print("[INFO] Starting Nyaya Setu...")
# match PyTorch threads (search models, translator) to the real CPU limit
import torch
from nyaya.llm import usable_cpus
torch.set_num_threads(usable_cpus())
retriever = Retriever(use_dense=True, use_rerank=os.environ.get("NYAYA_RERANK", "1") == "1")
backend = load_backend()
pipeline = NyayaPipeline(retriever, backend)
print(f"[SUCCESS] Ready. Model: {getattr(backend, 'label', backend.name)}")

LANG_CHOICES = [(f"{NATIVE_NAMES[c]} · {n}" if c != "en" else "English", c) for n, c in LANGUAGES.items()]

# CSS Styling
CUSTOM_CSS = """
:root { --ns-navy:#14213d; --ns-gold:#f4a300; --ns-muted:var(--body-text-color-subdued); }
.gradio-container { max-width: 1100px !important; margin: auto; }
#hero { background: linear-gradient(135deg, #14213d 0%, #24345c 60%, #3b2f63 100%);
        border-radius: 18px; padding: 22px 26px; color: #fff; }
#hero h1 { color:#fff; margin:0; font-size: 2rem; letter-spacing: .3px; }
#hero p { color:#dfe6f5; margin:.35rem 0 0; font-size: 1rem; }
#hero .badge { display:inline-block; background: rgba(244,163,0,.18); color:#ffd27a;
               border:1px solid rgba(244,163,0,.45); padding:2px 10px; border-radius:999px;
               font-size:.78rem; margin-right:6px; margin-top:10px; }
.answer-card { border:1px solid var(--border-color-primary); border-radius:14px; padding:18px 20px;
               background: var(--background-fill-primary); }
.answer-card:has(.prose:empty) { display:none; }
.trust { display:flex; gap:8px; flex-wrap:wrap; margin: 4px 0 10px; }
.pill { padding:4px 12px; border-radius:999px; font-size:.82rem; font-weight:600; }
.pill.ok { background:#e7f7ee; color:#11683a; }
.pill.warn { background:#fff4e0; color:#8a5300; }
.pill.info { background:#eef2fb; color:#2b3f73; }
.src { border:1px solid var(--border-color-primary); border-left:4px solid #3b5bdb; border-radius:10px;
       padding:10px 14px; margin:8px 0; background: var(--background-fill-secondary); }
.src.old { border-left-color:#f08c00; }
.src.cited { box-shadow: 0 0 0 2px rgba(59,91,219,.25); }
.src h4 { margin:0 0 4px; font-size:.95rem; color: var(--body-text-color); }
.src .tag { font-size:.72rem; font-weight:700; padding:1px 8px; border-radius:6px; background:#eef2fb;
            color:#2b3f73; margin-left:6px; }
.src .tag.old { background:#fff4e0; color:#8a5300; }
.src details summary { cursor:pointer; color:#3b5bdb; font-size:.85rem; }
.src pre { white-space:pre-wrap; font-family:inherit; font-size:.86rem; color: var(--body-text-color); margin:6px 0 0; }
.src .act { font-size:.8rem; color: var(--ns-muted); }
.status { color: var(--ns-muted); font-style: italic; }
.helpline { font-size: 2.2rem; font-weight: 800; color: var(--body-text-color); }
footer { display:none !important; }
@media (max-width: 640px) {
  #hero h1 { font-size: 1.5rem; }
  #hero { padding: 16px; }
  .answer-card { padding: 14px; }
}
"""

THEME = gr.themes.Soft(primary_hue="indigo", secondary_hue="amber", neutral_hue="slate",
                       font=[gr.themes.GoogleFont("Noto Sans"), "system-ui", "sans-serif"])


# Display Helpers
def trust_bar(r, lang):
    c = r["check"]
    pills = []
    if r["abstained"]:
        pills.append(f"<span class='pill warn'>⚠️ {html.escape(t('not_sure', lang))}</span>")
    else:
        cls = "ok" if c["supported"] == c["claims"] else "warn"
        pills.append(f"<span class='pill {cls}'>✅ {c['supported']}/{c['claims']} {html.escape(t('checked', lang))}</span>")
    if c["removed"]:
        pills.append(f"<span class='pill warn'>🧹 {c['removed']} unsupported removed</span>")
    if r["period"] == "old":
        pills.append("<span class='pill info'>📅 Event before 1 July 2024 → old law</span>")
    elif r["period"] == "new":
        pills.append("<span class='pill info'>📅 Event after 1 July 2024 → new law</span>")
    pills.append(f"<span class='pill info'>⏱ {r['seconds']}s</span>")
    return "<div class='trust'>" + "".join(pills) + "</div>"


def sources_html(r, lang):
    out = [f"<h3>📚 {html.escape(t('sources_title', lang))}</h3>"]
    for i, s in enumerate(r["sources"], 1):
        old = s.get("repealed")
        cls = "src" + (" old" if old else "") + (" cited" if i in r["cited"] else "")
        tag = f"<span class='tag old'>{html.escape(t('old_law', lang))}</span>" if old else \
              f"<span class='tag'>{html.escape(s['act_label'])}</span>"
        out.append(
            f"<div class='{cls}'><h4>[S{i}] {html.escape(s['unit'])} {html.escape(s['section'])} · "
            f"{html.escape(s['title'])}{tag}</h4>"
            f"<div class='act'>{html.escape(s['act_name'])}</div>"
            f"<details><summary>Read the law text</summary><pre>{html.escape(s['text'])}</pre></details></div>")
    for n in r["notes"][:4]:
        out.append(f"<div class='src old'><h4>🔁 Old ↔ New</h4><div style='font-size:.86rem'>{html.escape(n['note'])}</div></div>")
    return "".join(out)


# Ask Logic
# On a slow CPU (like the free Space) the model takes minutes, so the first answer is built
# straight from the law text in seconds; the model explanation is one click away.
FAST_FIRST = os.environ.get("NYAYA_FAST_FIRST", "1") == "1" and backend.name != "extractive"


def ask(question, lang, fast=None):
    fast = FAST_FIRST if fast is None else fast
    status_text = {"translating": "status_translating", "searching": "status_searching",
                   "writing": "status_writing", "checking": "status_checking"}
    hide = gr.update(visible=False)
    for status, r in pipeline.run(question, lang, fast=fast):
        if status == "draft":
            # show progress only; unchecked text is never shown to the user
            words = len(r.split())
            yield (f"<p class='status'>⏳ {html.escape(t('status_writing', lang))} ({words} words)</p>",
                   "", "", hide, hide)
            continue
        if status != "done":
            yield f"<p class='status'>⏳ {html.escape(t(status_text[status], lang))}</p>", "", "", hide, hide
            continue
        if "error" in r:
            yield f"<p class='status'>⚠️ {html.escape(t(r['error'], lang))}</p>", "", "", hide, hide
            return
        english = r["translation_quality"] < 0.8 and lang != "en"
        note = f"\n\n> ℹ️ {t('translation_note', lang)}" if english else ""
        # offer the model explanation only after a fast answer that found the law
        offer = fast and FAST_FIRST and not r["abstained"]
        yield (trust_bar(r, lang), r["answer"] + note, sources_html(r, lang),
               gr.update(visible=english, value=r["answer_en"]),
               gr.update(visible=offer, value="🧠 " + t("explain_button", lang)))


def explain(question, lang):
    yield from ask(question, lang, fast=False)


# Draft Logic
FIELD_KEYS = {dt: [k for k, _, _ in spec["fields"]] for dt, spec in DOC_TYPES.items()}
EXAMPLES_PH = {"name": "Ravi Kumar", "place": "Chennai", "address": "12, Gandhi Street, Adyar, Chennai 600020",
               "phone": "98765 43210", "email": "name@example.com", "age": "34", "cheque": "004512",
               "amount": "50000", "ref": "PR/2026/114", "time": "18:30", "period": "01/04/2024 to 31/03/2025"}


def non_latin(text):
    return any(ord(ch) > 0x2FF and ch.isalpha() for ch in text)


def make_draft(doc_type, lang, translated_copy, polish, *values):
    raw = dict(zip(FIELD_KEYS[doc_type], values))
    vals, errs, warns = D.validate(doc_type, raw)
    tr = (lambda k: t(k, lang))
    if errs:
        lines = "\n".join(f"- ❌ {html.escape(x)}" for x in D.error_lines(errs, tr))
        return f"### {html.escape(t('errors_title', lang))}\n\n{lines}", "", None, ""

    notes = []
    facts = vals.get("facts") or ""
    facts_en, native = facts, None
    if facts and non_latin(facts):
        # facts typed in an Indian language: English copy gets a translation, the other copy keeps their words
        facts_en, native = to_english(facts, lang if lang != "en" else "auto"), facts
        notes.append(t("facts_translated", lang))
    if polish and facts_en:
        facts_en = D.polish_facts(facts_en, D.FORM_TEXT["d_" + doc_type], backend)

    blocks = D.build_document(doc_type, vals, facts_en)
    folder = tempfile.mkdtemp()
    files = D.save_files(blocks, D.TITLES[doc_type], folder)
    readable = ""
    if translated_copy and lang != "en":
        other = D.translate_blocks(blocks, lang, facts_native=native)
        files += D.save_files(other, f"{D.TITLES[doc_type]}_{lang}", folder)
        readable = f"> {t('doc_lang_note', lang)}\n\n" + D.to_markdown(other)

    tip = D.TIPS[doc_type]
    if lang != "en":
        tip = from_english(tip, lang)[0]
    status = "".join(f"> ⚠️ {html.escape(w if lang == 'en' else from_english(w, lang)[0])}\n\n" for w in warns)
    status += "".join(f"> ℹ️ {html.escape(n)}\n\n" for n in notes)
    status += f"> 💡 {html.escape(tip)}"
    return status, D.to_markdown(blocks), files, readable


# Old -> New Finder
def find_new(act, number):
    number = (number or "").strip().upper()
    # only a section number like 420, 498A or 35 is accepted here
    if not re.fullmatch(r"\d{1,3}[A-Z]{0,2}", number):
        return "Please enter a section number, for example 420 or 498A."
    if act not in ("IPC", "CRPC", "IEA", "BNS", "BNSS", "BSA"):
        return "Please choose a law."
    maps = retriever.mapped(act, number)
    if not maps:
        return f"No mapping found for {act_label(act)} section {number}."
    lines = [f"### {act_label(act)} Section {number}"]
    old = retriever.lookup(act, number)
    if old:
        lines.append(f"**Old title:** {retriever.chunks[old[0]]['title']}")
    for to_act, to_num, m in maps:
        if to_num:
            lines.append(f"\n➡️ **{act_label(to_act)} Section {m.get('to_sub') or to_num}** — {m['to_title']}  \n"
                         f"_{m['status']}_ · {m['note']}")
            new = retriever.lookup(to_act, to_num)
            if new:
                lines.append(f"<details><summary>Read {act_label(to_act)} {to_num}</summary>\n\n"
                             f"{retriever.chunks[new[0]]['text']}\n\n</details>")
        else:
            lines.append(f"\n❌ **{m['status']}** · {m['note']}")
    lines.append("\n> Events before 1 July 2024 are dealt with under the old law; later events under the new law.")
    return "\n".join(lines)


# Language Switch
def doc_choices(lang):
    return [(t(f"d_{k}", lang), k) for k in DOC_TYPES]


def help_html(lang):
    return f"""
    <div class='answer-card'>
      <h3>{html.escape(t('help_title', lang))}</h3>
      <div class='helpline'>📞 15100</div>
      <p>{html.escape(t('help_aid', lang))}</p>
      <p>🚨 112 · 181 · 1930 (cybercrime.gov.in)</p>
      <hr>
      <p>🔒 {html.escape(t('privacy', lang))}</p>
      <p>{html.escape(t('help_how', lang))}</p>
      <p class='status' style='font-style:normal;font-size:.85rem'>{html.escape(t('help_disclaimer', lang))}
         Law text: India Code / Gazette of India via the GSMS-B Indian Legal Knowledge Base (CC BY 4.0).</p>
    </div>"""


def switch_language(lang):
    return (hero_html(lang),
            gr.update(label=t("ask_label", lang), placeholder=t("ask_placeholder", lang)),
            gr.update(value=t("ask_button", lang)),
            gr.update(value=t("clear_button", lang)),
            gr.update(samples=[[e] for e in examples(lang)], label=t("examples_title", lang)),
            gr.update(label="💬 " + t("tab_ask", lang)),
            gr.update(label="📝 " + t("tab_draft", lang)),
            gr.update(label="🔁 " + t("tab_finder", lang)),
            gr.update(label="🆘 " + t("tab_help", lang)),
            t("draft_intro", lang),
            gr.update(choices=doc_choices(lang), label=t("doc_label", lang)),
            t("finder_intro", lang),
            gr.update(label=t("law_label", lang)),
            gr.update(label=t("section_label", lang)),
            gr.update(value=t("finder_button", lang)),
            help_html(lang))


def hero_html(lang):
    return (f"<div id='hero'><h1>⚖️ Nyaya Setu <span style='font-weight:400;font-size:1rem;opacity:.8'>न्याय सेतु</span></h1>"
            f"<p>{html.escape(t('tagline', lang))}</p>"
            "<span class='badge'>BNS · BNSS · BSA 2023</span><span class='badge'>102 Indian laws</span>"
            "<span class='badge'>Citations checked</span><span class='badge'>8 languages</span></div>")


# UI Construction
with gr.Blocks(title="Nyaya Setu · Free legal help in your language") as app:
    with gr.Row(equal_height=True):
        with gr.Column(scale=4):
            hero = gr.HTML(hero_html("en"))
        with gr.Column(scale=1, min_width=180):
            lang = gr.Dropdown(choices=LANG_CHOICES, value="en", label="🌐 Language / भाषा")

    with gr.Tabs():
        with gr.Tab("💬 " + t("tab_ask")) as tab_ask:
            question = gr.Textbox(lines=3, label=t("ask_label"), placeholder=t("ask_placeholder"), autofocus=True,
                                  max_length=1000)
            with gr.Row():
                ask_btn = gr.Button(t("ask_button"), variant="primary", scale=3)
                clear_btn = gr.Button(t("clear_button"), scale=1)
            ex = gr.Dataset(components=[question], samples=[[e] for e in examples("en")], label=t("examples_title"))
            trust = gr.HTML()
            with gr.Group(elem_classes="answer-card"):
                answer = gr.Markdown()
            explain_btn = gr.Button("🧠 " + t("explain_button"), visible=False, variant="secondary")
            answer_en = gr.Textbox(label="English answer", visible=False, lines=8, interactive=False)
            sources = gr.HTML()

        with gr.Tab("📝 " + t("tab_draft")) as tab_draft:
            draft_intro = gr.Markdown(t("draft_intro"))
            doc_type = gr.Dropdown(choices=doc_choices("en"), value="police_complaint", label=t("doc_label"))

            @gr.render(inputs=[doc_type, lang])
            def draft_form(dt, lg):
                spec = DOC_TYPES[dt]
                opts = spec.get("options", {})
                boxes = []

                def field(key, kind, req):
                    lab = t(f"f_{key}", lg).rstrip(" *") + (" *" if req else "")
                    ph = "Mohan Kumar" if key.endswith("relname") else EXAMPLES_PH.get(kind, "")
                    k = f"{dt}-{key}"
                    if kind == "date":
                        return gr.DateTime(label=lab, include_time=False, type="string", key=k)
                    if kind == "relation":
                        return gr.Dropdown(choices=[(t(f"o_{r}", lg), r) for r in RELATIONS], label=lab, key=k,
                                           value=None)
                    if kind == "select":
                        return gr.Dropdown(choices=[(t(f"o_{o}", lg), o) for o in opts[key]], label=lab, key=k,
                                           value=opts[key][0] if key in ("days", "interest", "level") else None)
                    if kind == "multi":
                        return gr.CheckboxGroup(choices=[(t(f"o_{o}", lg), o) for o in opts[key]], label=lab, key=k)
                    if kind == "text":
                        return gr.Textbox(label=lab, lines=6, max_length=4000, key=k,
                                          placeholder=t("ph_facts", lg))
                    if kind == "lines":
                        return gr.Textbox(label=lab, lines=5, max_length=3000, key=k)
                    if kind == "address":
                        return gr.Textbox(label=lab, lines=2, max_length=300, placeholder=ph, key=k)
                    return gr.Textbox(label=lab, max_length=300 if kind == "short" else 120, placeholder=ph, key=k)

                you = [f for f in spec["fields"] if f[0].startswith("s_")]
                them = [f for f in spec["fields"] if f[0].startswith(("r_", "n_", "op_", "authority", "level"))]
                rest = [f for f in spec["fields"] if f not in you and f not in them]
                with gr.Row():
                    for title, group in (("sec_you", you), ("sec_them", them)):
                        if group:
                            with gr.Column():
                                gr.Markdown(f"**{t(title, lg)}**")
                                for f in group:
                                    boxes.append((f[0], field(*f)))
                gr.Markdown(f"**{t('sec_details', lg)}**")
                with gr.Row():
                    half = (len(rest) + 1) // 2
                    for group in (rest[:half], rest[half:]):
                        with gr.Column():
                            for f in group:
                                boxes.append((f[0], field(*f)))
                ordered = [dict(boxes)[k] for k in FIELD_KEYS[dt]]
                with gr.Row():
                    copy = gr.Checkbox(value=lg != "en", visible=lg != "en", key=f"{dt}-copy",
                                       label=t("doc_lang_label", lg) + ": English + " + NATIVE_NAMES.get(lg, ""))
                    polish = gr.Checkbox(value=False, visible=backend.name != "extractive", key=f"{dt}-polish",
                                         label=t("ai_polish", lg))
                btn = gr.Button(t("draft_button", lg), variant="primary")
                status = gr.Markdown()
                preview = gr.Markdown(elem_classes="answer-card")
                files = gr.File(label=t("download_label", lg), file_count="multiple")
                readable = gr.Markdown()
                btn.click(make_draft, inputs=[doc_type, lang, copy, polish] + ordered,
                          outputs=[status, preview, files, readable])

        with gr.Tab("🔁 " + t("tab_finder")) as tab_finder:
            finder_intro = gr.Markdown(t("finder_intro"))
            with gr.Row():
                old_act = gr.Dropdown(choices=[("IPC → BNS", "IPC"), ("CrPC → BNSS", "CRPC"),
                                               ("Evidence Act → BSA", "IEA"), ("BNS → IPC", "BNS"),
                                               ("BNSS → CrPC", "BNSS"), ("BSA → Evidence Act", "BSA")],
                                      value="IPC", label=t("law_label"))
                old_num = gr.Textbox(label=t("section_label"), placeholder="420 / 498A", max_length=6)
                find_btn = gr.Button(t("finder_button"), variant="primary")
            mapping_out = gr.Markdown()

        with gr.Tab("🆘 " + t("tab_help")) as tab_help:
            help_box = gr.HTML(help_html("en"))

    # Events
    ask_btn.click(ask, inputs=[question, lang], outputs=[trust, answer, sources, answer_en, explain_btn])
    question.submit(ask, inputs=[question, lang], outputs=[trust, answer, sources, answer_en, explain_btn])
    clear_btn.click(lambda: ("", "", "", "", gr.update(visible=False), gr.update(visible=False)),
                    outputs=[question, trust, answer, sources, answer_en, explain_btn])
    explain_btn.click(explain, inputs=[question, lang], outputs=[trust, answer, sources, answer_en, explain_btn])
    # fill the box, then ask (chained, so the answer always uses the example text)
    ex.click(lambda x: x[0], inputs=[ex], outputs=[question]).then(
        ask, inputs=[question, lang], outputs=[trust, answer, sources, answer_en, explain_btn])
    lang.change(switch_language, inputs=[lang],
                outputs=[hero, question, ask_btn, clear_btn, ex, tab_ask, tab_draft, tab_finder, tab_help,
                         draft_intro, doc_type, finder_intro, old_act, old_num, find_btn, help_box])
    find_btn.click(find_new, inputs=[old_act, old_num], outputs=[mapping_out])
    old_num.submit(find_new, inputs=[old_act, old_num], outputs=[mapping_out])

if __name__ == "__main__":
    app.queue(default_concurrency_limit=2).launch(theme=THEME, css=CUSTOM_CSS,
                                                  server_name=os.environ.get("HOST", "127.0.0.1"))
