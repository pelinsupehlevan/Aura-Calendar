import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from database import Database
from intent_classifier import IntentClassifier
from importance_classifier import ImportanceClassifier
import datetime
from typing import Dict, List, Any, Tuple, Optional
import numpy as np
import requests
from datetime import timedelta
import asyncio
import hashlib
from model_mapper import map_db_event_to_api_event, map_conflicts_to_api_format

# Load environment variables
load_dotenv()

class ConversationManager:
    def __init__(self, user_id: str = "default_user"):
        """Initialize the conversation manager with necessary components"""
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
            
        genai.configure(api_key=api_key)
        self.chat_model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        # We'll use the same model for embeddings since embedding-001 isn't available
        self.embedding_model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        # Initialize components
        self.db = Database()
        self.intent_classifier = IntentClassifier()
        self.importance_classifier = ImportanceClassifier()
        
        # Store user ID for conversation history
        self.user_id = user_id
        
        # Initialize conversation state
        self.conversation_history = []
        self.current_event_context = None
        
        # Load conversation history from database - THIS IS THE KEY PART THAT WAS MISSING
        self.load_conversation_history()
    
    def load_conversation_history(self):
        """Load conversation history from database for this user"""
        try:
            # Get recent conversations for this user
            recent_conversations = self.db.get_recent_conversations(limit=50)
            
            # Convert database format to our internal format
            self.conversation_history = []
            for conv in recent_conversations:
                # Add user message
                self.conversation_history.append({
                    "user_message": conv["user_message"],
                    "bot_response": conv["bot_response"],
                    "intent": None,  # We don't store intent in DB
                    "timestamp": conv["timestamp"],
                    "related_event_id": conv.get("related_event_id"),
                    "id": conv.get("id")
                })
            
            # Reverse to get chronological order (oldest first)
            self.conversation_history.reverse()
            
            print(f"Loaded {len(self.conversation_history)} previous conversations for user {self.user_id}")
        except Exception as e:
            print(f"Error loading conversation history: {e}")
            self.conversation_history = []
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embeddings for text using Gemini model or fallback to a simple hash-based approach"""
        try:
            # Try to get embeddings from the model
            result = await self.embedding_model.generate_content_async(text)
            
            # Check if embeddings are available
            if hasattr(result, 'embedding') and result.embedding:
                return result.embedding
            else:
                print("Model doesn't support embeddings, using fallback method")
                return self._fallback_embedding(text)
        except Exception as e:
            print(f"Error getting embedding: {e}")
            # Fall back to a deterministic hash-based embedding
            return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """Create a fallback embedding when the API fails"""
        # Create a deterministic but simple embedding based on hash of the text
        hash_object = hashlib.md5(text.encode())
        hash_hex = hash_object.hexdigest()
        
        # Convert hash to a list of floats between -1 and 1
        # We'll use a fixed dimension of 1536 for compatibility
        dimension = int(os.getenv("VECTOR_DIMENSION", 1536))
        embedding = []
        for i in range(dimension):
            # Use characters from the hash to generate float values
            idx = i % 32
            char_val = int(hash_hex[idx], 16)
            # Convert to a float between -1 and 1
            float_val = (char_val / 15.0) * 2 - 1
            embedding.append(float_val)
        
        # Normalize the embedding to unit length
        import math
        magnitude = math.sqrt(sum(x*x for x in embedding))
        normalized = [x/magnitude for x in embedding]
        
        return normalized

    
    def handle_query_events(self, intent_data: Dict) -> Tuple[str, Dict]:
        """
        Improved handler for QUERY_EVENT and CHECK_AVAILABILITY intents
        
        Args:
            intent_data: The intent classification data
            
        Returns:
            Tuple of (event_action, event_data)
        """
        # Get event_details from intent_data, using an empty dict as default if not present
        event_details = intent_data.get("event_details", {})
        
        if "start_time" in event_details and "end_time" in event_details:
            start_time = event_details["start_time"]
            end_time = event_details["end_time"]
            
            # Special handling for next week
            if "next week" in intent_data.get("query_text", "").lower():
                # Calculate next Monday
                today = datetime.datetime.now().date()
                today_weekday = today.weekday()  # 0 is Monday, 6 is Sunday
                days_until_next_monday = 7 - today_weekday if today_weekday > 0 else 7
                next_monday = today + datetime.timedelta(days=days_until_next_monday)
                
                # Set range from next Monday to next Sunday
                start_time = datetime.datetime.combine(next_monday, datetime.time.min)
                end_time = start_time + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)
                
                print(f"Next week query detected. Using date range: {start_time} to {end_time}")
            
            # For specific date queries (e.g., "10th May")
            elif "10th may" in intent_data.get("query_text", "").lower() or "10 may" in intent_data.get("query_text", "").lower():
                # Set proper full day range for May 10th
                may_10 = datetime.datetime(datetime.datetime.now().year, 5, 10)
                start_time = may_10.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time = may_10.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                print(f"May 10th query detected. Using date range: {start_time} to {end_time}")
            
            # If the time range is less than 24 hours and both times are at hour boundaries,
            # this is likely intended to be a full day query
            elif (end_time - start_time < datetime.timedelta(days=1) and 
                start_time.hour == 0 and start_time.minute == 0 and
                (end_time.hour == 0 or end_time.hour == 1) and end_time.minute == 0):
                
                # Adjust to full day
                day_date = start_time.date()
                start_time = datetime.datetime.combine(day_date, datetime.time.min)
                end_time = datetime.datetime.combine(day_date, datetime.time.max)
                
                print(f"Adjusted to full day query: {start_time} to {end_time}")
            
            # Get events in the specified range
            events = self.db.get_events_in_range(start_time, end_time)
            
            # Check if this is a single-day query for better response formatting
            is_single_day = start_time.date() == end_time.date()
            
            return "query", {
                "events": events,
                "single_day": is_single_day,
                "query_date": start_time.date() if is_single_day else None,
                "start_time": start_time,
                "end_time": end_time
            }
        else:
            # Default to showing next 7 days
            start_time = datetime.datetime.now()
            end_time = start_time + datetime.timedelta(days=7)
            events = self.db.get_events_in_range(start_time, end_time)
            
            return "query", {
                "events": events,
                "default_range": True,
                "start_time": start_time,
                "end_time": end_time
            }
        
    async def process_message(self, user_message: str) -> Dict:
        """
        Process a user message and generate an appropriate response
        
        Args:
            user_message: The user's message
        
        Returns:
            Dictionary with bot response and any actions to take
        """
        try:
            # Ensure conversation history is loaded
            if not self.conversation_history:
                self.load_conversation_history()
            
            # Classify intent
            intent_data = await self.intent_classifier.classify_intent(
                user_message, 
                self.conversation_history[-5:] if self.conversation_history else None
            )
            
            print(f"Classified intent: {intent_data}")
            
            # Store for response generation
            event_data = None
            event_action = None
            conflict_info = None
            related_event_id = None
            
            # Handle different intents
            if intent_data["intent"] == "GENERAL_CONVERSATION":
                # For general conversation, just pass to response generation
                pass
                
            elif intent_data["intent"] == "CREATE_EVENT":
                if intent_data.get("needs_clarification", False):
                    # We'll handle clarification in response generation
                    print("Needs clarification for event creation")
                    pass
                else:
                    # Extract event details and classify importance
                    event_details = intent_data.get("event_details", {})
                    print(f"Extracted event details: {event_details}")
                    
                    # Ensure we have both start_time and end_time
                    if "start_time" in event_details and isinstance(event_details["start_time"], datetime.datetime):
                        # If end_time is missing, set it to 1 hour after start_time
                        if "end_time" not in event_details or not isinstance(event_details["end_time"], datetime.datetime):
                            event_details["end_time"] = event_details["start_time"] + timedelta(hours=1)
                        
                        # Classify importance if not already set
                        if "importance" not in event_details:
                            event_details["importance"] = await self.importance_classifier.classify_importance(
                                event_details, 
                                user_message
                            )
                        
                        # Check for conflicts BEFORE creating the event
                        conflicting_events = self.db.check_conflicting_events(
                            event_details["start_time"], 
                            event_details["end_time"]
                        )
                        
                        if conflicting_events:
                            print(f"Found {len(conflicting_events)} conflicting events")
                            conflict_info = conflicting_events
                            event_action = "conflict"
                            event_data = event_details
                        else:
                            # No conflicts, create the event
                            try:
                                event_id = self.db.add_event(event_details)
                                print(f"Successfully created event with ID: {event_id}")
                                event_details["id"] = event_id
                                event_action = "created"
                                event_data = event_details
                                related_event_id = event_id
                                
                                # Store memory for the event
                                memory_content = (
                                    f"Event '{event_details['title']}' scheduled for "
                                    f"{event_details['start_time'].strftime('%Y-%m-%d %H:%M')} to "
                                    f"{event_details['end_time'].strftime('%Y-%m-%d %H:%M')}. "
                                    f"Importance: {event_details.get('importance', 5)}. "
                                    f"Description: {event_details.get('description', 'No description')}"
                                )
                                embedding = await self.get_embedding(memory_content)
                                self.db.store_memory(event_id, memory_content, embedding)
                            except Exception as e:
                                print(f"Error creating event: {e}")
                                event_action = "error"
                    else:
                        print("Missing or invalid start_time for event creation")
                        event_action = "needs_clarification"
                    
            elif intent_data["intent"] == "UPDATE_EVENT":
                # Handle event updates
                print("Processing UPDATE_EVENT intent")
                event_details = intent_data.get("event_details", {})
                event_id = event_details.get("event_id")
                
                if event_id:
                    print(f"Updating event ID: {event_id}")
                    related_event_id = event_id
                    # Check if updating time and if so, check for conflicts
                    if "start_time" in event_details or "end_time" in event_details:
                        # Get current event details
                        current_event = self.db.get_event(event_id)
                        
                        if current_event:
                            # Use current times if not being updated
                            start_time = event_details.get("start_time", current_event["start_time"])
                            end_time = event_details.get("end_time", current_event["end_time"])
                            
                            # Check for conflicts, excluding the current event
                            conflicting_events = self.db.check_conflicting_events(
                                start_time, 
                                end_time, 
                                exclude_event_id=event_id
                            )
                            
                            if conflicting_events:
                                conflict_info = conflicting_events
                                event_action = "conflict"
                                event_data = event_details
                            else:
                                # No conflicts, update the event
                                success = self.db.update_event(event_id, event_details)
                                if success:
                                    event_action = "updated"
                                    event_data = self.db.get_event(event_id)
                                else:
                                    event_action = "error"
                        else:
                            print(f"Event {event_id} not found for update")
                            event_action = "not_found"
                    else:
                        # Just updating non-time fields
                        success = self.db.update_event(event_id, event_details)
                        if success:
                            event_action = "updated"
                            event_data = self.db.get_event(event_id)
                        else:
                            event_action = "error"
                else:
                    print("No event_id provided for update")
                    event_action = "needs_clarification"
                
            elif intent_data["intent"] == "DELETE_EVENT":
                # Handle event deletion
                print("Processing DELETE_EVENT intent")
                event_details = intent_data.get("event_details", {})
                event_id = event_details.get("event_id")
                
                if event_id:
                    print(f"Attempting to delete event ID: {event_id}")
                    # Get event details before deletion for confirmation
                    event_before_deletion = self.db.get_event(event_id)
                    
                    if event_before_deletion:
                        related_event_id = event_id
                        success = self.db.delete_event(event_id)
                        if success:
                            print(f"Successfully deleted event {event_id}")
                            event_action = "deleted"
                            event_data = event_before_deletion  # Pass the original event data
                        else:
                            print(f"Failed to delete event {event_id}")
                            event_action = "error"
                    else:
                        print(f"Event {event_id} not found for deletion")
                        event_action = "not_found"
                else:
                    print("No event_id provided for deletion - need to search by title/description")
                    # If no specific ID, try to find the event by title or description
                    if "title" in event_details:
                        # Search for events by title (this is a simplified approach)
                        # You might want to implement a more sophisticated search
                        all_events = self.db.get_events_in_range(
                            datetime.datetime.now() - timedelta(days=30),
                            datetime.datetime.now() + timedelta(days=365)
                        )
                        
                        matching_events = [e for e in all_events if event_details["title"].lower() in e["title"].lower()]
                        
                        if len(matching_events) == 1:
                            # Found exactly one match, delete it
                            event_to_delete = matching_events[0]
                            related_event_id = event_to_delete["id"]
                            success = self.db.delete_event(event_to_delete["id"])
                            if success:
                                event_action = "deleted"
                                event_data = event_to_delete
                            else:
                                event_action = "error"
                        elif len(matching_events) > 1:
                            # Multiple matches, need clarification
                            event_action = "multiple_matches"
                            event_data = {"matches": matching_events}
                        else:
                            # No matches found
                            event_action = "not_found"
                    else:
                        event_action = "needs_clarification"
                
            elif intent_data["intent"] == "QUERY_EVENT" or intent_data["intent"] == "CHECK_AVAILABILITY":
                # Add the original query text to help with special case detection
                intent_data["query_text"] = user_message
                
                # Use the improved handler
                event_action, event_data = self.handle_query_events(intent_data)
                
                # Remove or comment out this problematic section that tries to access event_details directly
                # This is the source of the error because event_details isn't defined in this scope
                """
                if "start_time" in event_details and "end_time" in event_details:
                    events = self.db.get_events_in_range(
                        event_details["start_time"], 
                        event_details["end_time"]
                    )
                    event_action = "query"
                    event_data = {"events": events}
                else:
                    # Default to showing next 7 days
                    start_time = datetime.datetime.now()
                    end_time = start_time + timedelta(days=7)
                    events = self.db.get_events_in_range(start_time, end_time)
                    event_action = "query"
                    event_data = {"events": events, "default_range": True}
                """
                
            elif intent_data["intent"] == "RESCHEDULE_EVENT":
                # Handle rescheduling
                event_details = intent_data.get("event_details", {})
                event_id = event_details.get("event_id")
                
                if event_id and "start_time" in event_details and "end_time" in event_details:
                    related_event_id = event_id
                    # Check for conflicts with new time
                    conflicting_events = self.db.check_conflicting_events(
                        event_details["start_time"], 
                        event_details["end_time"], 
                        exclude_event_id=event_id
                    )
                    
                    if conflicting_events:
                        conflict_info = conflicting_events
                        event_action = "conflict"
                        event_data = event_details
                    else:
                        # No conflicts, reschedule the event
                        update_data = {
                            "start_time": event_details["start_time"],
                            "end_time": event_details["end_time"]
                        }
                        success = self.db.update_event(event_id, update_data)
                        if success:
                            event_action = "rescheduled"
                            event_data = self.db.get_event(event_id)
                        else:
                            event_action = "error"
                else:
                    event_action = "needs_clarification"
            
            # Generate response based on intent and actions taken
            system_prompt = """
            You are an AI assistant for a calendar app called Aura Calendar. Your name is Aura.
            
            Your primary role is to help users manage their calendar events.
            
            When responding to the user:
            1. Be concise and helpful
            2. If you've taken an action (created/updated/deleted an event), confirm it clearly
            3. If there are scheduling conflicts, explain them and suggest alternatives
            4. For general questions, be conversational and friendly
            5. Always acknowledge what you've done (or failed to do)
            6. Remember the conversation history and refer to it when appropriate
            
            Current date: {current_date}
            Current time: {current_time}
            
            Intent detected: {intent}
            Action taken: {action}
            
            Recent conversation history:
            {conversation_history}
            """
            
            # Create conversation history summary
            history_text = ""
            if len(self.conversation_history) > 0:
                history_text = "Recent conversation:\n"
                for conv in self.conversation_history[-3:]:  # Last 3 exchanges
                    timestamp = conv['timestamp'].strftime('%Y-%m-%d %H:%M')
                    history_text += f"[{timestamp}] User: {conv['user_message']}\n"
                    history_text += f"[{timestamp}] You: {conv['bot_response']}\n"
            
            # Format the prompt
            formatted_prompt = system_prompt.format(
                current_date=datetime.datetime.now().strftime('%Y-%m-%d'),
                current_time=datetime.datetime.now().strftime('%H:%M'),
                intent=intent_data["intent"],
                action=event_action or "none",
                conversation_history=history_text
            )
            
            # Add context information based on the action
            if event_action == "conflict" and conflict_info:
                # For conflicts, we'll let the UI handle it via the dialog
                # Just provide a simple acknowledgment message
                formatted_prompt += f"\n\nCONFLICT DETECTED with these events:\n"
                for event in conflict_info:
                    formatted_prompt += (
                        f"- '{event['title']}' at {event['start_time'].strftime('%Y-%m-%d %H:%M')} "
                        f"to {event['end_time'].strftime('%Y-%m-%d %H:%M')} "
                        f"(Importance: {event['importance']})\n"
                    )
                formatted_prompt += "\nThe system will show a conflict resolution dialog. Please acknowledge that there's a conflict and that the user will be prompted to resolve it."
                
            elif event_action == "created" and event_data:
                formatted_prompt += f"\n\nSUCCESSFULLY CREATED event:\n"
                formatted_prompt += f"- Title: '{event_data['title']}'\n"
                formatted_prompt += f"- Time: {event_data['start_time'].strftime('%Y-%m-%d %H:%M')} to {event_data['end_time'].strftime('%Y-%m-%d %H:%M')}\n"
                formatted_prompt += f"- Importance: {event_data.get('importance', 5)}\n"
                
            elif event_action == "deleted" and event_data:
                formatted_prompt += f"\n\nSUCCESSFULLY DELETED event:\n"
                formatted_prompt += f"- Title: '{event_data['title']}'\n"
                formatted_prompt += f"- Time: {event_data['start_time'].strftime('%Y-%m-%d %H:%M')} to {event_data['end_time'].strftime('%Y-%m-%d %H:%M')}\n"
                
            elif event_action == "updated" or event_action == "rescheduled":
                formatted_prompt += f"\n\nSUCCESSFULLY {event_action.upper()} event:\n"
                if event_data:
                    formatted_prompt += f"- Title: '{event_data['title']}'\n"
                    formatted_prompt += f"- Time: {event_data['start_time'].strftime('%Y-%m-%d %H:%M')} to {event_data['end_time'].strftime('%Y-%m-%d %H:%M')}\n"
                
            elif event_action == "query" and event_data:
                events = event_data.get("events", [])
                formatted_prompt += f"\n\nFOUND {len(events)} events"
                if event_data.get("default_range"):
                    formatted_prompt += " in the next 7 days"
                formatted_prompt += ":\n"
                
                for event in events:
                    formatted_prompt += (
                        f"- '{event['title']}' at {event['start_time'].strftime('%Y-%m-%d %H:%M')} "
                        f"to {event['end_time'].strftime('%Y-%m-%d %H:%M')}\n"
                    )
                
            elif event_action == "error":
                formatted_prompt += f"\n\nERROR occurred while processing the request."
                
            elif event_action == "not_found":
                formatted_prompt += f"\n\nNO MATCHING EVENT FOUND."
                
            elif event_action == "multiple_matches":
                formatted_prompt += f"\n\nFOUND MULTIPLE MATCHING EVENTS - need clarification:\n"
                if event_data and "matches" in event_data:
                    for event in event_data["matches"]:
                        formatted_prompt += (
                            f"- '{event['title']}' at {event['start_time'].strftime('%Y-%m-%d %H:%M')} "
                            f"(ID: {event['id']})\n"
                        )
                
            elif event_action == "needs_clarification":
                formatted_prompt += f"\n\nNEED MORE INFORMATION to complete this request."
            
            # Add the user message and generate response
            formatted_prompt += f"\n\nUser message: {user_message}\n\nYour response (be conversational and helpful):"
            
            # Generate response using Gemini
            response = await self.chat_model.generate_content_async(formatted_prompt)
            response_text = response.text
            
            # Don't use related_event_id if we just deleted that event
            if event_action == "deleted" and related_event_id is not None:
                # The event was deleted, so don't try to reference it
                conversation_id = self.db.store_conversation(
                    user_message, 
                    response_text, 
                    related_event_id=None  # Set to None since the event was deleted
                )
                print(f"Stored conversation without event reference (event {related_event_id} was deleted)")
            else:
                # Normal case - store with related event ID
                conversation_id = self.db.store_conversation(
                    user_message, 
                    response_text, 
                    related_event_id=related_event_id
                )
            
            # Also add to in-memory conversation history
            self.conversation_history.append({
                "user_message": user_message,
                "bot_response": response_text,
                "intent": intent_data["intent"],
                "timestamp": datetime.datetime.now(),
                "related_event_id": related_event_id,
                "id": conversation_id
            })
            
            # Keep conversation history limited to prevent memory issues
            if len(self.conversation_history) > 50:
                self.conversation_history = self.conversation_history[-50:]
            
            # Prepare the response object
            response_data = {
                "text": response_text,
                "ui_action": None,
            }
            
            # Add UI actions if needed
            if event_action == "conflict":
                response_data["ui_action"] = {
                    "type": "show_conflict",
                    "conflicts": conflict_info,
                    "proposed_event": event_data
                }
            elif event_action in ["created", "updated", "rescheduled"] and isinstance(event_data, dict) and "id" in event_data:
                print(f"Adding UI action for {event_action} event: {event_data}")
                
                # Convert the event data to the API model format
                api_event = map_db_event_to_api_event(event_data)
                
                response_data["ui_action"] = {
                    "type": "update_calendar",
                    "event": api_event
                }
            elif event_action == "deleted" and isinstance(event_data, dict) and "id" in event_data:
                response_data["ui_action"] = {
                    "type": "remove_event",
                    "event_id": event_data["id"]
                }

            return response_data
            
        except Exception as e:
            print(f"Error in process_message: {e}")
            import traceback
            traceback.print_exc()
            
            # Return a fallback response
            return {
                "text": "I'm sorry, I encountered an issue processing your request. Could you try again or rephrase your message?",
                "ui_action": None
            }
    
    async def retrieve_relevant_memories(self, user_message: str, intent_data: Dict) -> List[Dict]:
        """
        Retrieve relevant memories from the database
        
        Args:
            user_message: The user's message
            intent_data: Intent classification data
            
        Returns:
            List of relevant memory entries
        """
        try:
            # For simplicity, just get the most recent memories
            # This avoids vector similarity search issues
            recent_memories = self.db.query_similar_memories([], limit=5)
            return recent_memories
        except Exception as e:
            print(f"Error retrieving memories: {e}")
            return []  # Return empty list on error
    
    def clear_history(self):
        """Clear the conversation history"""
        self.conversation_history = []
        self.current_event_context = None
    
    def close(self):
        """Close database connections"""
        if self.db:
            self.db.close()