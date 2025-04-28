from flask import Flask, render_template, request, jsonify
from intent_classifier import classify_intent
from importance_classifier import ImportanceClassifier
import google.generativeai as genai
import os
from dotenv import load_dotenv
from flask_cors import CORS  # For handling cross-origin requests

# Load environment variables and set up Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash-lite')

# Initialize the Flask app
app = Flask(__name__)

# Enable CORS (to allow the frontend and backend to communicate across different ports)
CORS(app)

# Memory to store messages
memory = []

# Route for rendering the web page
@app.route("/", methods=["GET", "POST"])
def index():
    user_message = None
    bot_message = None
    if request.method == "POST":
        user_message = request.form["user_input"]
        try:
            # Classify the intent and analyze the importance of the user input
            intent_info = classify_intent(user_message)
            importance_info = ImportanceClassifier.analyze_importance(user_message)

            # Store the details in memory (without exposing raw data to the user)
            memory.append({
                "user_message": user_message
            })

            # Generate the confirmation response from Gemini
            bot_message = generate_response_from_gemini(intent_info, importance_info)

            # Store bot's response to memory
            memory.append({
                "bot_message": bot_message
            })

        except Exception as e:
            print(f"Error: {e}")
            bot_message = "Sorry, something went wrong while processing your request."

    return render_template("index.html", memory=memory, user_message=user_message, bot_message=bot_message)

# Function to generate response from Gemini
def generate_response_from_gemini(intent_info, importance_info):
    # Get important details from the intent and importance classifiers
    intent = intent_info.get("intent", "Unknown")
    importance = importance_info.get("detailed_importance_level", "Unknown")
    urgency = importance_info.get("urgency", "Unknown")
    impact = importance_info.get("impact", "Unknown")
    emotional_weight = importance_info.get("emotional_weight", "Unknown")
    time_sensitivity = importance_info.get("time_sensitivity", "Unknown")

    # Create the prompt for Gemini to generate a conversational message
    prompt = f"""
    The user has made a request related to '{intent}', which is classified with the following importance:
    Importance: {importance}
    Urgency: {urgency}
    Impact: {impact}
    Emotional Weight: {emotional_weight}
    Time Sensitivity: {time_sensitivity}

    Generate a human-like response to acknowledge and confirm the request. Do not mention the technical details such as intent, urgency, or impact directly. Keep it conversational, like confirming the task has been done.
    """

    # Call Gemini API to generate the confirmation message
    response = model.generate_content(prompt)
    
    return response.text.strip()

# API route for classifying intent and importance
@app.route("/api/classify", methods=["POST"])
def classify():
    try:
        data = request.get_json()
        print("Received data:", data)

        user_input = data.get("user_input")
        if not user_input:
            raise ValueError("User input is missing")

        intent_result = classify_intent(user_input)
        importance_result = ImportanceClassifier.analyze_importance(user_input)

        # Generate conversational response
        bot_response = generate_response_from_gemini(intent_result, importance_result)

        return jsonify({
            "intent": intent_result,
            "importance": importance_result,
            "bot_response": bot_response  # <-- Added this
        })

    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 400


# Run the app
if __name__ == "__main__":
    app.run(debug=True)
