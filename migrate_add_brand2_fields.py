"""
Migration script to add brand2, objective2, expected_outcome2, priority2, and notes2 columns
to the requests table and related columns to doctor_interactions table.
"""
import pymysql
import os
import re
from dotenv import load_dotenv

load_dotenv()

def parse_database_url(url):
    """Parse DATABASE_URL and return connection parameters."""
    # Format: mysql+pymysql://user:password@host:port/database
    pattern = r'mysql\+pymysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
    match = re.match(pattern, url)
    if match:
        return {
            'user': match.group(1),
            'password': match.group(2),
            'host': match.group(3),
            'port': int(match.group(4)),
            'database': match.group(5)
        }
    return None

def migrate():
    # Get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("Error: DATABASE_URL not found in environment variables")
        return
    
    # Parse the DATABASE_URL
    db_config = parse_database_url(database_url)
    
    if not db_config:
        print("Error: Could not parse DATABASE_URL")
        return
    
    print(f"Connecting to database at {db_config['host']}:{db_config['port']}")
    
    # Connect to the database
    connection = pymysql.connect(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
        charset='utf8mb4',
        ssl={'ssl': {'ssl-mode': 'REQUIRED'}}  # Aiven requires SSL
    )
    
    try:
        # Migrate requests table
        with connection.cursor() as cursor:
            # Check if columns exist
            cursor.execute("SHOW COLUMNS FROM requests LIKE 'brand2'")
            result = cursor.fetchone()
            
            if result:
                print("Column 'brand2' already exists in requests table. Skipping.")
            else:
                print("Adding missing columns to requests table...")
                
                # Add brand2 column
                cursor.execute("""
                    ALTER TABLE requests 
                    ADD COLUMN brand2 VARCHAR(255) NULL AFTER notes
                """)
                print("Added column: brand2")
                
                # Add objective2 column
                cursor.execute("""
                    ALTER TABLE requests 
                    ADD COLUMN objective2 TEXT NULL AFTER brand2
                """)
                print("Added column: objective2")
                
                # Add expected_outcome2 column
                cursor.execute("""
                    ALTER TABLE requests 
                    ADD COLUMN expected_outcome2 TEXT NULL AFTER objective2
                """)
                print("Added column: expected_outcome2")
                
                # Add priority2 column
                cursor.execute("""
                    ALTER TABLE requests 
                    ADD COLUMN priority2 VARCHAR(50) NULL AFTER expected_outcome2
                """)
                print("Added column: priority2")
                
                # Add notes2 column
                cursor.execute("""
                    ALTER TABLE requests 
                    ADD COLUMN notes2 TEXT NULL AFTER priority2
                """)
                print("Added column: notes2")
                
                connection.commit()
                print("\nRequests table migration completed successfully!")
                
        # Migrate doctor_interactions table
        with connection.cursor() as cursor:
            print("\nChecking doctor_interactions table...")
            
            cursor.execute("SHOW COLUMNS FROM doctor_interactions LIKE 'brand2_discussed'")
            result = cursor.fetchone()
            
            if not result:
                print("Adding missing columns to doctor_interactions table...")
                
                cursor.execute("""
                    ALTER TABLE doctor_interactions 
                    ADD COLUMN brand2_discussed VARCHAR(255) NULL AFTER brand_discussed
                """)
                print("Added column: brand2_discussed")
                
                cursor.execute("""
                    ALTER TABLE doctor_interactions 
                    ADD COLUMN brand2_interest_level VARCHAR(100) NULL AFTER interest_level
                """)
                print("Added column: brand2_interest_level")
                
                cursor.execute("""
                    ALTER TABLE doctor_interactions 
                    ADD COLUMN brand2_topics TEXT NULL AFTER topics_discussed
                """)
                print("Added column: brand2_topics")
                
                cursor.execute("""
                    ALTER TABLE doctor_interactions 
                    ADD COLUMN brand2_summary TEXT NULL AFTER summary
                """)
                print("Added column: brand2_summary")
                
                cursor.execute("""
                    ALTER TABLE doctor_interactions 
                    ADD COLUMN brand2_outcomes VARCHAR(255) NULL AFTER outcomes
                """)
                print("Added column: brand2_outcomes")
                
                connection.commit()
                print("\nDoctor interactions migration completed successfully!")
            else:
                print("Columns already exist in doctor_interactions table. Skipping.")
                
    except Exception as e:
        print(f"Error during migration: {e}")
        connection.rollback()
        raise
    finally:
        connection.close()

if __name__ == "__main__":
    migrate()
