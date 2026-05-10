import redis
import json
import os
from dotenv import load_dotenv
import pygeohash as gh

load_dotenv()

class Logisticscache:
    def __init__(self):
        host = os.getenv("REDIS_HOST", "localhost")
        
        # 2. Look for 'REDIS_PORT', default to 6379
        port = int(os.getenv("REDIS_PORT", 6379))
        self.client= redis.Redis(host=host, port=port, db=0, decode_responses=True)
        self.hits = 0
        self.misses = 0

    def get_geo(self,address):
        safe_key= f"geo:{address.lower().strip().replace(' ', '_')}"
        data= self.client.get(safe_key)
        if data:
            self.hits+=1
            return json.loads(data)
        self.misses+=1
        return  None

    def set_geo(self,address,coords):
        safe_key = f"geo:{address.lower().strip().replace(' ', '_')}"
        # Cache routes for 24 hours
        self.client.setex(safe_key, 86400, json.dumps(coords))

    def get_weather(self,geo_key, date_str):
        # Round to 2 decimals (~1.1km) for weather grid
        key = f"weather:{geo_key}:{date_str}"
        data  =self.client.get(key)
        if data:
            self.hits+=1
            return json.loads(data)
        self.misses+=1
        return None

    def set_weather(self, geo_key, date_str,label):
        key = f"weather:{geo_key}:{date_str}"
        print(key)
        # Cache weather for 1 hour
        self.client.setex(key, 3600, json.dumps(label))


    # In src/utils/cache.py
    def get_route_opt(self, fingerprint):
        # Retrieve from Redis/File/Memory using the hash
        return self.client.get(f"opt:{fingerprint}") 

    def set_route_opt(self, fingerprint, data):
        # Store the result so you don't pay for it again
        self.client.set(f"opt:{fingerprint}", data, ex=86400) # 24hr expiry

    def get_geohash(self,lat,lon,precision=5):
        return gh.encode(lat,lon,precision=precision)
   
    def print_stats(self):
        total = self.hits + self.misses
        print("\n" + "="*40)
        print(f"LOGISTICS CACHE STATS")
        print(f"Total Requests: {total}")
        print(f"Hits (Saved API): {self.hits}")
        print(f"Misses (New API): {self.misses}")
        if total > 0:
            print(f"Efficiency: {(self.hits/total)*100:.1f}%")
        print("="*40 + "\n")


