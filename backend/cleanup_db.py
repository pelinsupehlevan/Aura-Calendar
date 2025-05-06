import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def cleanup_database():
    """Script to clean up database tables for a fresh start"""
    print("Starting database cleanup...")
    
    # Database connection parameters
    db_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "dbname": os.getenv("DB_NAME", "aura_calendar")
    }
    
    conn = None
    try:
        # Connect to the database
        print(f"Connecting to database {db_params['dbname']}...")
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Drop tables in reverse order of dependencies
        print("Dropping existing tables if they exist...")
        
        # First, drop tables with foreign key dependencies
        cursor.execute("DROP TABLE IF EXISTS conversation_history;")
        print("- Dropped conversation_history table")
        
        cursor.execute("DROP TABLE IF EXISTS memory;")
        print("- Dropped memory table")
        
        # Then drop the main tables
        cursor.execute("DROP TABLE IF EXISTS events;")
        print("- Dropped events table")
        
        print("\nDatabase cleanup completed successfully!")
        print("You can now run main.py to recreate the tables")
        
    except Exception as e:
        print(f"Error during database cleanup: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    cleanup_database()