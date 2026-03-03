import psycopg2
import time
import os 
from dotenv import load_dotenv

load_dotenv()
def test_connection():
    try:
        conn= psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            # Fixed: Convert port to int
            port=int(os.getenv('POSTGRES_PORT', 5432)), 
            database=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD')
        )
    
        curr= conn.cursor()
        curr.execute("SELECT 1")
        result= curr.fetchone()
        curr.close()
        conn.close()
        print("Postgressql cnnection successful")
        return True
    except Exception as e:
        print(f"Error connecting to Postgressql: {e}")
        return False
    
if __name__=="__main__":
    for i in range(5):
        if test_connection():
            break
        print(f"Retry{i+1}/5..")
        time.sleep(2)