# **Nyaya-Tuned: Indian Legal SLM**

Nyaya-Tuned is a specialized Small Language Model (SLM) architected for the Indian Legal System. Built upon the Qwen 2.5 3B Instruct foundation, it has been fine-tuned on over 25,000 legal Q\&A pairs covering the Indian Penal Code (IPC), Code of Criminal Procedure (CrPC), and the Constitution of India.

The model utilizes QLoRA (Quantized Low-Rank Adaptation) for efficient 4-bit inference, enabling it to run on consumer hardware with 8GB VRAM. It includes a custom inference wrapper that provides multilingual support for regional Indian languages through real-time translation layers.

## **Key Capabilities**

* **Legal Specialization:** Trained on verbatim legal texts and synthetic reasoning data specific to Indian jurisdiction.  
* **Efficient Inference:** Optimized with 4-bit quantization for low-latency performance on edge devices.  
* **Multilingual Support:** Integrated translation layer supporting Hindi, Tamil, Telugu, Bengali, Marathi, and Gujarati.  
* **Dynamic Interface:** Includes a professional web application built with Gradio for intuitive interaction.

## **Installation**

1. **Clone the repository:**  
   git clone https://github.com/kkm121/Nyaya-setu-multi-lang.git
   cd Nyaya-Tuned

2. **Install dependencies:**  
   pip install \-r requirements.txt

## **Usage Pipeline**

### **1\. Data Generation**

Fetch and normalize legal datasets from open-source repositories into a standardized format.

python data\_pipeline.py

*Artifacts will be saved to data/ipc\_dataset.json.*

### **2\. Fine-Tuning**

Train the model on a local GPU. This process utilizes QLoRA to adapt the base model to the generated legal dataset.

python train.py

*Adapters will be saved to Nyaya-Adapter/.*

### **3\. Web Application**

Launch the dynamic inference engine with the graphical user interface.

python app.py

*Access the application at http://127.0.0.1:7860.*
<img width="1147" height="486" alt="image" src="https://github.com/user-attachments/assets/e987a549-5f73-4697-952a-804b8a71c3c8" />
<img width="1161" height="487" alt="image" src="https://github.com/user-attachments/assets/58892ee1-5f43-4f18-ae23-876e5014ce01" />


## **Technical Architecture**

* **Base Model:** Qwen 2.5 3B Instruct  
* **Training Method:** QLoRA (Rank 16, Alpha 16\)  
* **Quantization:** 4-bit NF4 (Normal Float 4\)  
* **Frameworks:** PyTorch, Hugging Face Transformers, PEFT, Gradio

## **Disclaimer**

Nyaya-Tuned is an Artificial Intelligence model designed for educational and informational purposes. It is not a substitute for professional legal advice. All outputs should be verified by qualified legal practitioners.
