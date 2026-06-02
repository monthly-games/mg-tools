import os
import json
import argparse
import google.generativeai as genai
from pathlib import Path
from PIL import Image

def analyze_character(image_path: str, api_key: str):
    genai.configure(api_key=api_key)
    
    # Use Flash for speed
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    img = Image.open(image_path)
    
    prompt = """
    Analyze this character sprite for a 2D game.
    Provide the output in JSON format only.
    
    Determine the following:
    1. "mood": One of ["neutral", "aggressive", "seductive", "cute", "scary"].
    2. "preset": Select the best animation preset from ["idle", "combat", "allure", "run", "die"].
       - If distinctive weapon or armor: "combat".
       - If charming/sexy pose: "allure".
       - If cute/small: "idle" or "run".
    3. "description": A 1-sentence description of the character.
    """
    
    try:
        response = model.generate_content([prompt, img])
        text = response.text.strip()
        # Clean markdown json blocks if present
        if text.startswith("```json"):
            text = text[7:-3]
        return json.loads(text)
    except Exception as e:
        print(f"Error analyzing character: {e}")
        return {"mood": "neutral", "preset": "idle", "description": "Analysis failed"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--key_file", default="config/gemini_key.txt")
    args = parser.parse_args()
    
    with open(args.key_file, "r") as f:
        key = f.read().strip()
        
    result = analyze_character(args.input, key)
    print(json.dumps(result, indent=2))
