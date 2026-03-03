def supervisor_process(user_query):
    """
    User_query = {
        'pickup': 'Warehouse A, Shanghai',
        'dropoff': 'Customer B, Shanghai',
        'pickup_time': '2026-03-02 14:00',
        'documents': ['waybill.pdf']
    }
    """
    
    # Step 1: Process document
    package_info = document_agent(user_query['documents'][0])
    
    # Step 2: Get weather
    weather = weather_api.get_forecast(
        location=user_query['dropoff'],
        time=user_query['pickup_time']
    )
    
    # Step 3: Get traffic
    traffic = traffic_api.get_conditions(
        route=(user_query['pickup'], user_query['dropoff'])
    )
    
    # Step 4: Plan route
    route = route_optimizer(
        pickup=user_query['pickup'],
        dropoff=user_query['dropoff'],
        package_info=package_info,
        weather=weather,
        traffic=traffic
    )
    
    # Step 5: Calculate price
    price = pricing_agent(
        pickup_time=user_query['pickup_time'],
        route_details=route,
        package_info=package_info,
        weather=weather
    )
    
    # Step 6: Validate everything
    validation = critic_agent(
        pickup=user_query['pickup'],
        dropoff=user_query['dropoff'],
        package_info=package_info,
        route=route,
        price=price,
        weather=weather
    )
    
    return {
        'route': route,
        'price': price,
        'validation': validation,
        'package_summary': package_info
    }
    \
    GEOCODING converts addresses → coordinates