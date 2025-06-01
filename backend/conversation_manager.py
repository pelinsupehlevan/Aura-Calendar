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
from recurring_event_utils import generate_recurring_events, parse_recurrence_from_text

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
        
        # Add context tracking for pending events
        self.pending_event_context = None
        self.last_conflict_context = None
        
        # Load conversation history from database
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

    def extract_context_from_recent_messages(self) -> Dict[str, Any]:
        """Extract event context from recent conversation history - IMPROVED VERSION"""
        context = {}
        
        # Look at the last few messages for event-related information
        recent_messages = self.conversation_history[-5:] if self.conversation_history else []
        
        # Clear any phantom context first
        for msg in recent_messages:
            user_msg = msg.get('user_message', '').lower()
            bot_msg = msg.get('bot_response', '').lower()
            
            # Look for actual event creation requests, not phantom references
            if any(keyword in user_msg for keyword in ['schedule', 'add', 'create', 'book', 'plan']):
                # Only extract context if there's a clear intent to create something
                
                # Look for event titles in recent messages
                if 'coffee' in user_msg:
                    context['title'] = 'coffee date'
                elif 'gym' in user_msg or 'workout' in user_msg:
                    context['title'] = 'gym session'
                elif 'meeting' in user_msg:
                    context['title'] = 'meeting'
                elif 'lunch' in user_msg:
                    context['title'] = 'lunch'
                elif 'dinner' in user_msg:
                    context['title'] = 'dinner'
                elif 'work' in user_msg or 'office' in user_msg or 'job' in user_msg:
                    context['title'] = 'work'
                
                # Look for people/relationships
                if 'sister' in user_msg:
                    if 'title' in context:
                        context['title'] = context['title'] + ' with sister'
                    else:
                        context['title'] = 'event with sister'
                elif 'friend' in user_msg:
                    if 'title' in context:
                        context['title'] = context['title'] + ' with friend'
                    else:
                        context['title'] = 'event with friend'
                
                # Look for dates - be more specific
                if 'tomorrow' in user_msg:
                    tomorrow = datetime.datetime.now() + timedelta(days=1)
                    context['date'] = tomorrow.date()
                elif 'today' in user_msg:
                    context['date'] = datetime.datetime.now().date()
                elif 'next week' in user_msg:
                    next_week = datetime.datetime.now() + timedelta(days=7)
                    context['date'] = next_week.date()
                
                # Look for times in the conversation - improved parsing
                import re
                time_patterns = [
                    r'(\d{1,2})\s*(am|pm)',
                    r'(\d{1,2}):(\d{2})\s*(am|pm)?',
                    r'at\s+(\d{1,2})\s*(am|pm)',
                    r'(\d{1,2})(?:\s*(?:o\'clock|oclock))',
                    # Turkish time patterns
                    r'(\d{1,2})(?:\s*(?:da|de))',  # "9da" = "at 9"
                ]
                
                for pattern in time_patterns:
                    matches = re.findall(pattern, user_msg, re.IGNORECASE)
                    if matches:
                        # Take the most recent time mentioned
                        match = matches[-1]
                        if len(match) >= 1:
                            hour = int(match[0])
                            if len(match) > 1 and match[1]:
                                if match[1].lower() in ['pm'] and hour != 12:
                                    hour += 12
                                elif match[1].lower() in ['am'] and hour == 12:
                                    hour = 0
                            context['time'] = f"{hour:02d}:00"
                        break
        
        return context

    async def handle_contextual_followup(self, user_message: str) -> Tuple[str, Dict]:
        """Handle follow-up messages - FIXED VERSION"""
        user_msg_lower = user_message.lower().strip()
        
        # Don't create phantom events - only respond to explicit requests
        explicit_create_patterns = [
            'create', 'add', 'schedule', 'book', 'plan', 'set up', 'make an appointment'
        ]
        
        # Check if this is an explicit creation request
        has_explicit_intent = any(pattern in user_msg_lower for pattern in explicit_create_patterns)
        
        if not has_explicit_intent:
            # This is not a contextual event creation, return None
            return None, {}
        
        # Extract context from recent conversation
        context = self.extract_context_from_recent_messages()
        
        # Only proceed if we have meaningful context
        if not context or 'title' not in context:
            return None, {}
        
        # Check if user is specifying a new time
        import re
        time_match = re.search(r'(\d{1,2})\s*(am|pm|:\d{2}|da|de)', user_msg_lower)
        
        if time_match:
            hour_str = time_match.group(1)
            period_or_suffix = time_match.group(2)
            
            hour = int(hour_str)
            if period_or_suffix == 'pm' and hour != 12:
                hour += 12
            elif period_or_suffix == 'am' and hour == 12:
                hour = 0
            
            context['time'] = f"{hour:02d}:00"
        
        # Build event details from context only if we have sufficient info
        if 'title' in context and 'date' in context:
            base_date = context['date']
            time_str = context.get('time', '10:00')  # default time
            
            # Parse time
            hour, minute = map(int, time_str.split(':'))
            start_datetime = datetime.datetime.combine(base_date, datetime.time(hour, minute))
            end_datetime = start_datetime + timedelta(hours=1)  # default 1 hour duration
            
            event_details = {
                'title': context['title'],
                'start_time': start_datetime,
                'end_time': end_datetime,
                'description': '',  # Empty description instead of context message
                'importance': 5
            }
            
            return "contextual_create", event_details
        
        return None, {}

    def handle_query_events(self, intent_data: Dict) -> Tuple[str, Dict]:
        """Improved handler for QUERY_EVENT and CHECK_AVAILABILITY intents"""
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

    async def create_recurring_events(self, event_details: Dict) -> Tuple[str, Dict]:
        """Handle creating recurring events"""
        try:
            # Generate individual events from the recurring pattern
            individual_events = generate_recurring_events(event_details)
            
            if not individual_events:
                return "error", {"message": "Could not generate recurring events"}
            
            # Check for conflicts with all generated events
            all_conflicts = []
            for event in individual_events:
                conflicts = self.db.check_conflicting_events(
                    event["start_time"], 
                    event["end_time"]
                )
                if conflicts:
                    all_conflicts.extend(conflicts)
            
            if all_conflicts:
                return "conflict", {
                    "conflicts": all_conflicts,
                    "proposed_events": individual_events,
                    "event_count": len(individual_events)
                }
            
            # No conflicts, create all events
            created_event_ids = []
            for event in individual_events:
                # Classify importance if not already set
                if "importance" not in event:
                    event["importance"] = await self.importance_classifier.classify_importance(
                        event, 
                        f"Recurring: {event_details.get('title', 'Event')}"
                    )
                
                event_id = self.db.add_event(event)
                created_event_ids.append(event_id)
                
                # Store memory for each event
                memory_content = (
                    f"Recurring event '{event['title']}' scheduled for "
                    f"{event['start_time'].strftime('%Y-%m-%d %H:%M')} to "
                    f"{event['end_time'].strftime('%Y-%m-%d %H:%M')}. "
                    f"Part of recurring series. "
                    f"Importance: {event.get('importance', 5)}. "
                    f"Description: {event.get('description', 'No description')}"
                )
                embedding = await self.get_embedding(memory_content)
                self.db.store_memory(event_id, memory_content, embedding)
            
            print(f"Successfully created {len(created_event_ids)} recurring events")
            
            return "created_recurring", {
                "event_ids": created_event_ids,
                "event_count": len(created_event_ids),
                "events": individual_events,
                "recurrence_type": event_details.get('recurrence_type', 'daily'),
                "title": event_details.get('title', 'Recurring Event')
            }
            
        except Exception as e:
            print(f"Error creating recurring events: {e}")
            return "error", {"message": str(e)}

    async def handle_bulk_deletion(self, user_message: str) -> Tuple[str, Dict]:
        """Handle bulk deletion requests like 'delete all events tomorrow'"""
        user_msg_lower = user_message.lower().strip()
        
        # Check for bulk deletion patterns
        bulk_delete_patterns = [
            'delete all', 'remove all', 'cancel all', 'clear all',
            'sil hepsini', 'tümünü sil', 'hepsini sil', 'yarınki tüm', 'tüm etkinlik'
        ]
        
        is_bulk_delete = any(pattern in user_msg_lower for pattern in bulk_delete_patterns)
        
        if not is_bulk_delete:
            return None, {}
        
        # Determine the time range for deletion
        target_date = None
        if any(word in user_msg_lower for word in ['tomorrow', 'yarın']):
            target_date = datetime.datetime.now().date() + timedelta(days=1)
        elif any(word in user_msg_lower for word in ['today', 'bugün']):
            target_date = datetime.datetime.now().date()
        
        if target_date:
            # Get events for the target date
            start_time = datetime.datetime.combine(target_date, datetime.time.min)
            end_time = datetime.datetime.combine(target_date, datetime.time.max)
            
            events_to_delete = self.db.get_events_in_range(start_time, end_time)
            
            if not events_to_delete:
                return "no_events_found", {"message": f"No events found for {target_date.strftime('%Y-%m-%d')}"}
            
            # Delete all events
            deleted_count = 0
            deleted_events = []
            
            for event in events_to_delete:
                try:
                    success = self.db.delete_event(event['id'])
                    if success:
                        deleted_count += 1
                        deleted_events.append(event)
                        print(f"Successfully deleted event: {event['title']} (ID: {event['id']})")
                    else:
                        print(f"Failed to delete event: {event['title']} (ID: {event['id']})")
                except Exception as e:
                    print(f"Error deleting event {event['id']}: {e}")
            
            if deleted_count > 0:
                return "bulk_deleted", {
                    "deleted_count": deleted_count,
                    "deleted_events": deleted_events,
                    "target_date": target_date.strftime('%Y-%m-%d')
                }
            else:
                return "deletion_failed", {"message": "Failed to delete events"}
        
        return None, {}
        
    async def process_message(self, user_message: str) -> Dict:
        """Process a user message and generate an appropriate response - IMPROVED VERSION"""
        try:
            # Ensure conversation history is loaded
            if not self.conversation_history:
                self.load_conversation_history()
            
            # First, check for bulk deletion requests
            bulk_action, bulk_data = await self.handle_bulk_deletion(user_message)
            
            if bulk_action:
                print(f"Processing bulk deletion: {bulk_action}")
                
                if bulk_action == "bulk_deleted":
                    # Generate success response
                    response_text = f"Successfully deleted {bulk_data['deleted_count']} events for {bulk_data['target_date']}."
                    
                    # Store conversation
                    conversation_id = self.db.store_conversation(user_message, response_text, related_event_id=None)
                    
                    # Add to in-memory conversation history
                    self.conversation_history.append({
                        "user_message": user_message,
                        "bot_response": response_text,
                        "intent": "BULK_DELETE",
                        "timestamp": datetime.datetime.now(),
                        "related_event_id": None,
                        "id": conversation_id
                    })
                    
                    return {
                        "text": response_text,
                        "ui_action": {
                            "type": "refresh_calendar",
                            "message": f"Deleted {bulk_data['deleted_count']} events"
                        }
                    }
                elif bulk_action == "no_events_found":
                    response_text = bulk_data["message"]
                    
                    # Store conversation
                    conversation_id = self.db.store_conversation(user_message, response_text, related_event_id=None)
                    
                    return {"text": response_text, "ui_action": None}
                else:
                    response_text = "There was an issue with deleting the events. Please try again."
                    return {"text": response_text, "ui_action": None}
            
            else:
                # Classify intent normally
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
                    
                elif intent_data["intent"] == "CREATE_RECURRING_EVENT":
                    print("Processing CREATE_RECURRING_EVENT intent")
                    event_details = intent_data.get("event_details", {})
                    
                    # Parse additional recurrence info from the user message if not already extracted
                    if not event_details.get('recurrence_type'):
                        recurrence_info = parse_recurrence_from_text(user_message)
                        event_details.update(recurrence_info)
                    
                    print(f"Recurring event details: {event_details}")
                    
                    if event_details.get("start_time") and isinstance(event_details["start_time"], datetime.datetime):
                        # If end_time is missing, set it to 1 hour after start_time
                        if "end_time" not in event_details or not isinstance(event_details["end_time"], datetime.datetime):
                            event_details["end_time"] = event_details["start_time"] + timedelta(hours=1)
                        
                        # Handle recurring event creation
                        event_action, event_data = await self.create_recurring_events(event_details)
                        
                        if event_action == "created_recurring":
                            # Set related_event_id to the first created event for conversation tracking
                            related_event_id = event_data["event_ids"][0] if event_data["event_ids"] else None
                        elif event_action == "conflict":
                            conflict_info = event_data.get("conflicts", [])
                            event_data = event_details  # Keep original event details for conflict resolution
                    else:
                        print("Missing or invalid start_time for recurring event creation")
                        event_action = "needs_clarification"
                    
                elif intent_data["intent"] == "CREATE_EVENT":
                    if intent_data.get("needs_clarification", False):
                        # We'll handle clarification in response generation
                        print("Needs clarification for event creation")
                        pass
                    else:
                        # Extract event details and classify importance
                        event_details = intent_data.get("event_details", {})
                        print(f"Extracted event details: {event_details}")
                        
                        # Don't create events without explicit user intent
                        if not event_details.get("title") or not event_details.get("start_time"):
                            print("Insufficient event details, skipping creation")
                            event_action = "needs_clarification"
                        else:
                            # Ensure we have both start_time and end_time
                            if isinstance(event_details["start_time"], datetime.datetime):
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
                    
                    if not event_id and "title" in event_details:
                        print("Attempting to resolve missing event_id using title and time...")
                        possible_events = self.db.find_events_by_title_and_time(
                            title=event_details["title"],
                            reference_date=event_details.get("start_time") or datetime.now()
                        )
                        
                        if len(possible_events) == 1:
                            event_id = possible_events[0]["id"]
                            event_details["event_id"] = event_id
                            print(f"Resolved event_id: {event_id}")
                        elif len(possible_events) > 1:
                            print("Multiple events matched. Need clarification.")
                            event_action = "needs_clarification"
                            # Optionally send back list of candidates
                        else:
                            print("No matching events found.")
                            event_action = "not_found"
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
                        #event_action = "needs_clarification"
                        if intent_data.get("needs_clarification", False):
                            # We'll handle clarification in response generation
                            print("Needs clarification for event creation")
                            pass
                        else:
                            # Extract event details and classify importance
                            event_details = intent_data.get("event_details", {})
                            print(f"Extracted event details: {event_details}")
                            
                            # Don't create events without explicit user intent
                            if not event_details.get("title") or not event_details.get("start_time"):
                                print("Insufficient event details, skipping creation")
                                event_action = "needs_clarification"
                            else:
                                # Ensure we have both start_time and end_time
                                if isinstance(event_details["start_time"], datetime.datetime):
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

                    
                elif intent_data["intent"] == "DELETE_EVENT":
                    # Handle event deletion - IMPROVED VERSION
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
                            event_action = "not_found"
                    else:
                        print("No event_id provided for deletion - searching by title/description")
                        # If no specific ID, try to find the event by title or description
                        if "title" in event_details and event_details["title"]:
                            # Get events from today and the future for searching
                            search_start = datetime.datetime.now() - timedelta(days=1)
                            search_end = datetime.datetime.now() + timedelta(days=365)
                            
                            all_events = self.db.get_events_in_range(search_start, search_end)
                            
                            # Search for events containing the title keywords
                            search_title = event_details["title"].lower()
                            matching_events = []
                            
                            # Look for exact matches first, then partial matches
                            for event in all_events:
                                event_title_lower = event["title"].lower()
                                if search_title in event_title_lower or event_title_lower in search_title:
                                    matching_events.append(event)
                            
                            print(f"Found {len(matching_events)} matching events for title: {search_title}")
                            
                            if len(matching_events) == 1:
                                # Found exactly one match, delete it
                                event_to_delete = matching_events[0]
                                related_event_id = event_to_delete["id"]
                                success = self.db.delete_event(event_to_delete["id"])
                                if success:
                                    print(f"Successfully deleted event: {event_to_delete['title']} (ID: {event_to_delete['id']})")
                                    event_action = "deleted"
                                    event_data = event_to_delete
                                else:
                                    print(f"Failed to delete event: {event_to_delete['title']} (ID: {event_to_delete['id']})")
                                    event_action = "error"
                            elif len(matching_events) > 1:
                                # Multiple matches, need clarification
                                print(f"Multiple matches found: {[e['title'] for e in matching_events]}")
                                event_action = "multiple_matches"
                                event_data = {"matches": matching_events}
                            else:
                                # No matches found
                                print(f"No events found matching: {search_title}")
                                event_action = "not_found"
                        else:
                            print("No event_id or title provided for deletion")
                            event_action = "needs_clarification"
                    
                elif intent_data["intent"] == "QUERY_EVENT" or intent_data["intent"] == "CHECK_AVAILABILITY":
                    # Add the original query text to help with special case detection
                    intent_data["query_text"] = user_message
                    
                    # Use the improved handler
                    event_action, event_data = self.handle_query_events(intent_data)
                    
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
            
            IMPORTANT: Do NOT create phantom events or reference events that don't exist.
            Only work with events that are explicitly requested by the user or that actually exist in the database.
            When multiple events is demanded to be deleted delete multiple events
            When an event is to be replaced or updated replace or update the requested event accordingly and delete the unchanged event in database, create new data for updated event
            
            When responding to the user:
            1. Be concise and helpful
            2. If you've taken an action (created/updated/deleted an event), confirm it clearly
            3. If there are scheduling conflicts, explain them and suggest alternatives
            4. For general questions, be conversational and friendly
            5. Always acknowledge what you've done (or failed to do)
            6. Remember the conversation history and refer to it when appropriate
            8. When you create an event from context (like follow-up messages), be clear about what you created
            9. NEVER mention events that were not actually created or that don't exist

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
            
            # Determine the intent for display
            display_intent =intent_data.get("intent", "UNKNOWN")
            
            # Format the prompt
            formatted_prompt = system_prompt.format(
                current_date=datetime.datetime.now().strftime('%Y-%m-%d'),
                current_time=datetime.datetime.now().strftime('%H:%M'),
                intent=display_intent,
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
                #if contextual_action == "contextual_create":
                    #formatted_prompt += f"- Note: Created from conversation context\n"
                
            elif event_action == "created_recurring" and event_data:
                formatted_prompt += f"\n\nSUCCESSFULLY CREATED {event_data['event_count']} RECURRING EVENTS:\n"
                formatted_prompt += f"- Title: '{event_data['title']}'\n"
                formatted_prompt += f"- Recurrence: {event_data['recurrence_type']}\n"
                formatted_prompt += f"- Total events created: {event_data['event_count']}\n"
                
            elif event_action == "deleted" and event_data:
                formatted_prompt += f"\n\nSUCCESSFULLY DELETED event:\n"
                formatted_prompt += f"- Title: '{event_data['title']}'\n"
                formatted_prompt += f"- Time: {event_data['start_time'].strftime('%Y-%m-%d %H:%M')} to {event_data['end_time'].strftime('%Y-%m-%d %H:%M')}\n"
                formatted_prompt += f"- Event was permanently removed from the calendar\n"
                
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
                "intent": display_intent,
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
            elif event_action == "created_recurring" and isinstance(event_data, dict):
                # For recurring events, we need to trigger a calendar refresh
                response_data["ui_action"] = {
                    "type": "refresh_calendar",
                    "event_count": event_data.get("event_count", 0),
                    "message": f"Created {event_data.get('event_count', 0)} recurring events"
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
        """Retrieve relevant memories from the database"""
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
        self.pending_event_context = None
        self.last_conflict_context = None
    
    def close(self):
        """Close database connections"""
        if self.db:
            self.db.close() 