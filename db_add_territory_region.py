"""
Script to add territory and region columns to the requests table
Run this after updating the models.py file
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not set in .env file")
    exit(1)

engine = create_engine(DATABASE_URL)

def add_columns():
    with engine.connect() as conn:
        # Check if columns exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'requests' 
            AND column_name IN ('territory', 'region')
        """))
        existing_columns = [row[0] for row in result]
        
        print(f"Existing columns in requests table: {existing_columns}")
        
        # Add territory column if it doesn't exist
        if 'territory' not in existing_columns:
            print("Adding 'territory' column...")
            conn.execute(text("ALTER TABLE requests ADD COLUMN territory VARCHAR(255)"))
            conn.commit()
            print("[OK] Added territory column")
        else:
            print("[OK] Territory column already exists")
        
        # Add region column if it doesn't exist
        if 'region' not in existing_columns:
            print("Adding 'region' column...")
            conn.execute(text("ALTER TABLE requests ADD COLUMN region VARCHAR(255)"))
            conn.commit()
            print("[OK] Added region column")
        else:
            print("[OK] Region column already exists")
        
        print("\nDatabase migration complete!")

if __name__ == "__main__":
    add_columns()
