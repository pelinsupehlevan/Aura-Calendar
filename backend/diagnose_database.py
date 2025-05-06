import os
import sys
from datetime import datetime, timedelta
from database import Database
from pprint import pprint

def diagnose_database():
    """Diagnose current state of database"""
    print("=== Database Diagnostic Script ===")
    
    db = None
    try:
        # Initialize database
        db = Database()
        print("✓ Database initialized successfully")
        
        # Check all events in the database
        print("\n1. Checking all events in database...")
        start_time = datetime.now() - timedelta(days=365)  # Look back 1 year
        end_time = datetime.now() + timedelta(days=365)    # Look forward 1 year
        
        all_events = db.get_events_in_range(start_time, end_time)
        
        if not all_events:
            print("✓ No events found in database")
        else:
            print(f"✓ Found {len(all_events)} events:")
            for i, event in enumerate(all_events, 1):
                print(f"\n  Event {i}:")
                print(f"    ID: {event['id']}")
                print(f"    Title: {event['title']}")
                print(f"    Start: {event['start_time']}")
                print(f"    End: {event['end_time']}")
                print(f"    Importance: {event['importance']}")
                print(f"    Status: {event['status']}")
        
        # Test conflict detection with an example time slot
        print("\n2. Testing conflict detection...")
        test_start = datetime.now() + timedelta(hours=1)
        test_end = datetime.now() + timedelta(hours=2)
        
        conflicts = db.check_conflicting_events(test_start, test_end)
        
        if not conflicts:
            print(f"✓ No conflicts found for time slot {test_start} to {test_end}")
        else:
            print(f"✓ Found {len(conflicts)} conflicts for time slot {test_start} to {test_end}:")
            for conflict in conflicts:
                print(f"    - {conflict['title']} (ID: {conflict['id']})")
        
        # Test deletion functionality with a temporary event
        print("\n3. Testing deletion functionality...")
        
        # Create a temporary event
        temp_event = {
            "title": "Temporary Test Event",
            "description": "This event will be deleted",
            "start_time": datetime.now() + timedelta(hours=10),
            "end_time": datetime.now() + timedelta(hours=11),
            "importance": 1
        }
        
        temp_event_id = db.add_event(temp_event)
        print(f"  Created temporary event with ID: {temp_event_id}")
        
        # Verify it exists
        retrieved = db.get_event(temp_event_id)
        if retrieved:
            print(f"  ✓ Temporary event exists: {retrieved['title']}")
        else:
            print("  ✗ Temporary event not found after creation")
        
        # Delete it
        deleted = db.delete_event(temp_event_id)
        if deleted:
            print("  ✓ Temporary event deleted successfully")
        else:
            print("  ✗ Failed to delete temporary event")
        
        # Verify deletion
        verified = db.get_event(temp_event_id)
        if verified is None:
            print("  ✓ Deletion verified - event no longer exists")
        else:
            print("  ✗ Deletion failed - event still exists")
        
        # Check database tables exist
        print("\n4. Checking database tables...")
        tables = ['events', 'memory', 'conversation_history']
        
        for table in tables:
            if db.table_exists(table):
                print(f"  ✓ Table '{table}' exists")
                
                # Count rows
                db.cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = db.cursor.fetchone()[0]
                print(f"    - Contains {count} rows")
            else:
                print(f"  ✗ Table '{table}' missing")
        
        print("\n✓ Diagnostic completed!")
        
    except Exception as e:
        print(f"\n✗ Diagnostic failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always close the database connection
        if db and hasattr(db, 'close'):
            try:
                db.close()
            except Exception as e:
                print(f"Error closing database: {e}")

if __name__ == "__main__":
    diagnose_database()