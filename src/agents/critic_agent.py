import numpy as np
import json
import pickle

class CriticAgent:
    def __init__(self, feature_engineer_path, traffic_lookup_path):
        # Load the saved Logic (Formulas)
        with open(feature_engineer_path, 'rb') as f:
            self.engineer = pickle.load(f)
        
        # Load the saved Memory (Historical Averages)
        with open(traffic_lookup_path, 'r') as f:
            self.traffic_memory = json.load(f)

    def verify_logistics(self, pickup_coords, dropoff_coords, ai_duration_min, ai_price, hour, day_of_week, vehicle_type):
        # 1. Physical Verification (Formula-based)
        calc_dist = self.engineer.haversine_distance(
            pickup_coords[0], pickup_coords[1], 
            dropoff_coords[0], dropoff_coords[1]
        )
        
        # 2. Market Context Verification (JSON-based)
        # We check the 'Expected' density from our memory
        mem_key = f"{day_of_week}_{hour}"
        context = self.traffic_memory.get(mem_key, {'actual_speed_kmh': 25.0, 'traffic_density_score': 1.0})
        
        hist_speed = context['actual_speed_kmh']
        hist_density = context['traffic_density_score']

        #verify acual distnace calculated by route agent
        speed = calc_dist / (max(ai_duration_min,1)/ 60)
        # If AI speed is 2x faster than history, the ETA is a lie.
        if speed > (hist_speed * 2.0):
            return False, f"ETA REJECTED: Speed {speed:.1f} is impossible for this hour."
        
        # 3. Apply the 'Senior Formula'
        # We use the formula to see what the price SHOULD be based on history
        is_rush = 1 if (hour in [8, 9, 10, 16, 17, 18, 19] and day_of_week < 5) else 0
        is_weekend = 1 if day_of_week >= 5 else 0
        
        # Rates from your Feature Engineer
        vehicle_base = {'e-scooter': 2.0, 'bicycle': 3.0, 'van': 15.0, 'truck': 45.0}
        vehicle_km_rate = {'e-scooter': 0.5, 'bicycle': 1.0, 'van': 2.5, 'truck': 5.0}
        
        base = vehicle_base.get(vehicle_type, 15.0)
        rate = vehicle_km_rate.get(vehicle_type, 2.5)
        
        surge = 1.0 + (is_rush * 0.3) + (is_weekend * 0.15)
        
        # This is where the JSON Memory protects the system:
        congestion = 1.2 if hist_density < 0.5 else 1.0
        
        # Calculate the "Truth Price"
        expected_price = (base + (calc_dist * rate) + (ai_duration_min * 0.2)) * surge * congestion
        
        # 4. The Decision Logic
        # Allow the AI to vary by 15% (for weather or dynamic demand)
        # If it varies more, the Critic REJECTS.
        price_error = abs(ai_price - expected_price) / expected_price
        
        if price_error > 0.15:
            return False, f"REJECTED: Price hallucination detected. Expected ~{expected_price:.2f}, got {ai_price}."
        
        return True, "VERIFIED: Price aligns with physics and historical traffic memory."