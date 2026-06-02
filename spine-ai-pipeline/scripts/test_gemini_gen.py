import google.generativeai as genai
import PIL.Image
from pathlib import Path

try:
    with open("config/gemini_key.txt", "r") as f:
        key = f.read().strip()
    genai.configure(api_key=key)
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    print("Attempting to generate image...")
    response = model.generate_content("Generate a pixel art image of a sword.", generation_config={"response_mime_type": "image/jpeg"})
    
    # Check if response contains image data
    # Gemini API usually returns inline data or uri?
    # Standard Gemini 1.5 doesn't generate images.
    
    print(f"Response: {response.text[:100]}")
    if response.parts:
         print(f"Parts: {len(response.parts)}")
         
except Exception as e:
    print(f"Error: {e}")
