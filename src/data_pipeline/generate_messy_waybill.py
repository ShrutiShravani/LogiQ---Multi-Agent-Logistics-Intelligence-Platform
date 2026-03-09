from fpdf import FPDF
from geopy.geocoders import Nominatim
import os
from datetime import datetime

# Initialize geolocator
geolocator = Nominatim(user_agent="LogiQ_Senior_Project")

def generate_messy_waybill(data, filename):
    # 1. Reverse Geocode (The Realism Layer)
    p_addr = geolocator.reverse(f"{data['lat_o']}, {data['lon_o']}").address
    d_addr = geolocator.reverse(f"{data['lat_d']}, {data['lon_d']}").address

    pdf = FPDF()
    pdf.add_page()

    # --- Header ---
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 15, txt="BIG APPLE LOGISTICS - INTERNAL", ln=True)
    
    # Noise: Adding a "Generated" date that the LLM should IGNORE
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, txt=f"Invoice Generated: 01-01-2025 (Ref Only)", ln=True)
    pdf.ln(5)

    # --- Prominent Scheduled Time (The one the LLM MUST find) ---
    pdf.set_fill_color(255, 255, 153) # Highlight
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, txt=f"SCHEDULED PICKUP: {data['pickup_time']}", ln=True, fill=True)
    pdf.ln(5)

    # --- Addresses ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, txt="ORIGIN:", ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(180, 5, txt=p_addr)
    pdf.ln(3)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 5, txt="DESTINATION:", ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(180, 5, txt=d_addr)
    pdf.ln(5)

    # --- The "Messy" Cargo Section ---
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="CARGO MANIFEST / DESCRIPTION", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)
    
    pdf.set_font("Arial", '', 11)
    # This is where the LLM has to sum weights
    pdf.multi_cell(0, 7, txt=data['description'])
    pdf.ln(5)
    
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(0, 10, txt=f"Tracking ID: {data['id']}", ln=True, align='R')

    os.makedirs('data/raw', exist_ok=True)
    output_path = f"data/raw/{filename}"
    pdf.output(output_path)
    print(f"Produced: {output_path}")

if __name__ == "__main__":
    # Using the 5 specific coordinate pairs you provided
    test_data = [
        {
            "id": "WB-001",
            "lat_o": 40.74155, "lon_o": -73.9783, 
            "lat_d": 40.717, "lon_d": -73.9521,
            "pickup_time": "2025-01-10 09:30:00",
            "description": "Quantity: 1 unit. Small electronic component. Weight: 2.5kg. Fragile."
        },
        {
            "id": "WB-005",
            "lat_o": 40.67843, "lon_o": -73.9685,
            "lat_d": 40.63571, "lon_d": -73.9666,
            "pickup_time": "2025-08-16 08:00:00",
            "description": "Bulk delivery. 4 parcels. Itemized weights: 5kg, 5kg, 4kg, 4kg. Combined mass: 18kg."
        }
    ]

    for i, entry in enumerate(test_data):
        generate_messy_waybill(entry, f"waybill_stress_test_{i+1}.pdf")