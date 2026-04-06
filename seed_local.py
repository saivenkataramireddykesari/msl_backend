import os
import sys

# Add current path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from main import seed_doctors

def run():
    db = SessionLocal()
    try:
        result = seed_doctors(db)
        print("Seed result:", result)
    except Exception as e:
        print("Error during seeding:", e)
    finally:
        db.close()

if __name__ == "__main__":
    run()
