import psycopg2  # Fixed spelling
import redis
import os
from dotenv import load_dotenv

load_dotenv()

def test_all():
    results = {}

    # --- Test PostgreSQL ---
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            # Fixed: Convert port to int
            port=int(os.getenv('POSTGRES_PORT', 5432)), 
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            connect_timeout=8
        )
        conn.close()
        results["POSTGRES"] = "PASS"
    except Exception as e:
        results["POSTGRES"] = f"FAILED: {e}" # Log the actual error!
    
    # --- Test Redis ---
    try:
        r = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            # Added a default 0 if REDIS_DB is missing
            db=int(os.getenv('REDIS_DB', 0)),socket_connect_timeout=2 
        )
        r.ping()
        results["REDIS"] = "PASS"
    except Exception as e:
        results["REDIS"] = f"FAILED: {e}" # Log the actual error!

    # --- Final Report ---
    print("\n" + "="*50)
    print(f"{'SERVICE':<15} {'STATUS'}")
    print("-" * 50)
    for service, status in results.items():
        print(f"{service:15} {status}")
    print("="*50)

if __name__ == "__main__":
    test_all()