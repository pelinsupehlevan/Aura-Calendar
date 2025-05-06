import os
import sys
import psycopg2
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

def setup_database():
    """
    All-in-one setup script for Aura Calendar:
    1. Checks and creates database if needed
    2. Installs pgvector extension if needed
    3. Drops existing tables to avoid conflicts
    4. Creates tables in the correct order
    """
    print("====== Aura Calendar Setup ======")
    print("Starting comprehensive database setup...")
    
    # Database connection parameters
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "aura_calendar")
    
    # Step 1: Connect to PostgreSQL server (postgres database) to create our database
    conn = None
    try:
        print(f"\n1. Connecting to PostgreSQL server on {db_host}:{db_port}...")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            dbname="postgres"  # Connect to default database first
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if our database exists
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Creating database '{db_name}'...")
            cursor.execute(f"CREATE DATABASE {db_name}")
            print(f"✓ Database '{db_name}' created successfully")
        else:
            print(f"✓ Database '{db_name}' already exists")
            
        cursor.close()
        conn.close()
        
        print("\n2. Setting up database schema...")
        
        # Step 2: Connect to our application database
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            dbname=db_name
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Step 3: Check and install pgvector extension
        print("Checking pgvector extension...")
        cursor.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
        pgvector_available = cursor.fetchone()
        
        if not pgvector_available:
            print("❌ ERROR: pgvector extension is not available on this PostgreSQL server")
            print("You need to install the pgvector extension before proceeding.")
            print("Visit: https://github.com/pgvector/pgvector for installation instructions")
            return False
        
        # Try to create the extension
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            print("✓ pgvector extension installed successfully")
        except Exception as e:
            print(f"❌ Error installing pgvector extension: {e}")
            print("You may need administrator privileges to install extensions")
            return False
        
        # Step 4: Drop existing tables to start fresh
        print("\n3. Cleaning up existing tables...")
        
        # Drop tables in the correct order (reverse dependency order)
        cursor.execute("DROP TABLE IF EXISTS conversation_history CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS memory CASCADE;")
        cursor.execute("DROP TABLE IF EXISTS events CASCADE;")
        print("✓ All existing tables dropped successfully")
        
        # Step 5: Create tables in the correct order
        print("\n4. Creating database tables...")
        
        # Create events table first
        print("Creating events table...")
        cursor.execute("""
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
        print("✓ Events table created successfully")
        
        # Create memory table with vector support
        print("Creating memory table...")
        cursor.execute("""
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
        print("✓ Memory table created successfully")
        
        # Create conversation history table
        print("Creating conversation_history table...")
        cursor.execute("""
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
        print("✓ Conversation history table created successfully")
        
        print("\n✅ Database setup completed successfully!")
        print("You can now run 'python main.py' to start the application")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during setup: {e}")
        return False
    finally:
        if conn:
            conn.close()

def check_environment():
    """Check if all required environment variables are set"""
    print("\nChecking environment variables...")
    required_vars = [
        ("DB_PASSWORD", os.getenv("DB_PASSWORD")),
        ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    ]
    
    missing = [name for name, value in required_vars if not value]
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease add these to your .env file")
        return False
    
    print("✓ All required environment variables are set")
    return True

if __name__ == "__main__":
    # Check environment variables first
    if not check_environment():
        sys.exit(1)
    
    # Set up the database
    if setup_database():
        print("\n🎉 Setup completed successfully! Your Aura Calendar is ready.")
        print("Run 'python main.py' to start the application")
    else:
        print("\n❌ Setup failed. Please fix the errors and try again.")
        sys.exit(1)