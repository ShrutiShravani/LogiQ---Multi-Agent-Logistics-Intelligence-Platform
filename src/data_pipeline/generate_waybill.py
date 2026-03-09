from fpdf import FPDF
from geopy.geocoders import Nominatim
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
app_id = os.getenv("APP_USER_AGENT") or "LogiQ_Senior_Project"
geolocator = Nominatim(user_agent=app_id)

def generate_professional_waybill(data):
    # 1. Convert Coordinates to Addresses
    p_addr = geolocator.reverse(f"{data['pickup_lat']}, {data['pickup_lon']}").address
    d_addr = geolocator.reverse(f"{data['dropoff_lat']}, {data['dropoff_lon']}").address

    # 2. Setup PDF
    today_date = datetime.now().strftime("%d-%m-%Y %H:%M")
    pdf = FPDF()
    pdf.add_page()

    # --- Header ---
    # Title
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 15, txt="BIG APPLE LOGISTICS", ln=False, align='L')
    
    # Generated Date (on the same line, aligned right)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 15, txt=f"Generated: {today_date}", ln=True, align='R')
    
    # Slogan (Centered)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, txt="Fast. Verified. Agentic.", ln=True, align='C')
    pdf.ln(10)
    
    # --- Shipment Info ---
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(190, 10, txt=f" WAYBILL ID: WB-2026-X99", ln=True, fill=True)
    
    # Scheduled Pickup (Now prominent)
    pdf.ln(2)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(200, 0, 0) # Professional red
    pdf.cell(0, 10, txt=f"SCHEDULED PICKUP TIME: {data['pickup_datetime']}", ln=True)
    pdf.set_text_color(0, 0, 0) # Reset to black
    pdf.ln(2)
    
    # --- Addresses (Adjusted Rect height to prevent overlap) ---
    pdf.set_draw_color(200, 200, 200)
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(10, 65, 190, 50, 'F') # Lowered and taller
    
    pdf.set_xy(15, 70)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt="PICKUP FROM:", ln=True)
    pdf.set_font("Arial", '', 9) # Smaller font to fit address
    pdf.multi_cell(180, 5, txt=p_addr)
    
    pdf.ln(2)
    pdf.set_x(15)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, txt="DELIVER TO:", ln=True)
    pdf.set_font("Arial", '', 9)
    pdf.set_x(15)
    pdf.multi_cell(180, 5, txt=d_addr)
    
    # --- Cargo Details ---
    pdf.set_xy(10, 125) # Absolute positioning to clear the boxes
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt="CARGO DESCRIPTION", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    
    pdf.set_font("Arial", '', 11)
    pdf.ln(2)
    pdf.cell(100, 10, txt=f"Item: Standard Parcel", ln=False)
    pdf.cell(100, 10, txt=f"Quantity: {data['parcel_count']} unit(s)", ln=True)
    pdf.cell(100, 10, txt=f"Total Weight: {data['weight']}", ln=True)
    
    # --- Final PDF ---
    filename = "waybill_test_1.pdf"
    pdf.output(filename)
    print(f"Generated {filename} successfully.")
    return filename

if __name__=="__main__":
    sample_data = {
        "pickup_datetime": "30-06-2026 23:59:58",
        "pickup_lon": -73.9881286621093,
        "pickup_lat": 40.7320289611816,
        "dropoff_lat": 40.7566795349121, 
        "dropoff_lon": -73.9901733398437,
        "parcel_count": 1,
        "weight": "2.0 kg"
    }
    generate_professional_waybill(sample_data)