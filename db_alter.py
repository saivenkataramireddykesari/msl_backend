from database import engine
from sqlalchemy import text

def run_migration():
    with engine.begin() as conn:
        try:
            # First create territories and regions sequence / table directly or via SQLAlchemy metadata
            # We already have them in models.py and they will be auto-created by app startup,
            # but just in case, we'll try to alter doctors.
            print("Running ALTER TABLE on doctors...")
            conn.execute(text("ALTER TABLE doctors ADD COLUMN territory_id INTEGER REFERENCES territories(id)"))
            conn.execute(text("ALTER TABLE doctors ADD COLUMN region_id INTEGER REFERENCES regions(id)"))
            print("Successfully added columns!")
        except Exception as e:
            print(f"Error (maybe columns already exist or tables not created): {e}")

if __name__ == "__main__":
    run_migration()
