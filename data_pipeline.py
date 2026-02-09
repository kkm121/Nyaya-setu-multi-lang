# Nyaya-Tuned Data Aggregation Pipeline
# Aggregates legal datasets into a standardized JSON format.

import pandas as pd
from datasets import load_dataset
import json
import os

# Configuration
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "ipc_dataset.json")

def build_dataset():
    print("[INFO] Initializing Nyaya-Tuned Pipeline...")
    
    # Create data directory
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"[INFO] Created directory: {DATA_DIR}")

    all_data = []

    # Source 1: General Indian Law
    print("[INFO] Downloading General Law Data...")
    try:
        ds_general = load_dataset("viber1/indian-law-dataset", split="train")
        df_general = ds_general.to_pandas()
        
        df_general = df_general.rename(columns={"Instruction": "instruction", "Response": "output"})
        df_general["input"] = "" 
        df_general = df_general[["instruction", "input", "output"]]
        
        all_data.append(df_general)
        print(f"[SUCCESS] Retrieved {len(df_general)} records.")
    except Exception as e:
        print(f"[ERROR] {e}")

    # Source 2: IPC & CrPC
    print("[INFO] Downloading IPC/CrPC Data...")
    target_files = ["ipc_qa.json", "crpc_qa.json", "constitution_qa.json"]
    
    for file_name in target_files:
        try:
            ds_sub = load_dataset("Techmaestro369/indian-legal-texts-finetuning", data_files=file_name, split="train")
            df_sub = ds_sub.to_pandas()
            
            # Sanitization
            if 'id' in df_sub.columns: df_sub = df_sub.drop(columns=['id'])
            
            df_sub = df_sub.rename(columns={"question": "instruction", "answer": "output"})
            df_sub["instruction"] = "Indian Legal Query: " + df_sub["instruction"]
            df_sub["input"] = ""
            df_sub = df_sub[["instruction", "input", "output"]]
            
            all_data.append(df_sub)
            print(f"[SUCCESS] {file_name}: {len(df_sub)} rows")
        except Exception as inner_e:
            print(f"[WARNING] Skipped {file_name}")

    # Merge & Save
    if not all_data:
        print("[CRITICAL] No data fetched.")
        return

    final_df = pd.concat(all_data, ignore_index=True)
    final_df.dropna(subset=["instruction", "output"], inplace=True)
    final_df.drop_duplicates(subset=["instruction"], inplace=True)
    final_df = final_df.sample(frac=1).reset_index(drop=True)

    # Save
    json_data = final_df.to_dict(orient="records")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"[SUCCESS] Dataset saved to: {os.path.abspath(OUTPUT_FILE)}")

if __name__ == "__main__":
    build_dataset()