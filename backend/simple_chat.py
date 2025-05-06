import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables
load_dotenv()

class SimpleChat:
    """A simplified chat handler that doesn't require the database or embeddings"""
    
    def __init__(self):
        """Initialize with Gemini API"""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Simple conversation history
        self.history = []
    
    async def process_message(self, message: str) -> Dict[str, Any]:
        """Process a user message and generate a response"""
        try:
            # Add to history
            self.history.append({"role": "user", "content": message})
            
            # Create system prompt
            system_prompt = """
            You are an AI assistant for a calendar app called Aura Calendar. Your name is Aura.
            
            You can:
            1. Help users manage their calendar events
            2. Answer questions about scheduling
            3. Provide general assistance
            
            When responding to the user:
            1. Be concise and helpful
            2. If you think they want to create/update/delete an event, mention that functionality
               but explain that you're currently in simplified mode.
            3. Be friendly and professional
            """
            
            # Create a history string for context
            history_text = ""
            if len(self.history) > 1:
                for i in range(max(0, len(self.history) - 5), len(self.history) - 1):
                    entry = self.history[i]
                    history_text += f"{entry['role'].capitalize()}: {entry['content']}\n"
            
            # Create full prompt
            full_prompt = f"{system_prompt}\n\n"
            
            if history_text:
                full_prompt += f"Recent conversation:\n{history_text}\n"
                
            full_prompt += f"User: {message}\n\nYour response:"
            
            # Generate response with Gemini
            response = await self.model.generate_content_async(full_prompt)
            response_text = response.text
            
            # Add to history
            self.history.append({"role": "assistant", "content": response_text})
            
            # Keep history limited
            if len(self.history) > 10:
                self.history = self.history[-10:]
            
            # Return formatted response
            return {
                "text": response_text,
                "ui_action": None
            }
        except Exception as e:
            print(f"Error in simple chat: {e}")
            return {
                "text": f"I encountered an error while processing your message. Please check your Gemini API key and network connection. Error: {str(e)}",
                "ui_action": None
            }