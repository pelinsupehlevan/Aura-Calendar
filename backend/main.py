import os
import json
import asyncio
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cors_fix import add_cors_middleware
from model_mapper import map_db_event_to_api_event, map_many_db_events_to_api_events

# Import both implementations
from database import Database
from conversation_manager import ConversationManager
from simple_chat import SimpleChat  # Keep this as a fallback

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Aura Calendar API")
add_cors_middleware(app) 

# Add CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Add this line
)

# Initialize both conversation handlers
conversation_manager = None
simple_chat = SimpleChat()

# Try to initialize the full conversation manager, but don't crash if it fails
try:
    conversation_manager = ConversationManager()
    print("Full conversation manager initialized successfully!")
except Exception as e:
    print(f"Warning: Could not initialize full conversation manager: {e}")
    print("Running in simplified mode with SimpleChat")
    # We'll use simple_chat as fallback

# Request/Response Models
class MessageRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class EventRequest(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    importance: Optional[int] = None
    event_id: Optional[int] = None

class EventResponse(BaseModel):
    event_id: int
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    importance: int
    status: str

class MessageResponse(BaseModel):
    text: str
    ui_action: Optional[Dict[str, Any]] = None

@app.on_event("shutdown")
def shutdown_event():
    """Close connections on shutdown"""
    if conversation_manager:
        conversation_manager.close()

def get_db():
    """Database dependency"""
    db = Database()
    try:
        yield db
    finally:
        db.close()

@app.post("/message", response_model=MessageResponse)
async def process_message(request: MessageRequest):
    """
    Process a user message and return a response
    
    This endpoint handles both general conversation and calendar-specific intents
    """
    try:
        # Try using the full conversation manager first
        if conversation_manager:
            try:
                print(f"Processing with full conversation manager: {request.message}")
                response = await conversation_manager.process_message(request.message)
                print("Message processed successfully with full conversation manager")
                return response
            except Exception as e:
                print(f"Error with full conversation manager: {e}")
                print("Falling back to simple chat")
        
        # Fall back to the simple chat if needed
        print(f"Processing with simple chat: {request.message}")
        response = await simple_chat.process_message(request.message)
        return response
    except Exception as e:
        print(f"Error processing message: {e}")
        import traceback
        traceback.print_exc()
        
        # Return a user-friendly error instead of a 500
        return {
            "text": f"I'm sorry, I encountered an error processing your message. Please try again later.",
            "ui_action": None
        }

@app.post("/events", response_model=EventResponse)
async def create_event(event: EventRequest, db: Database = Depends(get_db)):
    """
    Create a new calendar event
    
    This endpoint allows direct event creation without going through the conversation flow
    """
    try:
        # If importance not provided, use a default value
        if event.importance is None:
            # Try to use the importance classifier if available
            if conversation_manager:
                try:
                    importance = await conversation_manager.importance_classifier.classify_importance(
                        {
                            "title": event.title,
                            "description": event.description,
                            "start_time": event.start_time,
                            "end_time": event.end_time,
                            "location": event.location
                        }
                    )
                    event.importance = importance
                except Exception as e:
                    print(f"Error classifying importance: {e}")
                    event.importance = 5  # Default importance
            else:
                event.importance = 5  # Default importance
        
        # Create event in database
        event_dict = event.dict(exclude={"event_id"})
        event_id = db.add_event(event_dict)
        
        # Try to store memory for the event if conversation manager is available
        if conversation_manager:
            try:
                memory_content = (
                    f"Event '{event.title}' scheduled for "
                    f"{event.start_time.strftime('%Y-%m-%d %H:%M')} to "
                    f"{event.end_time.strftime('%Y-%m-%d %H:%M')}. "
                    f"Importance: {event.importance}. "
                    f"Description: {event.description or 'No description'}"
                )
                embedding = await conversation_manager.get_embedding(memory_content)
                db.store_memory(event_id, memory_content, embedding)
            except Exception as e:
                print(f"Warning: Could not store memory for event: {e}")
        
        # Fetch and return the created event

    
        created_event = db.get_event(event_id)
        return map_db_event_to_api_event(created_event)
    

    except Exception as e:
        print(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail="Error creating event")


@app.get("/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Database = Depends(get_db)):
    """Get details of a specific event"""
    event = db.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Convert to API model
    api_event = map_db_event_to_api_event(event)
    return api_event

@app.put("/events/{event_id}", response_model=EventResponse)
async def update_event(event_id: int, event: EventRequest, db: Database = Depends(get_db)):
    """Update an existing event"""
    # Check if event exists
    existing_event = db.get_event(event_id)
    if not existing_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    try:
        # Update the event
        event_dict = event.dict(exclude={"event_id"}, exclude_none=True)
        success = db.update_event(event_id, event_dict)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update event")
        
        # Try to store memory for the update if conversation manager is available
        if conversation_manager:
            try:
                memory_content = (
                    f"Event '{event.title}' updated. "
                    f"Now scheduled for {event.start_time.strftime('%Y-%m-%d %H:%M')} to "
                    f"{event.end_time.strftime('%Y-%m-%d %H:%M')}."
                )
                embedding = await conversation_manager.get_embedding(memory_content)
                db.store_memory(event_id, memory_content, embedding)
            except Exception as e:
                print(f"Warning: Could not store memory for event update: {e}")
        
        # Return the updated event
        updated_event = db.get_event(event_id)
        return map_db_event_to_api_event(updated_event)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating event: {e}")
        raise HTTPException(status_code=500, detail="Error updating event")

@app.delete("/events/{event_id}", response_model=dict)
async def delete_event(event_id: int, db: Database = Depends(get_db)):
    """Delete an event"""
    # Check if event exists
    existing_event = db.get_event(event_id)
    if not existing_event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    try:
        # Delete the event
        success = db.delete_event(event_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete event")
        
        # Try to store memory for the deletion if conversation manager is available
        if conversation_manager:
            try:
                memory_content = (
                    f"Event '{existing_event['title']}' that was scheduled for "
                    f"{existing_event['start_time'].strftime('%Y-%m-%d %H:%M')} was deleted."
                )
                embedding = await conversation_manager.get_embedding(memory_content)
                db.store_memory(None, memory_content, embedding)
            except Exception as e:
                print(f"Warning: Could not store memory for event deletion: {e}")
        
        return {"message": "Event deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting event: {e}")
        raise HTTPException(status_code=500, detail="Error deleting event")

@app.get("/events", response_model=List[EventResponse])
def get_events_in_range(
    start: Optional[datetime] = None, 
    end: Optional[datetime] = None, 
    db: Database = Depends(get_db)
):
    """Get events in a specific time range"""
    try:
        # Default to current day if not specified
        if not start:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if not end:
            end = start + timedelta(days=7)  # Show a week of events by default
        
        print(f"Fetching events from {start} to {end}")
            
        # Try to get events from the database
        events = db.get_events_in_range(start, end)
        
        # For debugging - print what we found
        print(f"Found {len(events)} events in database")
        
        # Convert database model to API model
        api_events = map_many_db_events_to_api_events(events)
        
        # Return the converted events
        return api_events
    except Exception as e:
        print(f"Error getting events: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Error getting events")

@app.get("/check-conflicts")
def check_conflicts(
    start: datetime,
    end: datetime,
    exclude_event_id: Optional[int] = None,
    db: Database = Depends(get_db)
):
    """Check for conflicting events in a time range"""
    try:
        conflicts = db.check_conflicting_events(start, end, exclude_event_id)
        return {"conflicts": conflicts, "has_conflicts": len(conflicts) > 0}
    except Exception as e:
        print(f"Error checking conflicts: {e}")
        raise HTTPException(status_code=500, detail="Error checking conflicts")

# @app.get("/mock-events")
# def get_mock_events():
#     """Test endpoint that always returns mock events"""
    
#     # Get current time rounded to the nearest hour
#     now = datetime.now().replace(minute=0, second=0, microsecond=0)
#     tomorrow = now + timedelta(days=1)
#     day_after = now + timedelta(days=2)
    
#     # Create mock events
#     events = [
#         {
#             "event_id": 1,
#             "title": "Team Meeting",
#             "description": "Weekly team sync to discuss project progress",
#             "start_time": now.replace(hour=10, minute=0).isoformat(),
#             "end_time": now.replace(hour=11, minute=0).isoformat(),
#             "location": "Conference Room A",
#             "importance": 8,
#             "status": "active"
#         },
#         {
#             "event_id": 2,
#             "title": "Lunch with Alex",
#             "description": "Discuss partnership opportunities",
#             "start_time": tomorrow.replace(hour=12, minute=30).isoformat(),
#             "end_time": tomorrow.replace(hour=13, minute=30).isoformat(),
#             "location": "Cafe Bella",
#             "importance": 5,
#             "status": "active"
#         },
#         {
#             "event_id": 3,
#             "title": "Project Deadline",
#             "description": "Submit final deliverables for client review",
#             "start_time": day_after.isoformat(),
#             "end_time": day_after.replace(hour=17).isoformat(),
#             "location": "",
#             "importance": 10,
#             "status": "active"
#         }
#     ]
    
#     # Return with proper CORS headers
#     return events

# Simple health check endpoint
@app.get("/health")
async def health_check():
    """
    Simple health check endpoint to verify the API is running
    """
    mode = "full" if conversation_manager else "simplified"
    return {"status": "ok", "message": f"Aura Calendar API is running in {mode} mode"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)