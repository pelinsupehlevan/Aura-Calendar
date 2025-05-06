import os
import psycopg2
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

def initialize_database():
    """Script to initialize the database for Aura Calendar"""
    print("Starting database initialization...")
    
    # Database connection parameters
    db_params = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "")
    }
    
    db_name = os.getenv("DB_NAME", "aura_calendar")
    
    # Connect to PostgreSQL server to create the database if it doesn't exist
    conn = None
    try:
        # First connect to 'postgres' database to be able to create a new database
        print(f"Connecting to PostgreSQL server on {db_params['host']}:{db_params['port']}...")
        conn = psycopg2.connect(
            host=db_params["host"],
            port=db_params["port"],
            user=db_params["user"],
            password=db_params["password"],
            dbname="postgres"  # Connect to default database first
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
        exists = cursor.fetchone()
        
        if not exists:
            print(f"Creating database '{db_name}'...")
            cursor.execute(f"CREATE DATABASE {db_name}")
            print(f"Database '{db_name}' created successfully")
        else:
            print(f"Database '{db_name}' already exists")
            
        cursor.close()
        conn.close()
        
        # Now connect to the created/existing database to check pgvector
        print(f"Connecting to '{db_name}' database...")
        conn = psycopg2.connect(
            host=db_params["host"],
            port=db_params["port"],
            user=db_params["user"],
            password=db_params["password"],
            dbname=db_name
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if pgvector extension is installed
        cursor.execute("SELECT * FROM pg_available_extensions WHERE name = 'vector'")
        pgvector_available = cursor.fetchone()
        
        if not pgvector_available:
            print("WARNING: pgvector extension is not available on this PostgreSQL server")
            print("You need to install pgvector extension before running the application")
            print("Visit: https://github.com/pgvector/pgvector for installation instructions")
        else:
            # Try to create the extension
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                print("pgvector extension installed successfully in the database")
            except Exception as e:
                print(f"Error installing pgvector extension: {e}")
                print("You may need administrator privileges to install extensions")
        
        print("\nDatabase initialization completed!")
        print(f"You can now run the application with: python main.py")
        
    except Exception as e:
        print(f"Error during database initialization: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    initialize_database()