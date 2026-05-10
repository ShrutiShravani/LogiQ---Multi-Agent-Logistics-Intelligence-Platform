from src.agents.agents.base_agent import BaseAgent
from src.models.data_models import ShipmentModel
import json
import math
import os
from src.utils.prediction_data_validator import DataValidationError
import time

class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="CriticAgent")
        self.mapping_path = os.path.join("data", "transformed","traffic_mapping.json")
            # Match the exact path where your NYCFeatureEngineer saved the JSON
        try:
            with open(self.mapping_path ,"r") as f:
                    self.traffic_memory = json.load(f)
        except FileNotFoundError:
            print(f"Warning: Traffic mapping not found for {self.name}. Using defaults.")
            self.traffic_memory = {}
        
        self.v_base = {'e_scooter': 2.0, 'bicycle': 2.5, 'van': 15.0, 'truck': 45.0}
        self.v_rate = {'e_scooter': 0.5, 'bicycle': 1.0, 'van': 2.5, 'truck': 5.0}
        
       

    def process(self, shipment: ShipmentModel) -> ShipmentModel:
        start_time=time.time()
        # --- CONDITION 1: DOCUMENT EXTRACTION ---
        overrides = [] 
        

        # --- CONDITION 2: ROUTE & ETA OVERRIDE ---
        correct_v = self._get_correct_vehicle(shipment.distance_km, shipment.total_weight_kg)
        if shipment.vehicle_type != correct_v:
            overrides.append(f"Vehicle: {shipment.vehicle_type} -> {correct_v}")
            shipment.vehicle_type = correct_v
            self._sync_vehicle_flags(shipment)
        
        # --- PASS 1: AUDIT INDIVIDUAL ---
        shipment.theoretical_price,duration_min,local_overrides = self._audit_reality(
            shipment,
            shipment.duration_min, 
            shipment.total_weight_kg,
            shipment.vehicle_type,
            shipment.distance_km   
        )
    
        # Recalculate final market price after audit
        shipment.theoretical_price = round(shipment.theoretical_price * shipment.weather_factor, 2)
        diff = abs(shipment.predicted_base_price - shipment.theoretical_price) / (shipment.theoretical_price if shipment.theoretical_price > 0 else 1)
        
        if diff > 0.20: # Senior level threshold
            overrides.append(f"Indvidual_Price: ${shipment.theoretical_price} Overriding-> ${shipment.predicted_base_price},duration:{local_overrides}")
            shipment.predicted_base_price = shipment.theoretical_price
       
        
        
        #check for optimized route
        if hasattr(shipment, 'operational_features') and shipment.operational_features:
            op_dist = shipment.operational_features.get('distance_km')
            op_weight = shipment.operational_features.get('total_weight_kg')
            op_dur = shipment.operational_features.get('duration_min')
            op_veh = shipment.operational_vehicle_type
            
            correct_v_op = self._get_correct_vehicle(op_dist, op_weight)
            if op_veh != correct_v_op:
                overrides.append(f"Op_Vehicle Override: {op_veh} -> {correct_v_op}")
                shipment.operational_vehicle_type = correct_v_op
                # Update the operational dictionary flags for XGBoost consistency
                for v in ['truck', 'van', 'bicycle', 'e_scooter']:
                    shipment.operational_features[f'type_{v}'] = 1 if correct_v_op == v else 0
            
            optimized_theoretical_price,new_op_dur ,local_overrides= self._audit_reality(
                shipment,
                op_dur, 
                shipment.operational_features['total_weight_kg'],
                shipment.operational_vehicle_type,
                op_dist
            )


            shipment.optimized_theoretical_price= round(optimized_theoretical_price* shipment.weather_factor,2)
       
            diff = abs(shipment.operational_cost - shipment.optimized_theoretical_price) / (shipment.theoretical_price if shipment.theoretical_price > 0 else 1)
        
            if diff > 0.15 and shipment.operational_cost!=0.0: # Senior level threshold
                overrides.append(f"Opertaionl_Price: ${shipment.optimized_theoretical_price} Overriding-> ${shipment.operational_cost},duration_override{local_overrides}")
                shipment.operational_cost = shipment.optimized_theoretical_price
       
    

        shipment.critic_agent_latency=time.time()-start_time
            # --- FINALIZE METRICS ---
        shipment.is_verified = True
        # Final Trace
        msg = f"[{self.name}]: " + ("; ".join(overrides) if overrides else "Verified - No Overrides.")
        shipment.agent_trace.append(msg)
        
        
        return shipment

    def _audit_reality(self,s,dur,weight, vehicle,dist):
        """Audits a specific route reality (Individual or Operational)"""
        local_overrides = []
        """
        # 1. Coordinate Awareness
        p_lat = lat if lat is not None else s.pickup_latitude
        p_lon = lon if lon is not None else s.pickup_longitude
        dest_lat = d_lat if d_lat is not None else s.dropoff_latitude
        dest_lon = d_lon if d_lon is not None else s.dropoff_longitude
        """
        min_dist_floor = dist
        # 1. Duration Check
        key = f"{s.hour}_{s.day_of_week}_{s.is_holiday}" # Standardize these
        stats = self.traffic_memory.get(key, {"actual_speed_kmh": 20.0})
        theoretical_dur = (min_dist_floor/ stats['actual_speed_kmh']) * 60 + 3.0
         #service floor

        if dur <= 0 or abs(dur - theoretical_dur) > (theoretical_dur * 0.8):
            local_overrides.append(f"_Dur: {dur}min -> {round(theoretical_dur, 2)}min")
            dur = round(theoretical_dur, 2)
 
        # 2. Pricing Check
        # We simulate a ShipmentModel object for the theoretical calculator
        theory_price = self._calculate_theoretical_price_raw(s,min_dist_floor, weight, vehicle, dur)
        
    

        return theory_price,dur,local_overrides

    def _get_correct_vehicle(self, d, w):
        if w > 150.0:
            return 'truck'
        elif w > 20.0 and d>15.0:
            return 'van'
        
        # Light weights (w <= 20)
        else:
            if d <= 3.0:
                return 'e_scooter'
            if 3.0 < d <= 15.0:  # Matches the new 10km Bicycle rule
                return 'bicycle'
        return 'van' # Ultimate fallback

    def _sync_vehicle_flags(self, s: ShipmentModel):
        s.type_e_scooter, s.type_bicycle, s.type_van, s.type_truck = 0, 0, 0, 0
        setattr(s, f"type_{s.vehicle_type}", 1)

    def _calculate_theoretical_price_raw(self, s, dist,weight, vehicle, dur):
        """A 'Raw' version of the price calculator for both realities"""
        base = self.v_base.get(vehicle, 45.0)
        km_r = self.v_rate.get(vehicle, 5.0)
        surge = 1.0 + (s.is_rush_hour * 0.2) + (s.is_weekend * 0.15) + (s.is_holiday * 0.4)
        congestion = 1.25 if s.traffic_density_score < 0.5 else 1.0
        weight_fee = (weight - 5) * 0.5 if weight > 5 else 0
        
        return round((base + (dist * km_r) + (s.parcel_count * 1.5) + (dur * 0.2)+ weight_fee) * surge * congestion, 2)
