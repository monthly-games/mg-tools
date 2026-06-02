import os
import google.generativeai as genai

# Load Key
try:
    with open("config/gemini_key.txt", "r") as f:
        key = f.read().strip()
    genai.configure(api_key=key)
    
    print("Listing Models:")
    for m in genai.list_models():
        print(f" - {m.name} ({m.supported_generation_methods})")
        
except Exception as e:
    print(f"Error: {e}")
