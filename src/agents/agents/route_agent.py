from sklearn.metrics.pairwise import haversine_distances
from src.models.data_models import ShipmentModel
from src.agents.agents.base_agent import BaseAgent
import requests
import os
from dotenv import load_dotenv
import re
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError
import math
import time
from src.utils.cache import Logisticscache
import functools
from typing import List
from src.agents.agents.temporal_batcher import SpatialTemporalBatcher
import time
import hashlib
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import json

load_dotenv()

def safe_api_call(retries=3, delay=1.5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "timeout" in str(e).lower():
                        print(f"Rate limit/Timeout. Retry {attempt+1} in {delay}s...")
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise e
            return None
        return wrapper
    return decorator

class RouteAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="RouteAgent")
        self.geolocator = Nominatim(user_agent=os.getenv("APP_USER_AGENT"))
        self.mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
        self.weather_key = os.getenv("VISUAL_CROSSING_KEY")
        self.cache = Logisticscache()
        self.batcher = SpatialTemporalBatcher()
    

    def generate_group_fingerprint(self,shipment_group:List[ShipmentModel])-> str:
        """Creates a unique hash for this specific set of waybills."""

        combined_ids= "-".join(sorted([str(s.shipment_id) for s in shipment_group]))
        return hashlib.sha256(combined_ids.encode()).hexdigest()

    def local_nearest_neighbourhood(self, shipment_group: List[ShipmentModel]) -> List[int]:
        n = len(shipment_group)
        # 1. Logic: Visit all pickups in order, then all deliveries in order.
        # This is the simplest "Safe" route that is never zero.
        order = list(range(2 * n)) 
        
        # 2. Calculate the actual distance of this sequence
        total_dist = 0.0
        
        # Build a temporary list of all lat/lon points (P1, P2, P3, D1, D2, D3)
        nodes = []
        for s in shipment_group:
            nodes.append((s.pickup_latitude, s.pickup_longitude))
        for s in shipment_group:
            nodes.append((s.dropoff_latitude, s.dropoff_longitude))
            
        # Calculate distance from point to point in the 'order'
        for i in range(len(order) - 1):
            curr_node = nodes[order[i]]
            next_node = nodes[order[i+1]]
            print(curr_node,next_node)
            total_dist += self.haversine_distance(
                curr_node[0], curr_node[1], 
                next_node[0], next_node[1]
            )
        
        print(f"Fallback Route Distance: {total_dist} km")
        print(order)
        return order

    @safe_api_call(retries=3, delay=2)
    def _get_coords(self, address: str):
        clean_address = re.sub(r'\(.*?\)', '', address)
        segments = clean_address.split(',')
        clean_address2 = ", ".join(segments[:4]).strip()
        
        cached_coords = self.cache.get_geo(clean_address2)
        if cached_coords:
            print(f"coords are cached already{cached_coords}")
            return float(cached_coords[0]), float(cached_coords[1])

        for attempt in range(3):
            try:
                time.sleep(1.1)
                location = self.geolocator.geocode(
                    clean_address2, 
                    viewbox=[(40.47, -74.25), (40.91, -73.70)], 
                    bounded=True,
                    timeout=20
                )
                if location:
                    self.cache.set_geo(clean_address2, [location.latitude, location.longitude])
                    return float(location.latitude), float(location.longitude)
                
                
                if len(segments)>2:
                    clean_address2 = ", ".join(segments[1:4])
                    location_fallback= self.geolocator.geocode(
                    clean_address2, 
                    viewbox=[(40.47, -74.25), (40.91, -73.70)], 
                    bounded=True,
                    timeout=20
                )
                if location_fallback:
                    self.cache.set_geo(clean_address2, [location_fallback.latitude, location_fallback.longitude])
                    return float(location_fallback.latitude), float(location_fallback.longitude)

                if len(segments)>=2:
                    clean_address2 = ", ".join(segments[-2])
                    location_fallback= self.geolocator.geocode(
                    clean_address2, 
                    viewbox=[(40.47, -74.25), (40.91, -73.70)], 
                    bounded=True,
                    timeout=20
                )
                if location_fallback:
                    self.cache.set_geo(clean_address2, [location_fallback.latitude, location_fallback.longitude])
                    return float(location_fallback.latitude), float(location_fallback.longitude)

            except Exception as e:
                print(f"Attempt {attempt+1} failed: {str(e)}")
                time.sleep(1.5)
        return None, None

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    @safe_api_call(retries=3, delay=2)
    def get_weather_impact(self, lat, lon, date_str):
        WEATHER_RULES = {
            "snow": (0.30, "Snow"),
            "rain": (0.15, "Rain"),
            "thunder": (0.45, "Storm"),
            "fog": (0.10, "Fog"),
            "cloudy": (0.05, "Overcast")
        }
        try:
            lat = round(lat, 2)
            lon = round(lon, 2)
            geo_key = self.cache.get_geohash(lat, lon) 
            print(f"geo_key:{geo_key}")
            condition = self.cache.get_weather(geo_key, date_str)
            if condition:
                print(f"DEBUG: Cache HIT. Condition: {condition}")
            else:
                print("DEBUG: Cache MISS. Calling Visual Crossing API...")
                api_key = self.weather_key
    
               
                url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat},{lon}/{date_str}?key={api_key}&unitGroup=metric&include=days&elements=datetime,temp,icon"
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    print("api not working")
                    return 0.0, "Clear"
                data = response.json()
                print(f"weather_Data:{data}")
                if "days" in data and len(data["days"]) > 0:
                    condition = data["days"][0].get("icon", "clear-day")
                    geo_key = self.cache.get_geohash(lat, lon)
                    print(f"geo_key:{geo_key}")
                    self.cache.set_weather(geo_key,date_str,label=condition)
                    print("weather cached saved")
                else: return 0.0, "Clear"

            for key, (penalty, label) in WEATHER_RULES.items():
                if key in condition.lower(): return penalty, label
            return 0.0, "Clear"
        except Exception as e:
            print(f"CRITICAL WEATHER ERROR: {str(e)}")
            return 0.0, "Clear"

    @safe_api_call(retries=3, delay=2)
    def get_mapbox_route(self, url):
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Mapbox_Error_{response.status_code}")
        return response.json()

    def get_mapbox_optimized_data(self, shipment_group: List[ShipmentModel]):

        #check fingerprint cache
        fingerprint= str(self.generate_group_fingerprint(shipment_group))
 
        cached_result= self.cache.get_route_opt(fingerprint)
        if cached_result:
            try:
                # If you saved it as a JSON string, you must decode it here
                cached_result = json.loads(cached_result)
                
                print(f"Cache Hit: Optimization fingerprint {fingerprint[:8]} retrieved.")
                return cached_result['order'], cached_result['dist']
                
            except Exception as e:
                print(f"Cache Parse Error: {e}. Proceeding to fresh calculation.")
                # If the cache is corrupted or in a weird format, just ignore it and re-calculate
        
        n = len(shipment_group)
        all_coords = []
        for s in shipment_group:
            all_coords.append(f"{s.pickup_longitude},{s.pickup_latitude}")
        for s in shipment_group:
            all_coords.append(f"{s.dropoff_longitude},{s.dropoff_latitude}")
        
        coords_str = ";".join(all_coords)

        # 3. Get Distance Matrix from Mapbox (The Engine)
        matrix_url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/driving/{coords_str}?annotations=distance&access_token={self.mapbox_token}"
        
        try:
            response = requests.get(matrix_url, timeout=5)
            matrix_data = response.json()
            
            if matrix_data.get("code") != "Ok":
                raise Exception(f"Mapbox Matrix Error: {matrix_data.get('code')}")
            
            if "distances" in matrix_data:
                matrix = matrix_data["distances"]
            elif "durations" in matrix_data:
                print("Using durations matrix for optimization.")
                matrix = matrix_data["durations"]
            else:
                print(f"CRITICAL: Mapbox response missing both. Full Response: {matrix_data}")
                raise KeyError("No valid matrix data found.")

            # Mapbox returns distances in meters
            distance_matrix = matrix

            # 4. Initialize OR-Tools Routing
            # Nodes: 2 * n (all pickups and all dropoffs)
            manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)
            routing = pywrapcp.RoutingModel(manager)

            def distance_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                return int(distance_matrix[from_node][to_node]*1000)

            transit_callback_index = routing.RegisterTransitCallback(distance_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

            dimension_name = 'Distance'
            routing.AddDimension(
            transit_callback_index,
            0,      # no slack
            100000000, # maximum distance per vehicle (1000km)
            True,   # start cumul to zero
            dimension_name)
            distance_dimension = routing.GetDimensionOrDie(dimension_name)

            # 5. Add THE BOTTLENECK FIX: Pickup and Delivery Constraints
            for i in range(n):
                pickup_node = i
                delivery_node = i + n
                pickup_idx = manager.NodeToIndex(pickup_node)
                delivery_idx = manager.NodeToIndex(delivery_node)
                
                routing.AddPickupAndDelivery(pickup_idx, delivery_idx)
                
                # This line ensures the delivery happens AFTER the pickup in the sequence
                routing.solver().Add(
                    distance_dimension.CumulVar(pickup_idx) <=
                    distance_dimension.CumulVar(delivery_idx)
                )

            # 6. Solve
            search_parameters = pywrapcp.DefaultRoutingSearchParameters()
            search_parameters.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
            )

            solution = routing.SolveWithParameters(search_parameters)

            if solution:
                # Extract the optimized order
                order = []
                index = routing.Start(0)
                total_dist_meters = 0
                while not routing.IsEnd(index):
                    order.append(manager.IndexToNode(index))
                    previous_index = index
                    index = solution.Value(routing.NextVar(index))
                    total_dist_meters += routing.GetArcCostForVehicle(previous_index, index, 0)
                
                total_dist = round(total_dist_meters/1000,2)
                total_dist_km=total_dist/1000
                print(f"total_Dist_km:{total_dist_km}")
                
                # Cache and Return
                self.cache.set_route_opt(fingerprint, json.dumps({"order": order, "dist": total_dist_km}))
                return order, total_dist_km

    
        except Exception as e:
            print(f"Optimization Error: {e}")
            #fallback to neighbour distance in case api fails
            order ,total_dist= self.local_nearest_neighbourhood(shipment_group)
            # Calculate approximate distance for the fallback order
            
            
            return order, round(total_dist, 2)

    def process_batch(self, shipments: List[ShipmentModel]) -> List[ShipmentModel]:
        start_time=time.time()
        for shipment in shipments:
            if not (shipment.pickup_latitude and shipment.pickup_longitude):
                lat, lon = self._get_coords(shipment.origin_address)
                d_lat, d_lon = self._get_coords(shipment.destination_address)
                shipment.pickup_latitude, shipment.pickup_longitude = lat, lon
                shipment.dropoff_latitude, shipment.dropoff_longitude = d_lat, d_lon

        clusters = self.batcher.group_shipments(shipments)
    
        final_list = []

        route_stops = []
    

        for cluster_index,group in enumerate(clusters):
            current_cluster_id=f"Cluster_{cluster_index}" if len(group)>= 2 else "SINGLETON"
            print(f"clusters_length:{len(group)}")
            if len(group) >= 2:
                print("length is greater than 2")
                total_cluster_weight = sum(s.total_weight_kg for s in group)
                cluster_passenger_count = sum(s.parcel_count for s in group)
                order, total_optimized_km = self.get_mapbox_optimized_data(group)
                print(f"DEBUG: Shipments in group: {len(group)}")
                print(f"DEBUG: Order received: {order}")
                print(f"DEBUG: Total optimized km: {total_optimized_km}")
                n = len(group)
                for i in order:
                    if i <n:
                        shipment = group[i]
                        route_stops.append({
                            "type": "PICKUP",
                            "shipment_obj": shipment, # or whatever unique ID you have
                            "lat": shipment.pickup_latitude,
                            "lon": shipment.pickup_longitude
                        })
                    else:
                        shipment = group[i - n]
                        route_stops.append({
                            "type": "DELIVERY",
                            "shipment_obj": shipment,
                            "lat": shipment.dropoff_latitude,
                            "lon": shipment.dropoff_longitude
                        })

                first_stop = route_stops[0]
                last_stop = route_stops[-1]

                # These are your 'Operational' coordinates for the whole cluster
                op_start_lat, op_start_lon = first_stop["lat"], first_stop["lon"]
                last_stop = route_stops[-1]
                final_lat, final_lon = last_stop["lat"], last_stop["lon"]
                
            
                for s in group:
                    s.cluster_id = current_cluster_id
                    processed = self.calculate_final_metrics(
                        s, shared_dist=total_optimized_km, cluster_weight=total_cluster_weight,op_start_lat=op_start_lat, 
                        op_start_lon=op_start_lon,op_lat=final_lat, op_lon=final_lon, cluster_passenger_count=cluster_passenger_count,
                        is_lead=(s == group[0])
                    )
                    final_list.append(processed)
            else:
                print("length is not greater than 2")
                s=group[0]
                s.single_cluster_id = current_cluster_id
                final_list.append(self.calculate_final_metrics(group[0]))
 
      
        
        shipment.route_agent_latency= time.time()-start_time
       
    
        return final_list

    def calculate_final_metrics(self, shipment: ShipmentModel, shared_dist: float = None, cluster_weight=None,op_start_lat=None, 
                        op_start_lon=None,op_lat=None, op_lon=None, cluster_passenger_count=None,is_lead: bool = False) -> ShipmentModel:
        # 1. INDIVIDUAL ROUTING
        try:
            lat, lon = shipment.pickup_latitude, shipment.pickup_longitude
            d_lat, d_lon = shipment.dropoff_latitude, shipment.dropoff_longitude
            route_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{lon},{lat};{d_lon},{d_lat}?access_token={self.mapbox_token}&alternatives=true&overview=false"
            data = self.get_mapbox_route(route_url)
          
            if data.get("code") == "Ok":
                shipment.route_options = []
                for idx, r in enumerate(data['routes']):
                    shipment.route_options.append({
                        "route_index": idx,
                        "base_distance_km": round(r['distance']/1000, 2),
                        "base_duration_min": round(r['duration']/60, 2),
                    })
                    print(f"route_option:{shipment.route_options}")
                shipment.distance_km = shipment.route_options[0]['base_distance_km']
                shipment.duration_min = shipment.route_options[0]['base_duration_min']
            else: raise Exception("Mapbox_Invalid")
        except Exception:
            shipment.distance_km = self.haversine_distance(shipment.pickup_latitude, shipment.pickup_longitude, shipment.dropoff_latitude, shipment.dropoff_longitude)
            shipment.duration_min = round((shipment.distance_km / 20) * 60, 2)
            shipment.route_options = [{"route_index": 0, "base_distance_km": shipment.distance_km, "base_duration_min": shipment.duration_min}]

        # 2. METADATA & TRAFFIC ENRICHMENT (Crucial to do BEFORE snapshot)
        self.enrich_metadata(shipment)
        hist_density = self.get_historical_traffic(shipment)
        pickup_date = shipment.pickup_time.strftime('%Y-%m-%d')
        print(pickup_date)
        print("getting_Weather")
        weather_penalty, weather_label = self.get_weather_impact(shipment.pickup_latitude, shipment.pickup_longitude, pickup_date)
        
        shipment.traffic_density_score = max(0.1, round(hist_density * (1.0 - weather_penalty), 2))
        shipment.weather_condition = weather_label

        for opt in shipment.route_options:
            opt['adjusted_duration_min'] = round(opt['base_duration_min'] / shipment.traffic_density_score, 2)
            opt['delay_delta'] = round(opt['adjusted_duration_min'] - opt['base_duration_min'], 2)
        shipment.duration_min = shipment.route_options[0]["adjusted_duration_min"]

        # 3. OPERATIONAL LOGIC & 
        if shared_dist and cluster_weight:
            original_w, original_d = shipment.total_weight_kg, shipment.distance_km
            
            # Temporary state for Snapshot
            if is_lead:
                shipment.total_weight_kg, shipment.distance_km = cluster_weight, shared_dist
                self.get_vehicle_type(shipment)
                shipment.operational_vehicle_type = shipment.vehicle_type
                
                base_shared_dur = shared_dist / 0.5 
                op_duration = round(base_shared_dur / shipment.traffic_density_score, 2)
                shipment.operational_duration_min = op_duration
                shipment.operational_distance_km=shared_dist
                
                shipment.operational_features = {
                    "total_weight_kg": cluster_weight,
                    "distance_km": shared_dist,
                    "passenger_count": cluster_passenger_count,
                    "dropoff_latitude": op_lat,
                    "dropoff_longitude": op_lon,
                    "pickup_latitude": op_start_lat,
                    "pickup_longitude": op_start_lon,
                    "hour": shipment.hour,
                    "day_of_week": shipment.day_of_week,
                    "is_holiday": shipment.is_holiday,
                    "is_rush_hour": shipment.is_rush_hour,
                    "is_weekend": shipment.is_weekend,
                    "is_high_demand": shipment.is_high_demand,
                    "traffic_density_score": shipment.traffic_density_score,
                    "duration_min": op_duration,
                    "type_van": shipment.type_van,
                    "type_truck": shipment.type_truck,
                    "type_bicycle": shipment.type_bicycle,
                    "type_e_scooter": shipment.type_e_scooter
                }

                shipment.total_weight_kg, shipment.distance_km = original_w, original_d
                self.get_vehicle_type(shipment) 
        
            
            else:
                shipment.operational_distance_km = 0.0
                shipment.operational_duration_min = 0.0
                shipment.operational_vehicle_type = "N/A"
             
        else:
            # If no cluster data provided, the operational view is the individual view
            self.get_vehicle_type(shipment)
            shipment.operational_vehicle_type =0
            shipment.operational_distance_km = 0
            shipment.operational_duration_min = 0
            op_duration = shipment.duration_min
            
            # Map coordinates so the Trace log doesn't break
            op_start_lat, op_start_lon = shipment.pickup_latitude, shipment.pickup_longitude
            op_lat, op_lon = shipment.dropoff_latitude, shipment.dropoff_longitude
            cluster_weight = shipment.total_weight_kg
            """
            shipment.operational_features = {
                    "total_weight_kg": shipment.total_weight_kg,
                    "distance_km": shipment.distance_km,
                    "passenger_count": shipment.parcel_count,
                    "dropoff_latitude": op_lat,
                    "dropoff_longitude": op_lon,
                    "pickup_latitude": op_start_lat,
                    "pickup_longitude": op_start_lon,
                    "hour": shipment.hour,
                    "day_of_week": shipment.day_of_week,
                    "is_holiday": shipment.is_holiday,
                    "is_rush_hour": shipment.is_rush_hour,
                    "is_weekend": shipment.is_weekend,
                    "is_high_demand": shipment.is_high_demand,
                    "traffic_density_score": shipment.traffic_density_score,
                    "duration_min": op_duration,
                    "type_van": shipment.type_van,
                    "type_truck": shipment.type_truck,
                    "type_bicycle": shipment.type_bicycle,
                    "type_e_scooter": shipment.type_e_scooter
                }

            """
        trace_entry = (
            f"[{self.name} Success]\n"
            f"--- ENVIRONMENT ---\n"
            f"Context: [H:{shipment.hour}, Day:{shipment.day_of_week}, Rush:{shipment.is_rush_hour}, Holiday:{shipment.is_holiday}]\n"
            f"Signals: [Traffic:{shipment.traffic_density_score}, Weather:{shipment.weather_condition}]\n"
            f"\n--- INDIVIDUAL VIEW (Customer Pricing) ---\n"
            f"Payload: {original_w if shared_dist else shipment.total_weight_kg}kg\n"
            f"Route:   [{shipment.pickup_latitude}, {shipment.pickup_longitude}] -> [{shipment.dropoff_latitude}, {shipment.dropoff_longitude}]\n"
            f"Metrics: {shipment.distance_km}km | {shipment.duration_min}min | Vehicle: {shipment.vehicle_type}\n"
            f"\n--- OPERATIONAL VIEW (Fleet Execution) ---\n"
            f"CLUSTER_ID:{shipment.cluster_id}\n"
            f"Payload: {cluster_weight if shared_dist else shipment.total_weight_kg}kg (ClusterTotal)\n"
            f"Route:   [{op_start_lat if op_start_lat else shipment.pickup_latitude}, {op_start_lon if op_start_lon else shipment.pickup_longitude}] -> [{op_lat if op_lat else shipment.dropoff_latitude}, {op_lon if op_lon else shipment.dropoff_longitude}]\n" 
            f"Metrics: {shipment.operational_distance_km}km | {shipment.operational_duration_min}min | Vehicle: {shipment.operational_vehicle_type}\n"
        )
    

        shipment.agent_trace.append(f"\n{trace_entry}\n")
    
        return shipment
    
