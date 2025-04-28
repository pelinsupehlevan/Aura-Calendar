import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
importance_model = genai.GenerativeModel('gemini-2.0-flash-lite')

class ImportanceClassifier:
    @staticmethod
    def analyze_importance(user_input):
        prompt = f"""
        Please analyze the importance of the following user input and return a detailed breakdown. 
        Use these categories: urgency, impact, emotional weight, time sensitivity, and overall importance level (critical, high, medium, low).

        Return a response strictly formatted as:
        {{
          "urgency": "...",
          "impact": "...",
          "emotional_weight": "...",
          "time_sensitivity": "...",
          "detailed_importance_level": "... (critical/high/medium/low)"
        }}

        Input: "{user_input}"
        """

        response = importance_model.generate_content(prompt)

        # Extracting the JSON response from the model's output
        json_text = extract_json(response.text)

        try:
            response_json = json.loads(json_text)
        except json.JSONDecodeError:
            print("Importance Parsing failed, fallback to default response.")
            response_json = {
                "urgency": "Unknown",
                "impact": "Unknown",
                "emotional_weight": "Unknown",
                "time_sensitivity": "Unknown",
                "detailed_importance_level": "Unknown"
            }

        return response_json

def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group()
    return "{}"