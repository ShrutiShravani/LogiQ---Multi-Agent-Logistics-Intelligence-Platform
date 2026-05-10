from fpdf import FPDF
from geopy.geocoders import Nominatim
import os
import random
import time

# Use a unique user agent to avoid being flagged/throttled
geolocator = Nominatim(user_agent="LogiQ_Final_Senior_Audit_2026_v9")

ANCHORS = [
    {"name": "Chelsea_Hub", "lat": 40.7465, "lon": -74.0014},
    {"name": "KipsBay_Hub", "lat": 40.7394, "lon": -73.9776},
    {"name": "Newark_Hub", "lat": 40.7357, "lon": -74.1724}
]

TEST_DATES = [
    "2026-01-15", # Winter (Snow/Ice check)
    "2026-05-20", # Spring (Rain check)
    "2026-07-10", # Summer (Heat/High demand check)
    "2026-09-05", # Autumn (Storm check)
    "2026-12-24"  # Holiday (Peak pricing check)
]

def get_random_description(force_anomaly=False):
    items_db = [
        {"name": "Macbook Pro", "cat": "laptop", "low": 1.5, "high": 2.5},
        {"name": "iPhone 15 Pro", "cat": "phone", "low": 0.17, "high": 0.25},
        {"name": "Mechanical Keyboard", "cat": "electronics", "low": 0.8, "high": 1.5},
        {"name": "Industrial Router", "cat": "industrial", "low": 5.0, "high": 12.0}
    ]
    
    num_item_types = random.choice([1, 2]) 
    manifest_lines = []
    total_wt = 0
    
    for i in range(num_item_types):
        item = random.choice(items_db)
        qty = random.randint(1, 3)
        is_bad = False
        if item['cat'] in ['laptop', 'phone']:
            is_bad = True if (force_anomaly and i == 0) else (random.random() > 0.8)
        
        unit_weight = (50.0 if item['cat'] == "laptop" else 20.0) if is_bad else round(random.uniform(item['low'], item['high']), 2)
        manifest_lines.append(f"- {qty}x {item['name']}. Unit Wt: {unit_weight}kg.")
       

    return f"MANIFEST CONTENTS:\n" + "\n".join(manifest_lines) 
def generate_messy_waybill(data, filename):
    # Try multiple times if the API is being slow
    for attempt in range(3):
        try:
            # zoom=18 forces house-level detail
            p_location = geolocator.reverse(f"{data['lat_o']}, {data['lon_o']}", addressdetails=True, zoom=18)
            time.sleep(1.5) # Space out requests
            d_location = geolocator.reverse(f"{data['lat_d']}, {data['lon_d']}", addressdetails=True, zoom=18)
            
            p_addr = p_location.address
            d_addr = d_location.address
            break # Success!
        except Exception as e:
            time.sleep(2)
            p_addr, d_addr = f"ERROR_ADDR_O_{random.randint(1,99)}", f"ERROR_ADDR_D_{random.randint(1,99)}"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 15, txt="BIG APPLE LOGISTICS - FREIGHT WAYBILL", ln=True)
    
    pdf.set_fill_color(255, 255, 153)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 10, txt=f"PICKUP WINDOW: {data['pickup_time']}", ln=True, fill=True)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, txt="ORIGIN:", ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(180, 5, txt=p_addr)
    pdf.ln(4)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, txt="DESTINATION:", ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(180, 5, txt=d_addr)
    pdf.ln(8)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="ITEMIZED CARGO DESCRIPTION", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Courier", '', 10)
    pdf.multi_cell(0, 6, txt=data['description'])
    pdf.ln(10)
    
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, txt=f"Tracking ID: {data['id']}", ln=True, align='R')

    os.makedirs('data/raw', exist_ok=True)
    pdf.output(f"data/raw/{filename}")
    print(f"Generated {filename} | {data['route_type']}")

if __name__ == "__main__":
    # 1. Pick a fixed time for all neighbors to ensure they fall in the same bucket
    shared_test_date = TEST_DATES[0] 
    shared_hour = 10 # 10:00 AM

    for i in range(10):
        is_neighbor = i < 6 
        
        if is_neighbor:
            # First 3 neighbor Chelsea, Next 3 neighbor Kips Bay
            base = ANCHORS[0] if i < 3 else ANCHORS[1]
            lat_o, lon_o = base['lat'], base['lon']
            
            # Destination is ~100m away
            lat_d = lat_o + random.uniform(-0.0015, 0.0015)
            lon_d = lon_o + random.uniform(-0.0015, 0.0015)
            
            # OVERRIDE: Use shared time for all neighbors
            test_date = shared_test_date
            random_hour = shared_hour
            route_type = f"CLUSTER_{base['name']}"
        else:
            # Long hauls keep their random variety
            origin = ANCHORS[0]
            dest = ANCHORS[2]
            lat_o, lon_o = origin['lat'], origin['lon']
            lat_d, lon_d = dest['lat'], dest['lon']
            test_date = random.choice(TEST_DATES)
            random_hour = random.randint(9, 18)
            route_type = "LONG_HAUL"

        pickup_timestamp = f"{test_date} {random_hour:02d}:00:00"

        entry = {
            "id": f"LOGIQ-2026-STRESS-{120+i}",
            "lat_o": lat_o, "lon_o": lon_o,
            "lat_d": lat_d, "lon_d": lon_d,
            "pickup_time": pickup_timestamp, 
            "description": get_random_description(force_anomaly=(i == 0)),
            "route_type": route_type
        }
        
        generate_messy_waybill(entry, f"waybill_{i+1}.pdf")
        time.sleep(2.0)