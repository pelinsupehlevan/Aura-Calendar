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
        self.model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        # Define the intents we want to recognize
        self.intent_types = [
            "CREATE_EVENT",           # Create a new calendar event
            "CREATE_RECURRING_EVENT", # Create recurring events
            "UPDATE_EVENT",           # Update an existing event
            "DELETE_EVENT",           # Delete/cancel an event
            "QUERY_EVENT",            # Ask about existing events
            "CHECK_AVAILABILITY",     # Check if a time slot is available
            "GENERAL_CONVERSATION",   # General conversation, not related to calendar
        ]
    
    async def classify_intent(self, user_message: str, conversation_history: List[Dict] = None) -> Dict:
        """Classify the user's intent using Gemini - IMPROVED VERSION"""
        # Create system prompt for Gemini
        system_prompt = f"""
        You are an AI assistant that analyzes user messages to determine intent related to calendar events.
        You should classify the intent and extract any relevant event details.
        
        Available intents are: {', '.join(self.intent_types)}
        
        IMPORTANT: Pay special attention to deletion requests and follow-up messages.
        
        DELETION PATTERNS to recognize:
        - "delete", "remove", "cancel"
        - "delete all", "remove all"
        - "delete event", "cancel meeting", "remove appointment"
        - "delete tomorrow's events"
        
        For calendar-related intents, extract these details when present:
        - title: The name/title of the event
        - description: Description of what the event is about
        - start_time: When the event starts (date and time)
        - end_time: When the event ends (date and time)
        - duration: The time that event consumes (default: 60 minutes)
        - location: Where the event takes place (if mentioned)
        - event_id: If the user is referring to a specific existing event (if mentioned)
        - recurrence: Information about recurring events
        
        For CREATE_RECURRING_EVENT intent, also extract:
        - recurrence_type: "daily", "weekly", "monthly", or "yearly"
        - recurrence_count: Number of occurrences (e.g., "7 days", "2 weeks")
        - recurrence_end_date: When the recurring events should stop
        - recurrence_days: For weekly events, which days (e.g., ["monday", "wednesday", "friday"])
        
        For DELETE_EVENT intent, be especially careful to extract:
        - event_id: If mentioned explicitly (like "delete event 5" or "cancel meeting 3")
        - title: If they mention deleting by name (like "delete the basketball game" or "cancel my dentist appointment")
        - time_reference: If they mention time (like "delete the 9 o'clock one", "delete tomorrow's events")
        - bulk_deletion: Boolean indicating if they want to delete multiple events
        
        CONTEXT AWARENESS:
        - Look for patterns where the user is continuing a previous conversation about scheduling
        - If the user mentions a time without explicit "create" or "add" keywords, but the context suggests event creation, still classify appropriately
        - If the user mentions "move", "update" or "reschedule" keywords classify the intent as UPDATE_EVENT

        IMPORTANT: Detect recurring event patterns like:
        - "every day for a week"
        - "daily at 10am for 7 days"
        - "gym session every day at 10am for a week"
        - "meeting every Monday for 4 weeks"
        - "workout every weekday"
        
        Return your analysis as a JSON object with these fields:
        - intent: One of the predefined intent types
        - confidence: How confident you are in this classification (0.0-1.0)
        - event_details: Object containing any event details you extracted
        - needs_clarification: Boolean indicating if you need more information
        - clarification_question: Question to ask the user if clarification is needed
        - context_dependent: Boolean indicating if this classification depends on conversation context
        
        Current date: {datetime.datetime.now().strftime('%Y-%m-%d')}
        Current time: {datetime.datetime.now().strftime('%H:%M')}
        
        Examples of DELETE_EVENT patterns:
        - "delete the basketball game"
        - "cancel my meeting with John"
        - "remove the event on Friday"
        - "delete event 5"
        
        Examples of recurring event patterns:
        - "Schedule gym every day at 10am for a week" -> CREATE_RECURRING_EVENT
        - "Add workout session daily at 6pm for 7 days" -> CREATE_RECURRING_EVENT
        - "Meeting every Monday at 2pm for 4 weeks" -> CREATE_RECURRING_EVENT
        - "Book dentist appointment tomorrow at 3pm" -> CREATE_EVENT
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
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    # Fallback: assume the entire response is JSON
                    json_str = response_text
            
            # Clean up any extra text and parse JSON
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                # If JSON parsing fails, try fallback classification
                print(f"Failed to parse JSON from response: {response_text}")
                return self._fallback_classification(user_message, conversation_history)
            
            # Validate intent type
            if result.get('intent') not in self.intent_types:
                result['intent'] = 'GENERAL_CONVERSATION'
            
            # Process date and time strings into datetime objects if present
            if 'event_details' in result and result['event_details']:
                event_details = result['event_details']
                
                # Process start_time if present
                if 'start_time' in event_details and event_details['start_time']:
                    try:
                        event_details['start_time'] = self._parse_datetime(event_details['start_time'])
                    except:
                        # Keep as string if parsing fails
                        pass
                
                # Process end_time if present
                if 'end_time' in event_details and event_details['end_time']:
                    try:
                        event_details['end_time'] = self._parse_datetime(event_details['end_time'])
                    except:
                        # Keep as string if parsing fails
                        pass
                
                # Process recurrence_end_date if present
                if 'recurrence_end_date' in event_details and event_details['recurrence_end_date']:
                    try:
                        event_details['recurrence_end_date'] = self._parse_datetime(event_details['recurrence_end_date'])
                    except:
                        # Keep as string if parsing fails
                        pass
                
                # For DELETE_EVENT, also try to parse event_id
                if result['intent'] == "DELETE_EVENT" and 'event_id' in event_details:
                    try:
                        # Try to convert to integer if it's a string
                        if isinstance(event_details['event_id'], str):
                            event_details['event_id'] = int(event_details['event_id'])
                    except ValueError:
                        # If it can't be converted to int, keep as string (might be title)
                        pass

                if result['intent'] == "UPDATE_EVENT" and 'event_id' in event_details:
                    try:
                        if isinstance(event_details['event_id'], str):
                            event_details['event_id'] = int(event_details['event_id'])
                    except ValueError:
                        # If it can't be converted to int, keep as string (might be title)
                        pass    
                
                # If we have a start_time but no end_time, default to 1 hour later
                if ('start_time' in event_details and 
                    isinstance(event_details['start_time'], datetime.datetime) and
                    ('end_time' not in event_details or not event_details['end_time'])):
                    
                    # Check if duration is specified
                    duration_minutes = 60  # default
                    if 'duration' in event_details:
                        try:
                            duration_minutes = int(event_details['duration'])
                        except:
                            pass
                    
                    event_details['end_time'] = event_details['start_time'] + datetime.timedelta(minutes=duration_minutes)
                    
                result['event_details'] = event_details
            
            return result
        
        except Exception as e:
            print(f"Error in intent classification: {e}")
            # Return a fallback classification
            return self._fallback_classification(user_message, conversation_history)
    
    def _fallback_classification(self, user_message: str, conversation_history: List[Dict] = None) -> Dict:
        """Fallback classification when AI fails"""
        user_msg_lower = user_message.lower().strip()
        
        # Simple rule-based fallback
        if any(word in user_msg_lower for word in ['delete', 'remove', 'cancel']):
            return {
                "intent": "DELETE_EVENT",
                "confidence": 0.7,
                "event_details": {"title": user_message},
                "needs_clarification": True,
                "clarification_question": "Which event would you like to delete?",
                "context_dependent": False
            }
        elif any(word in user_msg_lower for word in ['create', 'add', 'schedule', 'book', 'plan']):
            return {
                "intent": "CREATE_EVENT",
                "confidence": 0.7,
                "event_details": {},
                "needs_clarification": True,
                "clarification_question": "What event would you like to create?",
                "context_dependent": False
            }
        elif any(word in user_msg_lower for word in ['move', 'update', 'reschedule']):
            return {
                "intent": "UPDATE_EVENT",
                "confidence": 0.7,
                "event_details": {},
                "needs_clarification": False,
                "clarification_question": "",
                "context_dependent": False
            }
        else:
            return {
                "intent": "GENERAL_CONVERSATION",
                "confidence": 0.5,
                "event_details": {},
                "needs_clarification": False,
                "clarification_question": "",
                "context_dependent": False
            }
        
    
    def _parse_datetime(self, datetime_str: str) -> datetime.datetime:
        """Parse a natural language datetime string to a datetime object - IMPROVED VERSION"""
        now = datetime.datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Handle simple relative dates
        datetime_str = datetime_str.lower().strip()
        
        # First check if this is already a valid ISO format
        try:
            # Try parsing as ISO format
            return datetime.datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except ValueError:
            pass
        
        # Check for "next week" explicitly
        if "next week" in datetime_str:
            # Start of next week (next Monday)
            today_weekday = today.weekday()  # 0 is Monday, 6 is Sunday
            days_until_next_monday = 7 - today_weekday if today_weekday > 0 else 7
            next_monday = today + datetime.timedelta(days=days_until_next_monday)
            return next_monday
        
        # Check for specific date (like "10th May")
        date_pattern = r'(\d{1,2})(st|nd|rd|th)?\s+(of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)'
        date_match = re.search(date_pattern, datetime_str, re.IGNORECASE)
        if date_match:
            day = int(date_match.group(1))
            month_name = date_match.group(4).lower()
            months = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            month = months[month_name]
            year = now.year
            
            # Set the date to the specified day
            try:
                date = datetime.datetime(year, month, day)
                # If the date is in the past, assume next year
                if date < now and (month < now.month or (month == now.month and day < now.day)):
                    date = datetime.datetime(year + 1, month, day)
                    
                # For specific date queries with no time, set to midnight
                return date.replace(hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                # Invalid date (e.g., February 31)
                pass
        
        # Parse relative dates
        if any(word in datetime_str for word in ["today"]):
            base_date = today
        elif any(word in datetime_str for word in ["tomorrow"]):
            base_date = today + datetime.timedelta(days=1)
        elif any(word in datetime_str for word in ["yesterday"]):
            base_date = today - datetime.timedelta(days=1)
        elif "monday" in datetime_str:
            days_ahead = 0 - today.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            base_date = today + datetime.timedelta(days=days_ahead)
        elif "tuesday" in datetime_str:
            days_ahead = 1 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = today + datetime.timedelta(days=days_ahead)
        elif "wednesday" in datetime_str:
            days_ahead = 2 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = today + datetime.timedelta(days=days_ahead)
        elif "thursday" in datetime_str:
            days_ahead = 3 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = today + datetime.timedelta(days=days_ahead)
        elif "friday" in datetime_str:
            days_ahead = 4 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = today + datetime.timedelta(days=days_ahead)
        elif "saturday" in datetime_str:
            days_ahead = 5 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = today + datetime.timedelta(days=days_ahead)
        elif "sunday" in datetime_str:
            days_ahead = 6 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            base_date = today + datetime.timedelta(days=days_ahead)
        else:
            # Try to parse common date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d %Y', '%B %d', '%d %B']:
                try:
                    parsed = datetime.datetime.strptime(datetime_str.split()[0], fmt)
                    # If no year provided, use current year
                    if parsed.year == 1900:
                        parsed = parsed.replace(year=now.year)
                    base_date = parsed
                    break
                except ValueError:
                    continue
            else:
                # If nothing worked, return current time
                return now
        
        # Try to extract time - improved patterns
        time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm)?',  # 12:30 pm
            r'(\d{1,2})\s*(am|pm)',           # 12 pm
            r'(\d{1,2})\s*(?:o\'clock|oclock)', # 12 o'clock
            r'(\d{1,2})(?:da|de)',            # Turkish: 9da (at 9)
        ]
        
        for pattern in time_patterns:
            time_match = re.search(pattern, datetime_str, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if len(time_match.groups()) > 1 and time_match.group(2) else 0
                am_pm = time_match.group(3) if len(time_match.groups()) > 2 else None
                
                # Handle AM/PM
                if am_pm and am_pm.lower() == 'pm' and hour < 12:
                    hour += 12
                elif am_pm and am_pm.lower() == 'am' and hour == 12:
                    hour = 0
                    
                return base_date.replace(hour=hour, minute=minute)
        
        # Check for relative times like "in 2 hours", "in 30 minutes"
        hours_match = re.search(r'in\s+(\d+)\s+hours?', datetime_str)
        if hours_match:
            hours = int(hours_match.group(1))
            return now + datetime.timedelta(hours=hours)
            
        mins_match = re.search(r'in\s+(\d+)\s+minutes?', datetime_str)
        if mins_match:
            minutes = int(mins_match.group(1))
            return now + datetime.timedelta(minutes=minutes)
        
        # Default to 9am if no time specified
        return base_date.replace(hour=9, minute=0)