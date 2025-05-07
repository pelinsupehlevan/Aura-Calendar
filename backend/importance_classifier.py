import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, List, Any, Tuple

# Load environment variables
load_dotenv()

class ImportanceClassifier:
    def __init__(self):
        """Initialize the importance classifier with Gemini API"""
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        # Define importance scale
        self.importance_scale = {
            1: "Lowest importance, can be easily rescheduled or skipped",
            2: "Low importance, preferred to keep but flexible",
            3: "Medium importance, should be kept if possible",
            4: "High importance, should be kept with strong preference",
            5: "Critical importance, must be kept at all costs"
        }
    
    async def classify_importance(self, event_details: Dict, user_message: str = None) -> int:
        """
        Classify the importance of an event using Gemini
        
        Args:
            event_details: Dictionary with event details
            user_message: Optional original user message for context
        
        Returns:
            Importance score (1-5)
        """
        # Create system prompt for Gemini
        system_prompt = f"""
        You are an AI assistant that analyzes calendar events to determine their importance.
        You should classify the importance of events on a scale from 1 to 5:
        
        1: {self.importance_scale[1]}
        2: {self.importance_scale[2]}
        3: {self.importance_scale[3]}
        4: {self.importance_scale[4]}
        5: {self.importance_scale[5]}
        
        Consider these factors when determining importance:
        - Words indicating urgency/importance: "urgent", "important", "critical", "must", etc.
        - Type of event: work meetings, doctor appointments, personal celebrations, etc.
        - Time sensitivity: events that can't be easily rescheduled
        - Personal impact: how much the event might matter to the user emotionally
        
        Return only a single number representing the importance score (1-5).
        """
        
        # Build the event description
        event_description = json.dumps(event_details, default=str)
        
        # Add original user message if available
        context_message = ""
        if user_message:
            context_message = f"\nHere is the original user message: {user_message}"
        
        # Build the full prompt
        prompt = f"{system_prompt}\n\nEvent details: {event_description}{context_message}\n\nImportance score:"
        
        try:
            # Get response from Gemini
            response = await self.model.generate_content_async(prompt)
            response_text = response.text.strip()
            
            # Try to extract the importance score
            try:
                importance = int(response_text)
                # Ensure it's in the valid range
                if importance < 1:
                    importance = 1
                elif importance > 5:
                    importance = 5
                return importance
            except ValueError:
                # If the response isn't a clean integer, try to find a number in the text
                import re
                number_match = re.search(r'\b[1-5]\b', response_text)
                if number_match:
                    return int(number_match.group(0))
                else:
                    # Default to medium importance if we can't parse the response
                    return 3
                
        except Exception as e:
            print(f"Error in importance classification: {e}")
            # Default to medium importance in case of error
            return 3
    
    def get_importance_description(self, importance_score: int) -> str:
        """Get the text description for an importance score"""
        if importance_score in self.importance_scale:
            return self.importance_scale[importance_score]
        else:
            return "Unknown importance level"