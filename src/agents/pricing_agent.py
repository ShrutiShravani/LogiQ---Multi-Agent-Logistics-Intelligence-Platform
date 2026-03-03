def pricing_agent(pickup_time, route_details, package_info, weather):
    """
    Calculates final price using XGBoost + LLM
    """
    # STEP 1: Map to XGBoost's 11 features
    xgb_input = {
        'vendor_id': 2,  # Map courier to vendor_id
        'pickup_datetime': pickup_time,
        'dropoff_datetime': pickup_time + timedelta(minutes=route_details['eta_minutes']),
        'passenger_count': max(1, int(package_info['weight_kg'] / 5)),  # Heuristic mapping
        'pickup_longitude': 121.4737,  # From location
        'pickup_latitude': 31.2304,
        'dropoff_longitude': 121.4386,
        'dropoff_latitude': 31.2045,
        'store_and_fwd_flag': 1 if package_info['special_handling'] else 0,
        'trip_duration': route_details['eta_minutes'] * 60
    }
    
    # STEP 2: XGBoost predicts base price
    base_price = xgb_model.predict(pd.DataFrame([xgb_input]))[0]  # e.g., $45.67
    
    # STEP 3: LLM adjusts for weather
    weather_multiplier = llm_weather_adjustment(weather, package_info)
    
    final_price = base_price * weather_multiplier
    
    return {
        'base_price': round(base_price, 2),
        'final_price': round(final_price, 2),
        'weather_multiplier': weather_multiplier,
        'breakdown': {
            'distance_charge': base_price * 0.4,
            'weight_charge': base_price * 0.3,
            'special_handling_charge': base_price * 0.2 if package_info['special_handling'] else 0,
            'weather_surge': base_price * (weather_multiplier - 1)
        }
    }

    Input:

Route details (from Route Agent)

Package info (from Document Agent)

Weather (from API)
us ellm to combine etaher and prediciton and give final

pickup: "Warehouse A, Shanghai"
dropoff: "Customer B, Shanghai" 
time: "2026-03-02 17:00"  # Rush hour
weather: "Heavy rain forecast (15mm)"
package: "Refrigerated medical supplies"

# STEP 1: XGBoost base prediction
base_price = $48.50  # Based on distance + time + zone

# STEP 2: LLM reasoning
"""
- Heavy rain at rush hour: +20% (delays, risk)
- Medical supplies: +5% (priority handling)
- Historical data shows 15-25% surge in this zone during rain
→ Recommended multiplier: 1.25
"""

# STEP 3: Final price
final_price = $48.50 × 1.25 = $60.63

# STEP 4: Critic validation
"Price increase aligns with historical weather patterns in this zone. Approved."