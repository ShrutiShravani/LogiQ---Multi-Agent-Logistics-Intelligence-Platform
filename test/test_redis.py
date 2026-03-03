import redis
import time
import os
from dotenv import load_dotenv


load_dotenv()
def test_connection():
    try:
        r=redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT', 6379))
            
        )
        r.ping()
        r.set('test_key','test_value')
        r.delete('test_key')
        print("Redis connection successful")
        return True
    
    except Exception as e:
        print(f"Redis connection failed:{e}")
        return False

if __name__=="__main__":
    for i in range(5):
        if test_connection():
            break
        print(f"retry {i+1}/5..")
        time.sleep(2)
    