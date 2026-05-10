import xgboost as xgb
import pandas as pd
from src.models.data_models import ShipmentModel
from src.agents.agents.base_agent import BaseAgent
import numpy as np
import mlflow.pyfunc
import os
import platform
from src.utils.prediction_data_validator import DataValidationError, validate_columns,validate_dataype
import time

class PricingAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="PricingAgent")
        model_path=os.path.join("trained_models", "pricing_xgb_model.json")

        self.model=xgb.Booster()
        if os.path.exists(model_path):
            self.model.load_model(model_path)
            print(f"XGBoost model loaded successfully from: {model_path}")
        else:
            print(f"ERROR: Model file not found at: {model_path}")
            # List files to help you debug in the Docker logs
            print(f"Current directory contents: {os.listdir('.')}")
        self.feature_cols=['passenger_count', 'pickup_longitude', 'pickup_latitude', 'dropoff_longitude', 'dropoff_latitude', 'total_weight_kg', 'distance_km', 'hour', 'day_of_week', 'is_holiday', 'duration_min', 'traffic_density_score', 'is_rush_hour', 'is_weekend', 'is_high_demand', 'type_bicycle', 'type_e_scooter', 'type_truck', 'type_van']
        
    def process(self, shipment: ShipmentModel) -> ShipmentModel:
        start_time=time.time()
        best_price = float('inf')
        best_option = None
        for option in shipment.route_options:
            current_dist= option['base_distance_km']
            current_dur=option['adjusted_duration_min']
            shipment.distance_km = current_dist
            shipment.duration_min = current_dur

            # Predict
            current_final_price = self._get_prediction(shipment)
            print(f"current_final_price:{current_final_price}")
 
            surge_multiplier= self._calculate_market_surge(shipment)
    
            shipment.weather_factor = surge_multiplier

            if current_final_price < best_price:
                best_price = current_final_price
                best_option={
                    "price": best_price,
                    "predicted_base_price":current_final_price,
                    "distance": option['base_distance_km'],
                    "duration": option['adjusted_duration_min'],
                    "delta": option['delay_delta'],
                    "index": option['route_index'],
                    "surge_multiplier":surge_multiplier
                }
            
            if best_option:
                shipment.final_market_price = best_option['price']
                shipment.predicted_base_price = best_option['predicted_base_price']
                shipment.distance_km = best_option['distance']
                shipment.duration_min = best_option['duration']
                shipment.delay_delta = best_option['delta']
                shipment.weather_factor = best_option['surge_multiplier']
            

        #opertaional cost for comapny
        if hasattr(shipment, 'operational_features') and shipment.operational_features:
            # We create a temporary dataframe from the operational dictionary
            op_df = pd.DataFrame([shipment.operational_features])
            
            # Use the same logic but on the operational data
            op_dmat = xgb.DMatrix(op_df[self.feature_cols])
            op_pred = self.model.predict(op_dmat)[0]
            operational_cost = round(float(np.expm1(op_pred)), 2)
            shipment.operational_cost=round(operational_cost * self._calculate_market_surge(shipment), 2)
      
            shipment.old_operational_cost=shipment.operational_cost
        
        else:
            # For solo routes, cost = base price
            shipment.operational_cost = 0.0
        
        
        shipment.pricing_agent_latency = time.time() - start_time
        selected_index = best_option["index"] if (best_option and "index" in best_option) else "N/A (Optimized)"
        trace_entry=(
            f"[{self.name} Success] ->"
            f"best_route:Selected Route {selected_index},"
            f"final_price:{shipment.final_market_price},"
            f"weather_condition:{shipment.weather_condition},"
            f"weather_factor:{shipment.weather_factor}",
            f"optimized_cost:{shipment.old_operational_cost}"
        )
        
        shipment.agent_trace.append(f"\n{trace_entry}\n")
       
        return shipment
    
    def _get_prediction(self, shipment: ShipmentModel) -> float:
        """Helper to handle the XGBoost boilerplate"""
        data_dict = shipment.model_dump(by_alias=True)
        df = pd.DataFrame([data_dict])
        
        # Validation
        if not (validate_columns(df) and validate_dataype(df)):
            raise DataValidationError("Invalid features for pricing")
            
        X = df[self.feature_cols]
        dmat = xgb.DMatrix(X)
        prediction = self.model.predict(dmat)[0]
        base_price = np.expm1(prediction)

        shipment.raw_model_prediction= round(float(base_price),2)

        return round(base_price * self._calculate_market_surge(shipment), 2)

    def _calculate_market_surge(self, shipment: ShipmentModel) -> float:
        """Determines the market multiplier based on environmental factors"""
        multiplier = 1.0
        
        # Weather Surge
    
        if shipment.weather_condition == "Rain":
            multiplier += 0.2  # 10% Surge
        elif shipment.weather_condition == "Snow":
            multiplier += 0.4  # 30% Surge
        elif shipment.weather_condition == "Storm":
            multiplier += 0.6  # 50% Surge
        elif shipment.weather_condition == "Fog":
            multiplier += 0.1  # 50% Surge
        elif shipment.weather_condition == "Overcast":
            multiplier += 0.05 # 50% Surge
        else:
            multiplier=1.0
            
        return multiplier
