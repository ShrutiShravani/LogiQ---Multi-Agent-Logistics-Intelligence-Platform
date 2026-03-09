import redis
import json

class Logisticscache:
    def __init__(self):
        self.client= redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
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

    def get_weather(self, lat, lon, date_str):
        # Round to 2 decimals (~1.1km) for weather grid
        key = f"weather:{round(lat,2)}:{round(lon,2)}:{date_str}"
        data  =self.client.get(key)
        if data:
            self.hits+=1
            return data
        self.misses+=1
        return None

    def set_weather(self, lat, lon, date_str,label):
        key = f"weather:{round(lat,2)}:{round(lon,2)}:{date_str}"
        # Cache weather for 1 hour
        self.client.setex(key, 3600, json.dumps(label))
   
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


