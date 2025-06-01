import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

# Load environment variables
load_dotenv()

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        try:
            self.connect()
            self.setup_pgvector()
            self.setup_tables()
        except Exception as e:
            print(f"Error initializing database: {e}")
            # Clean up resources if initialization failed
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            # Re-raise the exception so caller knows initialization failed
            raise
    
    def connect(self):
        """Establish connection to PostgreSQL database"""
        try:
            # Print connection details for debugging (remove sensitive info in production)
            print(f"Connecting to database: {os.getenv('DB_NAME')} on {os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}")
            
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
                dbname=os.getenv("DB_NAME", "aura_calendar"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "")
            )
            # Use transactions for better control
            self.conn.autocommit = False
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            print("Database connection established successfully")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            print("Make sure the database exists and credentials are correct in your .env file")
            raise
    
    def setup_pgvector(self):
        """Set up pgvector extension if not already installed"""
        try:
            # Check if the vector extension is already installed
            self.cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
            if self.cursor.fetchone() is None:
                # If not, try to install it
                print("Installing pgvector extension...")
                self.cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                self.conn.commit()
                print("pgvector extension installed successfully")
            else:
                print("pgvector extension already installed")
        except Exception as e:
            print(f"Error setting up pgvector: {e}")
            print("Make sure pgvector is installed on your PostgreSQL server.")
            print("If you haven't installed it yet, you need to:")
            print("1. Install the pgvector extension on your PostgreSQL server")
            print("2. Create the extension in your database by running:")
            print("   CREATE EXTENSION vector;")
            self.conn.rollback()
            raise
    
    def table_exists(self, table_name):
        """Check if a table exists in the database"""
        self.cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        """, (table_name,))
        return self.cursor.fetchone()['exists']
    
    def setup_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            # Step 1: Create events table first
            if not self.table_exists('events'):
                print("Creating events table...")
                self.cursor.execute("""
                    CREATE TABLE events (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        description TEXT,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP NOT NULL,
                        location VARCHAR(200),
                        importance INTEGER DEFAULT 5,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status VARCHAR(20) DEFAULT 'active'
                    );
                """)
                self.conn.commit()
                print("Events table created successfully")
            else:
                print("Events table already exists")
            
            # Step 2: Create memory table after events table is created
            if not self.table_exists('memory'):
                print("Creating memory table...")
                self.cursor.execute("""
                    CREATE TABLE memory (
                        id SERIAL PRIMARY KEY,
                        event_id INTEGER,
                        content TEXT NOT NULL,
                        embedding vector(1536),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_event
                            FOREIGN KEY (event_id) 
                            REFERENCES events(id)
                            ON DELETE SET NULL
                    );
                """)
                self.conn.commit()
                print("Memory table created successfully")
            else:
                print("Memory table already exists")
            
            # Step 3: Create conversation_history table
            if not self.table_exists('conversation_history'):
                print("Creating conversation_history table...")
                self.cursor.execute("""
                    CREATE TABLE conversation_history (
                        id SERIAL PRIMARY KEY,
                        user_message TEXT NOT NULL,
                        bot_response TEXT NOT NULL,
                        related_event_id INTEGER,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_related_event
                            FOREIGN KEY (related_event_id) 
                            REFERENCES events(id)
                            ON DELETE SET NULL
                    );
                """)
                self.conn.commit()
                print("Conversation history table created successfully")
            else:
                print("Conversation history table already exists")
                
            print("Database tables setup complete")
        except Exception as e:
            print(f"Error setting up tables: {e}")
            self.conn.rollback()
            raise
    
    def add_event(self, event_data: Dict) -> int:
        """Add a new event to the calendar"""
        try:
            print(f"Attempting to add event: {event_data}")
            
            # Validate required fields
            required_fields = ['title', 'start_time', 'end_time']
            for field in required_fields:
                if field not in event_data:
                    raise ValueError(f"Missing required field: {field}")
            
            query = """
                INSERT INTO events 
                (title, description, start_time, end_time, location, importance) 
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            self.cursor.execute(
                query, 
                (
                    event_data['title'],
                    event_data.get('description', ''),
                    event_data['start_time'],
                    event_data['end_time'],
                    event_data.get('location', ''),
                    event_data.get('importance', 5)
                )
            )
            event_id = self.cursor.fetchone()['id']
            self.conn.commit()
            print(f"Event added successfully with ID: {event_id}")
            return event_id
        except Exception as e:
            print(f"Error adding event: {e}")
            self.conn.rollback()
            raise
    
    def update_event(self, event_id: int, event_data: Dict) -> bool:
        """Update an existing event"""
        try:
            print(f"Attempting to update event {event_id} with data: {event_data}")
            
            # Create dynamic update query based on provided fields
            update_parts = []
            params = []
            
            for key, value in event_data.items():
                if key in ['title', 'description', 'start_time', 'end_time', 'location', 'importance', 'status']:
                    update_parts.append(f"{key} = %s")
                    params.append(value)
            
            if not update_parts:
                print("No valid fields to update")
                return False
                
            query = f"""
                UPDATE events 
                SET {', '.join(update_parts)}
                WHERE id = %s;
            """
            params.append(event_id)
            
            self.cursor.execute(query, params)
            success = self.cursor.rowcount > 0
            self.conn.commit()
            print(f"Event {event_id} update result: {success} (rows affected: {self.cursor.rowcount})")
            return success
        except Exception as e:
            print(f"Error updating event: {e}")
            self.conn.rollback()
            raise
    
    def delete_event(self, event_id: int) -> bool:
        """Delete an event from the calendar - IMPROVED VERSION"""
        try:
            print(f"Attempting to delete event with ID: {event_id}")
            
            # Start a transaction
            self.cursor.execute("BEGIN;")
            
            # First, check if the event exists
            check_query = "SELECT id, title FROM events WHERE id = %s;"
            self.cursor.execute(check_query, (event_id,))
            existing_event = self.cursor.fetchone()
            
            if not existing_event:
                print(f"Event with ID {event_id} does not exist")
                self.cursor.execute("ROLLBACK;")
                return False
            
            print(f"Found event to delete: {existing_event['title']} (ID: {existing_event['id']})")
            
            # Delete related records first to maintain referential integrity
            # Delete conversation history references
            self.cursor.execute("UPDATE conversation_history SET related_event_id = NULL WHERE related_event_id = %s;", (event_id,))
            print(f"Cleared conversation history references for event {event_id}")
            
            # Delete memory entries
            self.cursor.execute("DELETE FROM memory WHERE event_id = %s;", (event_id,))
            deleted_memories = self.cursor.rowcount
            print(f"Deleted {deleted_memories} memory entries for event {event_id}")
            
            # Finally, delete the event itself
            delete_query = "DELETE FROM events WHERE id = %s;"
            self.cursor.execute(delete_query, (event_id,))
            deleted_count = self.cursor.rowcount
            
            # Commit the transaction
            self.cursor.execute("COMMIT;")
            
            print(f"Delete query executed. Rows affected: {deleted_count}")
            
            if deleted_count > 0:
                print(f"Successfully deleted event {event_id} and all related data")
                return True
            else:
                print(f"No event was deleted for ID {event_id}")
                return False
            
        except Exception as e:
            print(f"Error deleting event: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.cursor.execute("ROLLBACK;")
            except:
                pass  # Rollback might fail if connection is broken
            self.conn.rollback()
            raise
    
    def get_event(self, event_id: int) -> Optional[Dict]:
        """Get a specific event by ID"""
        try:
            print(f"Fetching event with ID: {event_id}")
            query = "SELECT * FROM events WHERE id = %s AND status = 'active';"
            self.cursor.execute(query, (event_id,))
            event = self.cursor.fetchone()
            
            if event:
                print(f"Found event: {event['title']} (ID: {event['id']})")
                return dict(event)
            else:
                print(f"No active event found with ID: {event_id}")
                return None
        except Exception as e:
            print(f"Error getting event: {e}")
            raise
    
    def find_events_by_title_and_time(self, title: str, reference_date: datetime) -> List[Dict]:
        "Find events matching a title and near a specific date"""
        try:
            print(f"Searching for events with title like '{title}' near {reference_date}")
            query = """
                SELECT * FROM events 
                WHERE status = 'active'
                AND LOWER(title) LIKE LOWER(%s)
                AND DATE(start_time) BETWEEN DATE(%s) - INTERVAL '1 day' AND DATE(%s) + INTERVAL '1 day';
            """
            like_pattern = f"%{title}%"
            self.cursor.execute(query, (like_pattern, reference_date, reference_date))
            rows = self.cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            print(f"Error finding events by title and time: {e}")
            return []

    def get_events_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get all events within a specific time range"""
        try:
            print(f"Querying events from {start_time} to {end_time}")
            
            query = """
                SELECT * FROM events 
                WHERE 
                    status = 'active' AND (
                        (start_time BETWEEN %s AND %s) OR
                        (end_time BETWEEN %s AND %s) OR
                        (start_time <= %s AND end_time >= %s)
                    )
                ORDER BY start_time ASC;
            """
            self.cursor.execute(query, (start_time, end_time, start_time, end_time, start_time, end_time))
            
            events = self.cursor.fetchall()
            print(f"Found {len(events)} active events")
            
            # Convert to list of dictionaries
            result = []
            for event in events:
                event_dict = dict(event)
                result.append(event_dict)
                
            return result
        except Exception as e:
            print(f"Error getting events in range: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def check_conflicting_events(self, start_time: datetime, end_time: datetime, exclude_event_id: Optional[int] = None) -> List[Dict]:
        """Check for conflicting events in the specified time range - FIXED VERSION"""
        try:
            print(f"Checking for conflicts between {start_time} and {end_time}")
            if exclude_event_id:
                print(f"Excluding event ID: {exclude_event_id}")
                
            # FIXED conflict detection logic:
            # Events are considered conflicting if they overlap in time
            # Two events overlap if: start1 < end2 AND start2 < end1
            # This properly handles all overlap scenarios while excluding adjacent events
            
            if exclude_event_id is not None:
                query = """
                    SELECT * FROM events 
                    WHERE 
                        status = 'active'
                        AND id != %s
                        AND start_time < %s 
                        AND end_time > %s
                    ORDER BY importance DESC, start_time ASC;
                """
                params = [exclude_event_id, end_time, start_time]
            else:
                query = """
                    SELECT * FROM events 
                    WHERE 
                        status = 'active'
                        AND start_time < %s 
                        AND end_time > %s
                    ORDER BY importance DESC, start_time ASC;
                """
                params = [end_time, start_time]
            
            self.cursor.execute(query, params)
            conflicts = self.cursor.fetchall()
            
            print(f"Found {len(conflicts)} conflicting events")
            
            # Convert to list of dictionaries and log details
            result = []
            for conflict in conflicts:
                conflict_dict = dict(conflict)
                print(f"  - Conflict: {conflict_dict['title']} at {conflict_dict['start_time']} to {conflict_dict['end_time']}")
                result.append(conflict_dict)
                
            return result
        except Exception as e:
            print(f"Error checking conflicting events: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def store_memory(self, event_id: Optional[int], content: str, embedding: List[float]) -> int:
        """Store a memory entry with vector embedding"""
        try:
            query = """
                INSERT INTO memory
                (event_id, content, embedding)
                VALUES (%s, %s, %s)
                RETURNING id;
            """
            self.cursor.execute(query, (event_id, content, embedding))
            memory_id = self.cursor.fetchone()['id']
            self.conn.commit()
            return memory_id
        except Exception as e:
            print(f"Error storing memory: {e}")
            self.conn.rollback()
            raise
    
    def query_similar_memories(self, embedding: List[float], limit: int = 5) -> List[Dict]:
        """Query similar memories using vector similarity search"""
        try:
            # First try with a simple query without vector operations
            try:
                # Note: We're just getting the most recent memories instead of using vector similarity
                # This is a workaround until pgvector is properly set up
                query = """
                    SELECT m.*, e.title as event_title, e.start_time, e.end_time, e.importance
                    FROM memory m
                    LEFT JOIN events e ON m.event_id = e.id
                    ORDER BY m.created_at DESC
                    LIMIT %s;
                """
                self.cursor.execute(query, (limit,))
                return self.cursor.fetchall()
            except Exception as e:
                print(f"Error with memory query: {e}")
                # Fallback to even simpler query
                query = """
                    SELECT * FROM memory
                    ORDER BY created_at DESC
                    LIMIT %s;
                """
                self.cursor.execute(query, (limit,))
                return self.cursor.fetchall()
        except Exception as e:
            print(f"Error querying memories: {e}")
            print("Returning empty list as fallback")
        return []
    
    def store_conversation(self, user_message: str, bot_response: str, related_event_id: Optional[int] = None) -> int:
        """Store a conversation entry"""
        try:
            # Verify the event exists if an ID is provided
            if related_event_id is not None:
                event = self.get_event(related_event_id)
                if not event:
                    print(f"Warning: Event ID {related_event_id} not found, storing conversation without event reference")
                    related_event_id = None
            
            query = """
                INSERT INTO conversation_history
                (user_message, bot_response, related_event_id)
                VALUES (%s, %s, %s)
                RETURNING id;
            """
            self.cursor.execute(query, (user_message, bot_response, related_event_id))
            conversation_id = self.cursor.fetchone()['id']
            self.conn.commit()
            return conversation_id
        except Exception as e:
            print(f"Error storing conversation: {e}")
            self.conn.rollback()
            raise
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """Get recent conversations"""
        try:
            query = """
                SELECT * FROM conversation_history
                ORDER BY timestamp DESC
                LIMIT %s;
            """
            self.cursor.execute(query, (limit,))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Error getting recent conversations: {e}")
            raise
    
    def get_all_events(self) -> List[Dict]:
        """Get all active events - useful for debugging"""
        try:
            query = """
                SELECT * FROM events 
                WHERE status = 'active'
                ORDER BY start_time ASC;
            """
            self.cursor.execute(query)
            events = self.cursor.fetchall()
            
            result = []
            for event in events:
                event_dict = dict(event)
                result.append(event_dict)
                
            return result
        except Exception as e:
            print(f"Error getting all events: {e}")
            return []
    
    def cleanup_orphaned_records(self):
        """Clean up orphaned records in related tables"""
        try:
            print("Cleaning up orphaned records...")
            
            # Clean up memory entries for non-existent events
            self.cursor.execute("""
                DELETE FROM memory 
                WHERE event_id IS NOT NULL 
                AND event_id NOT IN (SELECT id FROM events WHERE status = 'active');
            """)
            deleted_memories = self.cursor.rowcount
            
            # Clean up conversation history for non-existent events
            self.cursor.execute("""
                UPDATE conversation_history 
                SET related_event_id = NULL 
                WHERE related_event_id IS NOT NULL 
                AND related_event_id NOT IN (SELECT id FROM events WHERE status = 'active');
            """)
            updated_conversations = self.cursor.rowcount
            
            self.conn.commit()
            
            print(f"Cleaned up {deleted_memories} orphaned memory entries")
            print(f"Updated {updated_conversations} conversation references")
            
        except Exception as e:
            print(f"Error cleaning up orphaned records: {e}")
            self.conn.rollback()
    
    def get_database_stats(self) -> Dict:
        """Get database statistics for debugging"""
        try:
            stats = {}
            
            # Count events
            self.cursor.execute("SELECT COUNT(*) FROM events WHERE status = 'active';")
            stats['active_events'] = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM events WHERE status != 'active';")
            stats['inactive_events'] = self.cursor.fetchone()[0]
            
            # Count memories
            self.cursor.execute("SELECT COUNT(*) FROM memory;")
            stats['memory_entries'] = self.cursor.fetchone()[0]
            
            # Count conversations
            self.cursor.execute("SELECT COUNT(*) FROM conversation_history;")
            stats['conversations'] = self.cursor.fetchone()[0]
            
            return stats
        except Exception as e:
            print(f"Error getting database stats: {e}")
            return {}
    
    def close(self):
        """Close database connections"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("Database connection closed")