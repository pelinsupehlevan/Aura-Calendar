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
        """Delete an event from the calendar"""
        try:
            print(f"Attempting to delete event with ID: {event_id}")
            
            # First, check if the event exists
            check_query = "SELECT id, title FROM events WHERE id = %s;"
            self.cursor.execute(check_query, (event_id,))
            existing_event = self.cursor.fetchone()
            
            if not existing_event:
                print(f"Event with ID {event_id} does not exist")
                return False
            
            print(f"Found event to delete: {existing_event['title']} (ID: {existing_event['id']})")
            
            # Delete the event
            query = "DELETE FROM events WHERE id = %s;"
            self.cursor.execute(query, (event_id,))
            deleted_count = self.cursor.rowcount
            self.conn.commit()
            
            print(f"Delete query executed. Rows affected: {deleted_count}")
            
            if deleted_count > 0:
                print(f"Successfully deleted event {event_id}")
                return True
            else:
                print(f"No event was deleted for ID {event_id}")
                return False
            
        except Exception as e:
            print(f"Error deleting event: {e}")
            import traceback
            traceback.print_exc()
            self.conn.rollback()
            raise
    
    def get_event(self, event_id: int) -> Optional[Dict]:
        """Get a specific event by ID"""
        try:
            print(f"Fetching event with ID: {event_id}")
            query = "SELECT * FROM events WHERE id = %s;"
            self.cursor.execute(query, (event_id,))
            event = self.cursor.fetchone()
            
            if event:
                print(f"Found event: {event['title']} (ID: {event['id']})")
                return dict(event)
            else:
                print(f"No event found with ID: {event_id}")
                return None
        except Exception as e:
            print(f"Error getting event: {e}")
            raise
    
    def get_events_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Get all events within a specific time range"""
        try:
            print(f"Querying events from {start_time} to {end_time}")
            
            query = """
                SELECT * FROM events 
                WHERE 
                    (start_time BETWEEN %s AND %s) OR
                    (end_time BETWEEN %s AND %s) OR
                    (start_time <= %s AND end_time >= %s)
                ORDER BY start_time ASC;
            """
            self.cursor.execute(query, (start_time, end_time, start_time, end_time, start_time, end_time))
            
            events = self.cursor.fetchall()
            print(f"Found {len(events)} events")
            
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
        """Check for conflicting events in the specified time range"""
        try:
            print(f"Checking for conflicts between {start_time} and {end_time}")
            if exclude_event_id:
                print(f"Excluding event ID: {exclude_event_id}")
                
            # Fixed conflict detection to properly handle adjacent events
            # Events are considered conflicting if:
            # 1. New event starts before existing event ends AND new event ends after existing event starts
            # This excludes cases where one event ends exactly when another starts
            
            if exclude_event_id is not None:
                query = """
                    SELECT * FROM events 
                    WHERE 
                        (start_time < %s AND end_time > %s)
                        AND status = 'active'
                        AND id != %s
                    ORDER BY importance DESC, start_time ASC;
                """
                params = [end_time, start_time, exclude_event_id]
            else:
                query = """
                    SELECT * FROM events 
                    WHERE 
                        (start_time < %s AND end_time > %s)
                        AND status = 'active'
                    ORDER BY importance DESC, start_time ASC;
                """
                params = [end_time, start_time]
            
            self.cursor.execute(query, params)
            conflicts = self.cursor.fetchall()
            
            print(f"Found {len(conflicts)} conflicting events")
            
            # Convert to list of dictionaries
            result = []
            for conflict in conflicts:
                conflict_dict = dict(conflict)
                print(f"  - {conflict_dict['title']} at {conflict_dict['start_time']} to {conflict_dict['end_time']}")
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
    
    def close(self):
        """Close database connections"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("Database connection closed")