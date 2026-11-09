# Nyaya-Tuned Local Training Engine
# Fine-tunes Qwen 2.5 3B on Indian Legal data.

import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

# Configuration
LOCAL_MODEL_PATH = os.path.join("models", "Qwen2.5-3B-Instruct")
HF_MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
OUTPUT_DIR = "Nyaya-Adapter"
DATASET_PATH = os.path.join("data", "ipc_dataset.json")

def train():
    # Dataset Verification
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}. Run pipeline script first.")

    # Model Source Logic
    if os.path.exists(LOCAL_MODEL_PATH):
        model_source = LOCAL_MODEL_PATH
        print(f"[INFO] Using local base model at: {LOCAL_MODEL_PATH}")
    else:
        model_source = HF_MODEL_ID
        print(f"[WARNING] Local model not found. Downloading from Hugging Face: {HF_MODEL_ID}")

    print(f"[INFO] Initializing training for {model_source}")

    # Quantization Setup
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=False,
    )

    # Model Initialization
    model = AutoModelForCausalLM.from_pretrained(
        model_source,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    model.config.use_cache = False

    tokenizer = AutoTokenizer.from_pretrained(model_source, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # Data Loading
    dataset = load_dataset("json", data_files=DATASET_PATH, split="train")

    # Formatting Function
    def format_prompts(examples):
        output_texts = []
        instructions = examples['instruction'] if isinstance(examples['instruction'], list) else [examples['instruction']]
        inputs = examples['input'] if isinstance(examples['input'], list) else [examples['input']]
        outputs = examples['output'] if isinstance(examples['output'], list) else [examples['output']]

        for i in range(len(instructions)):
            inst = instructions[i]
            inp = inputs[i] if i < len(inputs) else ""
            resp = outputs[i]

            context = f"\nContext: {inp}" if (inp and len(str(inp)) > 2) else ""
            text = f"<|im_start|>user\n{inst}{context}<|im_end|>\n<|im_start|>assistant\n{resp}<|im_end|>"
            output_texts.append(text)
        
        return output_texts

    # LoRA Config
    peft_config = LoraConfig(
        lora_alpha=16, 
        lora_dropout=0.05, 
        r=16, 
        bias="none", 
        task_type="CAUSAL_LM",
        target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj']
    )

    # Training Configuration
    training_args = SFTConfig(
        output_dir="./checkpoints",
        num_train_epochs=1,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        optim="paged_adamw_32bit",
        save_steps=100,
        logging_steps=25,
        learning_rate=2e-4,
        weight_decay=0.001,
        fp16=False,
        bf16=False,
        max_grad_norm=0.3,
        max_steps=-1,
        warmup_ratio=0.03,
        group_by_length=True,
        lr_scheduler_type="cosine",
        report_to="none",
        dataset_text_field="text",
        max_seq_length=512,
        packing=False
    )

    # Trainer Initialization
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        peft_config=peft_config,
        formatting_func=format_prompts,
        processing_class=tokenizer,
        args=training_args
    )

    print("[INFO] Starting fine-tuning...")
    trainer.train()

    print(f"[INFO] Saving model to {OUTPUT_DIR}...")
    trainer.model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("[SUCCESS] Training complete.")

if __name__ == "__main__":
    train()