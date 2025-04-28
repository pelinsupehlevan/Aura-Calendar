import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash-lite')

def classify_intent(user_input):
    prompt = f"""
    Analyze the following user input and return ONLY this format strictly:

    {{
      "intent": "describe the user's intent in a few words",
      "importance": "high, medium, or low"
    }}

    Input: "{user_input}"
    """

    response = model.generate_content(prompt)

    # Try to extract the JSON part even if Gemini adds extra text
    json_text = extract_json(response.text)

    try:
        response_json = json.loads(json_text)
    except json.JSONDecodeError:
        print("Intent Parsing failed, fallback to unknown.")
        response_json = {"intent": "Unknown", "importance": "Unknown"}

    return response_json

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group()
    return "{}"