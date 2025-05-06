from typing import Dict, List, Any, Optional

def map_db_event_to_api_event(db_event: Dict) -> Dict:
    """Convert a database event dictionary to an API event model"""
    if not db_event:
        return None
    
    # Create a new dictionary with the correct field names
    api_event = {
        "event_id": db_event.get("id"),
        "title": db_event.get("title", ""),
        "description": db_event.get("description"),
        "start_time": db_event.get("start_time"),
        "end_time": db_event.get("end_time"),
        "location": db_event.get("location"),
        "importance": db_event.get("importance", 5),
        "status": db_event.get("status", "active")
    }
    
    return api_event

def map_many_db_events_to_api_events(db_events: List[Dict]) -> List[Dict]:
    """Convert a list of database events to API event models"""
    if not db_events:
        return []
    
    return [map_db_event_to_api_event(event) for event in db_events]