import requests
import json
from datetime import datetime, timedelta

# Base URL for the API
BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint"""
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health check: {response.status_code}")
    print(f"Response: {response.json()}")
    print(f"Headers: {dict(response.headers)}")
    print()

def test_get_events():
    """Test getting events"""
    # Get events for the next month
    start = datetime.now()
    end = start + timedelta(days=30)
    
    params = {
        "start": start.isoformat(),
        "end": end.isoformat()
    }
    
    response = requests.get(f"{BASE_URL}/events", params=params)
    print(f"Get events: {response.status_code}")
    
    if response.status_code == 200:
        events = response.json()
        print(f"Found {len(events)} events")
        for event in events:
            print(f"- {event['title']} at {event['start_time']}")
    else:
        print(f"Error: {response.text}")
    
    print(f"Headers: {dict(response.headers)}")
    print()

def test_cors():
    """Test CORS headers"""
    # Send an OPTIONS request to check CORS headers
    headers = {
        "Origin": "http://localhost:8080",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type"
    }
    
    response = requests.options(f"{BASE_URL}/events", headers=headers)
    print(f"CORS check: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print()

def test_create_event():
    """Test creating an event"""
    # Create a test event
    event_data = {
        "title": "Test Event",
        "description": "This is a test event",
        "start_time": (datetime.now() + timedelta(days=1)).isoformat(),
        "end_time": (datetime.now() + timedelta(days=1, hours=1)).isoformat(),
        "importance": 5,
        "location": "Test Location"
    }
    
    response = requests.post(
        f"{BASE_URL}/events",
        json=event_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Create event: {response.status_code}")
    
    if response.status_code == 200:
        event = response.json()
        print(f"Created event: {event}")
    else:
        print(f"Error: {response.text}")
    
    print()

if __name__ == "__main__":
    print("Testing API...")
    test_health()
    test_cors()
    test_get_events()
    test_create_event()
    print("Done!")