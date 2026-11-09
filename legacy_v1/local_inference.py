# Nyaya-Tuned Local Inference Engine (CLI Version)
# Command-line tool for querying the model without a web browser.

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from deep_translator import GoogleTranslator

# Configuration
LOCAL_MODEL_PATH = os.path.join("models", "Qwen2.5-3B-Instruct")
HF_MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
ADAPTER_PATH = "./Nyaya-Adapter" 

# Language Codes
LANG_MAP = {
    "en": "en", "hi": "hi", "ta": "ta", "te": "te",
    "kn": "kn", "ml": "ml", "bn": "bn", "mr": "mr",
    "gu": "gu", "pa": "pa"
}

# Path Verification
if os.path.exists(LOCAL_MODEL_PATH):
    model_source = LOCAL_MODEL_PATH
    print(f"[INFO] Using local base model: {LOCAL_MODEL_PATH}")
else:
    model_source = HF_MODEL_ID
    print(f"[WARNING] Local model not found. Using Hugging Face ID: {HF_MODEL_ID}")

if not os.path.exists(ADAPTER_PATH):
    print(f"[WARNING] Adapter path not found at {ADAPTER_PATH}. Running base model only.")
    USE_ADAPTER = False
else:
    print(f"[INFO] Adapter found at {ADAPTER_PATH}")
    USE_ADAPTER = True

print("[INFO] Loading model... (This may take a moment)")

# Quantization
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=False,
)

# Model Load
base_model = AutoModelForCausalLM.from_pretrained(
    model_source,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True
)

# Adapter Load
if USE_ADAPTER:
    try:
        model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
        print("[SUCCESS] Adapters attached.")
    except Exception as e:
        print(f"[ERROR] Adapter load failed: {e}")
        model = base_model
else:
    model = base_model

tokenizer = AutoTokenizer.from_pretrained(model_source, trust_remote_code=True)

def generate_response(query, lang_code="en"):
    # Translate Input
    english_query = query
    if lang_code != "en":
        print(f"   [Translating Input]...")
        try:
            english_query = GoogleTranslator(source='auto', target='en').translate(query)
            print(f"   [Interpreted]: {english_query}")
        except Exception as e:
            return f"Translation Error: {str(e)}"

    # Generate
    prompt = f"<|im_start|>user\n{english_query}<|im_end|>\n<|im_start|>assistant\n"
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.4,
            do_sample=True,
            repetition_penalty=1.1
        )
    
    full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Parse
    if "assistant" in full_response:
        english_response = full_response.split("assistant")[-1].strip()
    else:
        english_response = full_response

    # Translate Output
    final_response = english_response
    if lang_code != "en":
        print(f"   [Translating Output]...")
        try:
            final_response = GoogleTranslator(source='en', target=lang_code).translate(english_response)
        except Exception as e:
            final_response = f"Translation Error: {english_response}"

    return final_response

def main():
    print("\n" + "="*50)
    print("  NYAYA-TUNED TERMINAL INTERFACE")
    print("   Type 'exit' to quit.")
    print("   Language Codes: en, hi, ta, te, bn, etc.")
    print("="*50)

    current_lang = "en"

    while True:
        try:
            user_input = input(f"\n[{current_lang.upper()}] Legal Query > ").strip()
            
            # Commands
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting.")
                break
            
            if user_input.lower().startswith("lang "):
                new_lang = user_input.split(" ")[1]
                if new_lang in LANG_MAP:
                    current_lang = new_lang
                    print(f"[INFO] Language switched to {new_lang}")
                    continue
                else:
                    print(f"[ERROR] Invalid language code. Available: {list(LANG_MAP.keys())}")
                    continue

            if not user_input:
                continue

            # Processing
            print("   Thinking...")
            response = generate_response(user_input, current_lang)
            print("-" * 50)
            print(f" \033[1mOPINION:\033[0m\n{response}")
            print("-" * 50)

        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    main()
