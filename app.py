# Nyaya-Tuned Dynamic Web App (Local Edition)
# Features: Glassmorphism UI, Multilingual Wrapper, Auto-Model Switching, Stop Server

import os
import torch
import gradio as gr
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from deep_translator import GoogleTranslator

# Configuration
LOCAL_MODEL_PATH = os.path.join("models", "Qwen2.5-3B-Instruct")
HF_MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER_DIR = "Nyaya-Adapter" 

# CSS Styling
CUSTOM_CSS = """
.gradio-container {
    background: linear-gradient(135deg, #1a1c2c 0%, #4a192c 100%);
}
h1 {
    color: #ffffff; 
    font-family: 'Helvetica Neue', sans-serif;
    text-align: center;
    font-size: 2.5rem;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
}
.subtitle {
    text-align: center;
    color: #e0e0e0;
    margin-bottom: 20px;
}
.input-box textarea {
    background-color: #2b2d42 !important;
    color: white !important;
    border: 1px solid #555 !important;
}
.output-box textarea {
    background-color: #1a1a1a !important;
    color: #00ff9d !important; 
    font-family: 'Consolas', monospace;
}
button.primary {
    background: linear-gradient(90deg, #ff4b1f 0%, #ff9068 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: bold;
    transition: transform 0.2s;
}
button.primary:hover {
    transform: scale(1.05);
}
button.stop {
    background-color: #ef4444 !important;
    color: white !important;
    font-weight: bold;
}
"""

# Model Initialization
print("[INFO] Initializing Nyaya-Tuned Engine...")

if os.path.exists(LOCAL_MODEL_PATH):
    model_source = LOCAL_MODEL_PATH
    print(f"[INFO] Using local base model: {LOCAL_MODEL_PATH}")
else:
    model_source = HF_MODEL_ID
    print(f"[WARNING] Local model not found. Using Hugging Face ID: {HF_MODEL_ID}")

# Quantization Loading
bnb_config = None
try:
    print("[INFO] Attempting to enable 4-bit quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False,
    )
except Exception as e:
    print(f"[WARNING] 4-bit quantization failed (likely bitsandbytes compatibility issue): {e}")
    print("[INFO] Falling back to standard float16 loading. This may use more RAM.")

print(f"[INFO] Loading Base Model...")

# Load model with or without quantization based on success above
if bnb_config:
    base_model = AutoModelForCausalLM.from_pretrained(
        model_source,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
else:
    # Fallback for systems where bitsandbytes fails
    base_model = AutoModelForCausalLM.from_pretrained(
        model_source,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )

if os.path.exists(ADAPTER_DIR):
    print(f"[SUCCESS] Found Adapters at {ADAPTER_DIR}. Attaching...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
else:
    print(f"[WARNING] Adapters not found at {ADAPTER_DIR}. Running in Base Model Mode.")
    model = base_model

tokenizer = AutoTokenizer.from_pretrained(model_source, trust_remote_code=True)

# Translation Logic
LANG_MAP = {
    "English": "en", "Hindi": "hi", "Tamil": "ta", "Telugu": "te",
    "Kannada": "kn", "Bengali": "bn", "Marathi": "mr", "Gujarati": "gu"
}

def predict(query, lang_name):
    lang_code = LANG_MAP.get(lang_name, "en")
    
    # Input Translation
    eng_query = query
    trans_info = ""
    if lang_code != "en":
        try:
            eng_query = GoogleTranslator(source='auto', target='en').translate(query)
            trans_info = f"\n\n[Translated Input]: {eng_query}"
        except:
            pass

    # Inference Generation
    prompt = f"<|im_start|>user\n{eng_query}<|im_end|>\n<|im_start|>assistant\n"
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.4,
            do_sample=True,
            repetition_penalty=1.1
        )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    if "assistant" in response:
        response = response.split("assistant")[-1].strip()

    # Output Translation
    final_output = response
    if lang_code != "en":
        try:
            final_output = GoogleTranslator(source='en', target=lang_code).translate(response)
        except:
            final_output = response + " (Translation Failed)"

    return final_output + trans_info

# UI Construction
with gr.Blocks(css=CUSTOM_CSS, title="Nyaya-Tuned AI") as app:
    gr.Markdown("<h1>Nyaya-Tuned</h1>")
    gr.Markdown("<div class='subtitle'>Advanced Indian Legal Intelligence System</div>")
    
    with gr.Row():
        with gr.Column(scale=1):
            lang_dropdown = gr.Dropdown(choices=list(LANG_MAP.keys()), value="English", label="Select Language")
            query_input = gr.Textbox(lines=5, placeholder="Enter legal scenario or IPC section...", label="Legal Query", elem_classes="input-box")
            
            with gr.Row():
                submit_btn = gr.Button("Analyze Case", variant="primary")
                clear_btn = gr.Button("Clear")
                stop_btn = gr.Button("Stop Server", variant="stop")
                
        with gr.Column(scale=1):
            output_text = gr.Textbox(lines=15, label="Legal Opinion", elem_classes="output-box", interactive=False)
            
    gr.Markdown("---")
    gr.Markdown("*Disclaimer: This is an AI model. Always consult a qualified lawyer for legal advice.*")

    submit_btn.click(fn=predict, inputs=[query_input, lang_dropdown], outputs=output_text)
    clear_btn.click(lambda: ("", ""), outputs=[query_input, output_text])
    
    def shutdown():
        print("[INFO] Server shutdown initiated.")
        app.close()
        return "Server stopped."
        
    stop_btn.click(shutdown, inputs=None, outputs=output_text)

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", share=False)
