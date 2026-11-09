# Interface Text
# English is written by hand in plain words that translate well (no idioms like "checked against").
# Hindi is reviewed by hand (REVIEWED below). Other languages are machine translated once by
# scripts/build_ui_text.py and saved to ui_text.json; hand-reviewed text always wins.

import json
import os

UI_PATH = os.path.join(os.path.dirname(__file__), "ui_text.json")

EN = {
    "tagline": "Free legal help for everyone, in your language. Every answer shows the exact law it comes from.",
    "ask_label": "Your question",
    "ask_placeholder": "Describe your problem in simple words. For example: My landlord is not returning my deposit.",
    "ask_button": "Get answer",
    "clear_button": "Erase",
    "examples_title": "Example questions",
    "sources_title": "This answer is based on these laws",
    "checked": "statements match the law text",
    "not_sure": "Not sure. Showing related laws only.",
    "translation_note": "This translation may not be perfect. The English answer is shown below.",
    "status_translating": "Translating now...",
    "status_searching": "Searching 102 Indian laws now...",
    "status_writing": "The answer is being written now...",
    "status_checking": "Each statement is being matched with the law text now...",
    "old_law": "Old law. It applies to events before 1 July 2024.",
    "draft_intro": "Choose a document and fill in your details. Fields marked * are required. Everything is checked before the document is made, and nothing is made up.",
    "draft_button": "Create document",
    "facts_label": "What happened? Write in your own words.",
    "relief_label": "What do you want?",
    "read_in_language": "Read it in your language. This copy is only for understanding. Submit the English copy.",
    "finder_intro": "Do you have an old IPC, CrPC or Evidence Act section number? Find the matching section in the new law.",
    "finder_button": "Find the new section",
    "help_title": "Do you need a lawyer? Free legal aid is available.",
    "privacy": "Your questions are not stored. Do not type passwords, bank numbers or Aadhaar numbers.",
    "ask_empty": "Please type your question.",
    "ask_unclear": "Please describe your legal problem in a few clear words. For example: My landlord is not returning my deposit.",
    "tab_ask": "Ask",
    "tab_draft": "Draft a document",
    "tab_finder": "Old to new law",
    "tab_help": "Help",
    "doc_label": "Document",
    "law_label": "Law",
    "section_label": "Section number",
    "download_label": "Download",
    "explain_button": "Explain in simple words. The AI writes it, and it can take a few minutes.",
    "help_aid": ("Call the NALSA free legal aid helpline. You can also visit the District Legal Services Authority "
                 "at your district court. Women, children, SC and ST members, people in custody, workers and people "
                 "with low income can get a free lawyer."),
    "help_how": ("How Nyaya Setu answers: it searches the text of 102 Indian laws. It writes an answer only from the "
                 "sections it finds. Then it matches each statement with those sections. If the law does not support "
                 "an answer, it says so. It does not guess."),
    "help_disclaimer": "This is legal information. It is not legal advice.",
    # form fields
    # document names
}

EXAMPLES = [
    "The police refused to file my FIR. What can I do?",
    "The cheque my friend gave me bounced. What should I do?",
    "I bought a phone that stopped working in a week and the shop refuses to replace it.",
    "My husband beats me. How do I get a protection order?",
    "Someone took money from me promising a job and disappeared.",
    "What is IPC 420 called under the new law?",
]

# The same examples in plain words, used only as the source for machine translation
# (idioms like "bounced" came out as "booted", "destroyed" or "lost" in some languages)
EXAMPLES_FOR_TRANSLATION = [
    "The police refused to register my FIR. What can I do?",
    "My friend gave me a cheque. The bank returned the cheque unpaid. What should I do?",
    "I bought a phone. It stopped working in one week. The shop refuses to replace it.",
    "My husband beats me. How do I get a protection order?",
    "A person took money from me. He promised me a job. Then he disappeared.",
    "What is IPC 420 called under the new law?",
]

# Hand-reviewed translations (take priority over machine translation)
REVIEWED = {
    "hi": {
        "text": {
            "tagline": "सबके लिए मुफ़्त कानूनी मदद, आपकी अपनी भाषा में। हर उत्तर दिखाता है कि वह किस कानून पर आधारित है।",
            "ask_label": "आपका सवाल",
            "ask_placeholder": "अपनी समस्या आसान शब्दों में लिखें। उदाहरण: मेरा मकान मालिक मेरी जमा राशि वापस नहीं कर रहा है।",
            "ask_button": "जवाब पाएँ",
            "clear_button": "मिटाएँ",
            "examples_title": "उदाहरण सवाल",
            "sources_title": "यह उत्तर इन कानूनों पर आधारित है",
            "checked": "कथन कानून के पाठ से मेल खाते हैं",
            "not_sure": "पक्का नहीं है। केवल संबंधित कानून दिखाए जा रहे हैं।",
            "translation_note": "यह अनुवाद पूरी तरह सही न हो, ऐसा संभव है। अंग्रेज़ी उत्तर नीचे दिया गया है।",
            "status_translating": "अनुवाद हो रहा है...",
            "status_searching": "102 भारतीय कानूनों में खोज हो रही है...",
            "status_writing": "उत्तर लिखा जा रहा है...",
            "status_checking": "हर कथन का कानून के पाठ से मिलान किया जा रहा है...",
            "old_law": "पुराना कानून। यह 1 जुलाई 2024 से पहले की घटनाओं पर लागू होता है।",
            "draft_intro": "दस्तावेज़ चुनें और अपनी जानकारी भरें। * वाले खाने भरना ज़रूरी है। दस्तावेज़ बनने से पहले हर जानकारी जाँची जाती है, और कुछ भी मनगढ़ंत नहीं लिखा जाता।",
            "draft_button": "दस्तावेज़ बनाएँ",
            "facts_label": "क्या हुआ? अपने शब्दों में लिखें।",
            "relief_label": "आप क्या चाहते हैं?",
            "read_in_language": "इसे अपनी भाषा में पढ़ें। यह प्रति केवल समझने के लिए है। जमा अंग्रेज़ी प्रति करें।",
            "finder_intro": "क्या आपके पास IPC, CrPC या साक्ष्य अधिनियम की पुरानी धारा संख्या है? नए कानून में उसकी मिलती-जुलती धारा खोजें।",
            "finder_button": "नई धारा खोजें",
            "help_title": "क्या आपको वकील चाहिए? मुफ़्त कानूनी सहायता उपलब्ध है।",
            "privacy": "आपके सवाल सहेजे नहीं जाते। पासवर्ड, बैंक नंबर या आधार नंबर न लिखें।",
            "ask_empty": "कृपया अपना सवाल लिखें।",
            "ask_unclear": "कृपया अपनी कानूनी समस्या कुछ साफ़ शब्दों में बताएँ। उदाहरण: मेरा मकान मालिक मेरी जमा राशि वापस नहीं कर रहा है।",
            "tab_ask": "सवाल पूछें",
            "tab_draft": "दस्तावेज़ बनाएँ",
            "tab_finder": "पुराना से नया कानून",
            "tab_help": "मदद",
            "doc_label": "दस्तावेज़",
            "law_label": "कानून",
            "section_label": "धारा संख्या",
            "download_label": "डाउनलोड",
            "explain_button": "आसान शब्दों में समझाएँ। इसे AI लिखेगा, इसमें कुछ मिनट लग सकते हैं।",
            "help_aid": ("NALSA की मुफ़्त कानूनी सहायता हेल्पलाइन पर कॉल करें। आप अपने ज़िला न्यायालय में ज़िला विधिक सेवा "
                         "प्राधिकरण (DLSA) भी जा सकते हैं। महिलाएँ, बच्चे, SC और ST समुदाय के लोग, हिरासत में लोग, मज़दूर "
                         "और कम आय वाले लोग मुफ़्त वकील पा सकते हैं।"),
            "help_how": ("न्याय सेतु कैसे जवाब देता है: यह 102 भारतीय कानूनों के पाठ में खोज करता है। यह केवल मिली हुई "
                         "धाराओं से उत्तर लिखता है। फिर हर कथन का उन धाराओं से मिलान करता है। अगर कानून से उत्तर का "
                         "समर्थन नहीं होता, तो यह साफ़ बता देता है। यह अनुमान नहीं लगाता।"),
            "help_disclaimer": "यह कानूनी जानकारी है। यह कानूनी सलाह नहीं है।",
        },
        "examples": [
            "पुलिस ने मेरी FIR दर्ज करने से मना कर दिया। मैं क्या कर सकता/सकती हूँ?",
            "मेरे दोस्त ने जो चेक दिया था, वह बाउंस हो गया। मुझे क्या करना चाहिए?",
            "मैंने एक फ़ोन खरीदा जो एक हफ़्ते में खराब हो गया, और दुकान उसे बदलने से मना कर रही है।",
            "मेरे पति मुझे मारते हैं। मुझे सुरक्षा आदेश (protection order) कैसे मिलेगा?",
            "किसी ने नौकरी दिलाने का वादा करके मुझसे पैसे लिए और गायब हो गया।",
            "नए कानून में IPC 420 को क्या कहा जाता है?",
        ],
    },
}

# Form labels, options and messages come from the drafting module (one place for all of them)
from .drafting import FORM_TEXT  # noqa: E402
from .form_text_hi import FORM_HI  # noqa: E402

EN.update(FORM_TEXT)
REVIEWED["hi"]["text"].update(FORM_HI)

_cache = None


def load():
    global _cache
    if _cache is None:
        _cache = {}
        if os.path.exists(UI_PATH):
            with open(UI_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
    return _cache


def t(key, lang="en"):
    if lang == "en":
        return EN[key]
    if key in REVIEWED.get(lang, {}).get("text", {}):
        return REVIEWED[lang]["text"][key]
    return load().get(lang, {}).get("text", {}).get(key, EN[key])


def examples(lang="en"):
    if lang == "en":
        return EXAMPLES
    if lang in REVIEWED:
        return REVIEWED[lang]["examples"]
    return load().get(lang, {}).get("examples", EXAMPLES)
