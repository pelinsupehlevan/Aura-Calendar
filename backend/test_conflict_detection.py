import asyncio
from conversation_manager import ConversationManager
from database import Database
from datetime import datetime, timedelta

async def test_conflict_detection():
    """Test that conflict detection works properly"""
    print("=== Testing Conflict Detection ===")
    
    # Initialize conversation manager
    manager = ConversationManager()
    
    try:
        # Create a test event
        print("\n1. Creating initial test event...")
        response1 = await manager.process_message("Create a meeting called 'Test Meeting' on Friday at 2pm")
        print(f"Response: {response1['text']}")
        
        # Try to create a conflicting event
        print("\n2. Trying to create a conflicting event...")
        response2 = await manager.process_message("Create a 'Dentist Appointment' on Friday at 2:30pm")
        print(f"Response: {response2['text']}")
        
        # Check if conflict was detected
        if response2['ui_action'] and response2['ui_action']['type'] == 'show_conflict':
            print("✓ Conflict detection works! Conflicts found:")
            for conflict in response2['ui_action']['conflicts']:
                print(f"  - {conflict['title']} at {conflict['start_time']}")
        else:
            print("✗ Conflict detection failed - no conflicts detected")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.close()

async def test_deletion():
    """Test that deletion works properly"""
    print("\n\n=== Testing Event Deletion ===")
    
    # Initialize conversation manager
    manager = ConversationManager()
    
    try:
        # Create a test event to delete
        print("\n1. Creating test event to delete...")
        response1 = await manager.process_message("Create a meeting called 'Delete Me Meeting' tomorrow at 10am")
        print(f"Response: {response1['text']}")
        
        # Try to delete the event
        print("\n2. Trying to delete the event...")
        response2 = await manager.process_message("Delete the 'Delete Me Meeting'")
        print(f"Response: {response2['text']}")
        
        # Check if deletion was successful
        if response2['ui_action'] and response2['ui_action']['type'] == 'remove_event':
            print("✓ Deletion successful! Event removed.")
            print(f"  Deleted event ID: {response2['ui_action']['event_id']}")
        else:
            print("✗ Deletion failed - no removal action detected")
        
        # Verify the event is gone
        print("\n3. Verifying deletion...")
        response3 = await manager.process_message("Show me tomorrow's events")
        print(f"Response: {response3['text']}")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.close()

async def test_duplicate_prevention():
    """Test that duplicate events are prevented"""
    print("\n\n=== Testing Duplicate Event Prevention ===")
    
    # Initialize conversation manager  
    manager = ConversationManager()
    
    try:
        # Create the same event twice
        print("\n1. Creating first event...")
        response1 = await manager.process_message("Create a 'Team Meeting' on Monday at 9am")
        print(f"Response: {response1['text']}")
        
        print("\n2. Trying to create the same event again...")
        response2 = await manager.process_message("Create a 'Team Meeting' on Monday at 9am")
        print(f"Response: {response2['text']}")
        
        # Check if duplicate was prevented
        if response2['ui_action'] and response2['ui_action']['type'] == 'show_conflict':
            print("✓ Duplicate prevention works! Conflict detected.")
        else:
            print("✗ Duplicate was not prevented")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.close()

async def main():
    """Run all tests"""
    print("Starting comprehensive tests for conflicts and deletions...\n")
    
    await test_conflict_detection()
    await test_deletion()
    await test_duplicate_prevention()
    
    print("\n\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(main())