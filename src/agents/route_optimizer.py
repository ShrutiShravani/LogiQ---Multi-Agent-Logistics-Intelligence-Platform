def route_optimizer(pickup, dropoff, package_info, weather, traffic):
    """
    Plans optimal delivery route
    """
    route_details = {
        'distance_km': 25.3,           # ← THIS goes to XGBoost
        'eta_minutes': 45,               # ← THIS goes to XGBoost
        'num_stops': 2,                   # ← THIS goes to XGBoost
        'route_polyline': [...],
        'vehicle_type': 'refrigerated' if 'refrigerated' in package_info['special_handling'] else 'standard'
    }
    
    return route_details

    Input:

Pickup location (from user)

Dropoff location (from user)

Package info (from Document Agent)

Weather (from API)

Traffic (from API)