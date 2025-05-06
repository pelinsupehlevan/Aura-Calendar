#!/usr/bin/env python3
"""Test script to verify conflict detection logic"""

import sys
from datetime import datetime, timedelta
from database import Database

def test_conflict_detection():
    """Test various conflict scenarios"""
    db = Database()
    
    try:
        # Create test events
        print("=== Setting up test events ===")
        
        # Event 1: 12:00 PM - 2:00 PM
        event1 = {
            "title": "Meeting 1",
            "description": "12-2pm meeting",
            "start_time": datetime.now().replace(hour=12, minute=0, second=0, microsecond=0),
            "end_time": datetime.now().replace(hour=14, minute=0, second=0, microsecond=0),
            "importance": 5
        }
        
        # Event 2: 2:00 PM - 3:00 PM (should NOT conflict with Event 1)
        event2 = {
            "title": "Meeting 2",
            "description": "2-3pm meeting",
            "start_time": datetime.now().replace(hour=14, minute=0, second=0, microsecond=0),
            "end_time": datetime.now().replace(hour=15, minute=0, second=0, microsecond=0),
            "importance": 5
        }
        
        # Event 3: 1:30 PM - 3:30 PM (should conflict with both)
        event3 = {
            "title": "Meeting 3",
            "description": "1:30-3:30pm meeting",
            "start_time": datetime.now().replace(hour=13, minute=30, second=0, microsecond=0),
            "end_time": datetime.now().replace(hour=15, minute=30, second=0, microsecond=0),
            "importance": 5
        }
        
        # Clean up any existing test events
        print("Cleaning up existing test events...")
        all_events = db.get_events_in_range(
            datetime.now() - timedelta(days=1),
            datetime.now() + timedelta(days=1)
        )
        for event in all_events:
            if event['title'].startswith('Meeting '):
                db.delete_event(event['id'])
        
        # Add the test events
        print("\nAdding test events...")
        event1_id = db.add_event(event1)
        print(f"Created Event 1 (ID: {event1_id}): {event1['title']} - {event1['start_time']} to {event1['end_time']}")
        
        event2_id = db.add_event(event2)
        print(f"Created Event 2 (ID: {event2_id}): {event2['title']} - {event2['start_time']} to {event2['end_time']}")
        
        # Test conflict detection
        print("\n=== Testing conflict detection ===")
        
        # Test 1: Check if Event 2 conflicts with Event 1 (it shouldn't)
        print(f"\nTest 1: Check if {event2['title']} conflicts with existing events")
        conflicts = db.check_conflicting_events(event2['start_time'], event2['end_time'])
        print(f"Conflicts found: {len(conflicts)}")
        for conflict in conflicts:
            print(f"  - {conflict['title']} (ID: {conflict['id']})")
        print(f"Expected: 0 conflicts (adjacent events should not conflict)")
        
        # Test 2: Check if Event 3 conflicts with existing events (it should)
        print(f"\nTest 2: Check if {event3['title']} conflicts with existing events")
        conflicts = db.check_conflicting_events(event3['start_time'], event3['end_time'])
        print(f"Conflicts found: {len(conflicts)}")
        for conflict in conflicts:
            print(f"  - {conflict['title']} (ID: {conflict['id']})")
        print(f"Expected: 2 conflicts (should conflict with both Event 1 and Event 2)")
        
        # Test 3: Test with event exclusion
        print(f"\nTest 3: Check Event 3 conflicts excluding Event 1")
        conflicts = db.check_conflicting_events(event3['start_time'], event3['end_time'], exclude_event_id=event1_id)
        print(f"Conflicts found: {len(conflicts)}")
        for conflict in conflicts:
            print(f"  - {conflict['title']} (ID: {conflict['id']})")
        print(f"Expected: 1 conflict (should only conflict with Event 2)")
        
        # Cleanup
        print("\n=== Cleaning up test events ===")
        db.delete_event(event1_id)
        db.delete_event(event2_id)
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_conflict_detection()