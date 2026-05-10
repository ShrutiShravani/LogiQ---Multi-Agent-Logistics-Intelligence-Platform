import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:password@localhost:5432/logistics_db"

def run_migration():
    try:
        with psycopg.connect(DB_URI, autocommit=True) as conn:
            print("Connecting to database...")
            checkpointer = PostgresSaver(conn)
            print("Running checkpointer setup...")
            checkpointer.setup()
            print("SUCCESS: 'checkpoints' tables created!")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    run_migration()