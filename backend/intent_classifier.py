import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, List, Any, Tuple
import datetime
import re

# Load environment variables
load_dotenv()

class IntentClassifier:
    def __init__(self):
        """Initialize the intent classifier with Gemini API"""
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Define the intents we want to recognize
        self.intent_types = [
            "CREATE_EVENT",           # Create a new calendar event
            "UPDATE_EVENT",           # Update an existing event
            "DELETE_EVENT",           # Delete/cancel an event
            "QUERY_EVENT",            # Ask about existing events
            "CHECK_AVAILABILITY",     # Check if a time slot is available
            "RESCHEDULE_EVENT",       # Move an event to a different time
            "GENERAL_CONVERSATION",   # General conversation, not related to calendar
        ]
    
    async def classify_intent(self, user_message: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Classify the user's intent using Gemini
        
        Args:
            user_message: The user's message to analyze
            conversation_history: Optional list of previous conversation turns
        
        Returns:
            Dictionary containing intent classification and extracted event details
        """
        # Create system prompt for Gemini
        system_prompt = f"""
        You are an AI assistant that analyzes user messages to determine intent related to calendar events.
        You should classify the intent and extract any relevant event details.
        
        Available intents are: {', '.join(self.intent_types)}
        
        For calendar-related intents, extract these details when present:
        - title: The name/title of the event
        - description: Description of what the event is about
        - start_time: When the event starts (date and time)
        - end_time: When the event ends (date and time)
        - duration: The time that event consumes (default : 60 minutes)
        - location: Where the event takes place (if mentioned)
        - event_id: If the user is referring to a specific existing event (if mentioned)
        
        Return your analysis as a JSON object with these fields:
        - intent: One of the predefined intent types
        - confidence: How confident you are in this classification (0.0-1.0)
        - event_details: Object containing any event details you extracted
        - needs_clarification: Boolean indicating if you need more information
        - clarification_question: Question to ask the user if clarification is needed
        
        Current date: {datetime.datetime.now().strftime('%Y-%m-%d')}
        """
        
        # Create the conversation history context
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            context_messages = []
            for turn in conversation_history[-5:]:  # Just use the last 5 turns for context
                context_messages.append(f"User: {turn['user_message']}")
                context_messages.append(f"Assistant: {turn['bot_response']}")
            conversation_context = "Recent conversation history:\n" + "\n".join(context_messages) + "\n\n"
        
        # Build the full prompt
        prompt = f"{system_prompt}\n\n{conversation_context}User message: {user_message}\n\nAnalysis:"
        
        try:
            # Get response from Gemini
            response = await self.model.generate_content_async(prompt)
            response_text = response.text
            
            # Try to extract JSON from the response
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no code block, try to find JSON directly
                json_str = response_text
            
            # Clean up any extra text and parse JSON
            result = json.loads(json_str)
            
            # Validate intent type
            if result['intent'] not in self.intent_types:
                result['intent'] = 'GENERAL_CONVERSATION'
            
            # Process date and time strings into datetime objects if present
            if 'event_details' in result and result['event_details']:
                event_details = result['event_details']
                
                # Process start_time if present
                if 'start_time' in event_details and event_details['start_time']:
                    try:
                        # First try parsing in standard ISO format
                        event_details['start_time'] = datetime.datetime.fromisoformat(
                            event_details['start_time'].replace('Z', '+00:00')
                        )
                    except (ValueError, TypeError):
                        try:
                            # Try parsing in natural language
                            event_details['start_time'] = self._parse_datetime(event_details['start_time'])
                        except:
                            # Keep as string if parsing fails
                            pass
                
                # Process end_time if present
                if 'end_time' in event_details and event_details['end_time']:
                    try:
                        # First try parsing in standard ISO format
                        event_details['end_time'] = datetime.datetime.fromisoformat(
                            event_details['end_time'].replace('Z', '+00:00')
                        )
                    except (ValueError, TypeError):
                        try:
                            # Try parsing in natural language
                            event_details['end_time'] = self._parse_datetime(event_details['end_time'])
                        except:
                            # Keep as string if parsing fails
                            pass
                
                # If we have a start_time but no end_time, default to 1 hour later
                if ('start_time' in event_details and 
                    isinstance(event_details['start_time'], datetime.datetime) and
                    ('end_time' not in event_details or not event_details['end_time'])):
                    event_details['end_time'] = event_details['start_time'] + datetime.timedelta(hours=1)
                    
                result['event_details'] = event_details
            
            return result
        
        except Exception as e:
            print(f"Error in intent classification: {e}")
            # Return a default response in case of error
            return {
                "intent": "GENERAL_CONVERSATION",
                "confidence": 0.5,
                "event_details": {},
                "needs_clarification": False,
                "clarification_question": ""
            }
    
    def _parse_datetime(self, datetime_str: str) -> datetime.datetime:
        """
        Parse a natural language datetime string to a datetime object
        
        This is a simplified version - in a production system, you might use a more
        robust solution like dateparser or write more comprehensive parsing logic
        """
        now = datetime.datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Handle simple relative dates
        datetime_str = datetime_str.lower().strip()
        
        if "today" in datetime_str:
            base_date = today
        elif "tomorrow" in datetime_str:
            base_date = today + datetime.timedelta(days=1)
        elif "next monday" in datetime_str:
            days_ahead = 7 - today.weekday()
            base_date = today + datetime.timedelta(days=days_ahead)
        # Add more relative date handling as needed
        
        else:
            # This is very simplified - you would need more robust parsing here
            # For now, return the current datetime as a fallback
            return now
        
        # Try to extract time
        time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', datetime_str, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            am_pm = time_match.group(3)
            
            # Handle AM/PM
            if am_pm and am_pm.lower() == 'pm' and hour < 12:
                hour += 12
            elif am_pm and am_pm.lower() == 'am' and hour == 12:
                hour = 0
                
            return base_date.replace(hour=hour, minute=minute)
        
        # Default to 9am if no time specified
        return base_date.replace(hour=9, minute=0)