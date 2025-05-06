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
from model_mapper import map_db_event_to_api_event


# Load environment variables
load_dotenv()

class ConversationManager:
    def __init__(self):
        """Initialize the conversation manager with necessary components"""
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
            
        genai.configure(api_key=api_key)
        self.chat_model = genai.GenerativeModel('gemini-1.5-pro')
        
        # We'll use the same model for embeddings since embedding-001 isn't available
        self.embedding_model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Initialize components
        self.db = Database()
        self.intent_classifier = IntentClassifier()
        self.importance_classifier = ImportanceClassifier()
        
        # Initialize conversation state
        self.conversation_history = []
        self.current_event_context = None
    
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
    
    async def process_message(self, user_message: str) -> Dict:
        """
        Process a user message and generate an appropriate response
        
        Args:
            user_message: The user's message
        
        Returns:
            Dictionary with bot response and any actions to take
        """
        try:
            # Classify intent
            intent_data = await self.intent_classifier.classify_intent(
                user_message, 
                self.conversation_history[-5:] if self.conversation_history else None
            )
            
            # Store for response generation
            event_data = None
            event_action = None
            conflict_info = None
            
            # Handle different intents
            if intent_data["intent"] == "GENERAL_CONVERSATION":
                # For general conversation, just pass to response generation
                pass
                
# In your conversation_manager.py, find the part that handles CREATE_EVENT intent
# Add these debug prints:

            elif intent_data["intent"] == "CREATE_EVENT":
                if intent_data.get("needs_clarification", False):
                    # We'll handle clarification in response generation
                    print("Needs clarification for event creation")
                    pass
                else:
                    # Extract event details and classify importance
                    event_details = intent_data.get("event_details", {})
                    print(f"Extracted event details: {event_details}")
                    
                    if event_details and "start_time" in event_details and "end_time" in event_details:
                        # ... rest of your event creation code ...
                        try:
                            event_id = self.db.add_event(event_details)
                            print(f"Successfully created event with ID: {event_id}")
                            event_details["id"] = event_id
                            event_action = "created"
                            event_data = event_details
                            
                            # ... rest of your code ...
                        except Exception as e:
                            print(f"Error creating event: {e}")
                    
            elif intent_data["intent"] == "UPDATE_EVENT":
                # ... Remaining update event logic ...
                pass
                
            elif intent_data["intent"] == "DELETE_EVENT":
                # ... Remaining delete event logic ...
                pass
                
            elif intent_data["intent"] == "QUERY_EVENT" or intent_data["intent"] == "CHECK_AVAILABILITY":
                # ... Remaining query event logic ...
                pass
                
            elif intent_data["intent"] == "RESCHEDULE_EVENT":
                # ... Remaining reschedule event logic ...
                pass
            
            # Generate response based on intent and actions taken - simplified for now
            system_prompt = """
            You are an AI assistant for a calendar app called Aura Calendar. Your name is Aura.
            
            Your primary role is to help users manage their calendar events.
            
            When responding to the user:
            1. Be concise and helpful
            2. If you've taken an action (created/updated/deleted an event), confirm it clearly
            3. If there are scheduling conflicts, explain them and suggest alternatives
            4. For general questions, be conversational and friendly
            
            Current date: {current_date}
            Current time: {current_time}
            
            Intent detected: {intent}
            """
            
            # Format the prompt
            formatted_prompt = system_prompt.format(
                current_date=datetime.datetime.now().strftime('%Y-%m-%d'),
                current_time=datetime.datetime.now().strftime('%H:%M'),
                intent=intent_data["intent"]
            )
            
            # Add context information
            if event_data:
                formatted_prompt += f"\n\nEvent details: {json.dumps(event_data, default=str)}"
                
            if event_action:
                formatted_prompt += f"\n\nAction: Event was {event_action}."
                
            if conflict_info:
                formatted_prompt += "\n\nConflicting events:\n"
                for event in conflict_info:
                    formatted_prompt += (
                        f"- {event['title']} at {event['start_time'].strftime('%Y-%m-%d %H:%M')} "
                        f"(Importance: {event['importance']})\n"
                    )
            
            # Add the user message and generate response
            formatted_prompt += f"\n\nUser message: {user_message}\n\nYour response:"
            
            # Generate response using Gemini
            response = await self.chat_model.generate_content_async(formatted_prompt)
            response_text = response.text
            
            # Store the conversation
            self.conversation_history.append({
                "user_message": user_message,
                "bot_response": response_text,
                "intent": intent_data["intent"],
                "timestamp": datetime.datetime.now()
            })
            
            # Prepare the response object
            # Prepare the response object
            response_data = {
                "text": response_text,
                "ui_action": None,
            }

            
            if event_action in ["created", "updated", "rescheduled"] and isinstance(event_data, dict) and "id" in event_data:
                print(f"Adding UI action for {event_action} event: {event_data}")
                
                # Convert the event data to the API model format
                api_event = None
                if "id" in event_data:
                    # If this is an event object directly from this method
                    api_event = {
                        "event_id": event_data["id"],
                        "title": event_data.get("title", ""),
                        "description": event_data.get("description"),
                        "start_time": event_data.get("start_time"),
                        "end_time": event_data.get("end_time"),
                        "location": event_data.get("location"),
                        "importance": event_data.get("importance", 5),
                        "status": "active"
                    }
                
                response_data["ui_action"] = {
                    "type": "update_calendar",
                    "event": api_event
                }
                print(f"Final response data: {response_data}")
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