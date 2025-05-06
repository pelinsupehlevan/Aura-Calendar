import os
import sys
from datetime import datetime, timedelta
from database import Database

def test_database_operations():
    """Test database operations to diagnose issues"""
    print("=== Database Operations Test ===")
    
    db = None
    try:
        # Initialize database
        db = Database()
        print("✓ Database initialized successfully")
        
        # Test 1: Create a test event
        print("\n1. Testing event creation...")
        test_event = {
            "title": "Test Event",
            "description": "This is a test event",
            "start_time": datetime.now() + timedelta(hours=1),
            "end_time": datetime.now() + timedelta(hours=2),
            "location": "Test Location",
            "importance": 7
        }
        
        event_id = db.add_event(test_event)
        print(f"✓ Created event with ID: {event_id}")
        
        # Test 2: Retrieve the event
        print("\n2. Testing event retrieval...")
        retrieved_event = db.get_event(event_id)
        if retrieved_event:
            print(f"✓ Retrieved event: {retrieved_event['title']}")
            print(f"  Start: {retrieved_event['start_time']}")
            print(f"  End: {retrieved_event['end_time']}")
        else:
            print("✗ Failed to retrieve event")
        
        # Test 3: Update the event
        print("\n3. Testing event update...")
        update_data = {
            "title": "Updated Test Event",
            "importance": 9
        }
        
        success = db.update_event(event_id, update_data)
        if success:
            print("✓ Event updated successfully")
            updated_event = db.get_event(event_id)
            print(f"  New title: {updated_event['title']}")
            print(f"  New importance: {updated_event['importance']}")
        else:
            print("✗ Failed to update event")
        
        # Test 4: Check for conflicts
        print("\n4. Testing conflict detection...")
        conflicts = db.check_conflicting_events(
            test_event["start_time"],
            test_event["end_time"]
        )
        print(f"✓ Found {len(conflicts)} conflicting events")
        for conflict in conflicts:
            print(f"  - {conflict['title']} (ID: {conflict['id']})")
        
        # Test 5: Delete the event
        print("\n5. Testing event deletion...")
        success = db.delete_event(event_id)
        if success:
            print("✓ Event deleted successfully")
            
            # Verify deletion
            deleted_event = db.get_event(event_id)
            if deleted_event is None:
                print("✓ Deletion verified - event no longer exists")
            else:
                print("✗ Deletion failed - event still exists")
        else:
            print("✗ Failed to delete event")
        
        # Test 6: Test with multiple events
        print("\n6. Testing with multiple events...")
        
        # Create multiple test events
        event_ids = []
        for i in range(3):
            event = {
                "title": f"Multi Test Event {i+1}",
                "description": f"Multi test event {i+1}",
                "start_time": datetime.now() + timedelta(hours=i+3),
                "end_time": datetime.now() + timedelta(hours=i+4),
                "importance": 5 + i
            }
            event_id = db.add_event(event)
            event_ids.append(event_id)
            print(f"Created event {i+1} with ID: {event_id}")
        
        # Query events in range
        start_range = datetime.now()
        end_range = datetime.now() + timedelta(hours=8)
        events_in_range = db.get_events_in_range(start_range, end_range)
        print(f"Found {len(events_in_range)} events in specified range")
        for event in events_in_range:
            print(f"  - {event['title']} (ID: {event['id']})")
        
        # Delete all test events
        deleted_count = 0
        for event_id in event_ids:
            if db.delete_event(event_id):
                deleted_count += 1
        
        print(f"Successfully deleted {deleted_count}/{len(event_ids)} events")
        
        # Final verification
        final_events = db.get_events_in_range(start_range, end_range)
        print(f"Final check: {len(final_events)} events remain in range")
        if final_events:
            for event in final_events:
                print(f"  - {event['title']} (ID: {event['id']})")
        
        print("\n✓ All tests completed!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always close the database connection
        if db and hasattr(db, 'close'):
            try:
                db.close()
                print("\nDatabase connection closed")
            except Exception as e:
                print(f"Error closing database: {e}")

def test_database_connection():
    """Test basic database connection"""
    print("=== Database Connection Test ===")
    
    try:
        import psycopg2
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Connection parameters
        params = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
            "dbname": os.getenv("DB_NAME", "aura_calendar"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "")
        }
        
        print(f"Testing connection with:")
        print(f"  Host: {params['host']}")
        print(f"  Port: {params['port']}")
        print(f"  Database: {params['dbname']}")
        print(f"  User: {params['user']}")
        
        # Attempt connection
        conn = psycopg2.connect(**params)
        print("✓ Database connection successful!")
        
        # Test basic query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✓ PostgreSQL version: {version}")
        
        # Check for events table
        cursor.execute("""
            SELECT tablename FROM pg_tables 
            WHERE tablename = 'events';
        """)
        
        if cursor.fetchone():
            print("✓ Events table exists")
            
            # Count existing events
            cursor.execute("SELECT COUNT(*) FROM events;")
            count = cursor.fetchone()[0]
            print(f"✓ Events table has {count} events")
        else:
            print("✗ Events table not found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nPlease check:")
        print("1. PostgreSQL is running")
        print("2. Database 'aura_calendar' exists")
        print("3. Credentials in .env file are correct")
        print("4. PostgreSQL is accepting connections")

if __name__ == "__main__":
    print("Starting database tests...\n")
    
    # First test the basic connection
    test_database_connection()
    
    print("\n" + "="*50 + "\n")
    
    # Then test database operations
    test_database_operations()
    
    print("\nTest completed.")