from pydantic import BaseModel, Field, ConfigDict,field_validator,model_validator
from datetime import datetime
from typing import Optional,List,Dict,Any
from decimal import Decimal

class LineItem(BaseModel):
    product_name:str
    unit_weight_kg:float
    quantity:int
    category:str
    
    @field_validator('unit_weight_kg')
    @classmethod
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError(f"Weight must be greater than 0. Got: {v}")
        return v


class ShipmentModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # 1. FROM WAYBILL (Document Agent
    shipment_id: str = Field(..., alias="waybill_id")
    cluster_id: Optional[str] = "SINGLETON"
    single_cluster_id: Optional[str] = "SINGLETON"
    items:List[LineItem]
    origin_address: str
    destination_address: str
    total_weight_kg:float = 0.0
    parcel_count: int = Field(..., alias="passenger_count")
    pickup_time: datetime
    type_truck: int = 0
    type_van: int = 0
    type_bicycle: int = 0
    type_e_scooter: int = 0
    vehicle_type:str="bicycle"
    route_options:List[Dict[str,Any]]=[]
    selected_route_index: int = 0
    delay_delta: float = 0.0
  

    # 2. FROM ROUTE AGENT & UTILS
    # These map directly to your XGBoost training columns
    pickup_latitude: float = 0.0
    pickup_longitude: float = 0.0
    dropoff_latitude: float = 0.0
    dropoff_longitude: float = 0.0
    distance_km: float = 0.0
    duration_min: float = 0.0
    
    # 3. FROM FEATURE ENGINEERING (Applied on-the-fly)
    hour: int = 0
    day_of_week: int = 0
    is_holiday: int = 0  # <--- ADD THIS to match your CSV
    is_rush_hour: int = 0
    is_weekend: int = 0
    is_high_demand: int = 0
    traffic_density_score: float = 1.0 # Match training default

    # 4. DEMAND FORECASTING INPUTS
    weather_condition: str="sunny"
    weather_factor: float = 1.0 # Default: 1.0 (Off-peak)
      
    # 5. FINAL OUTPUTS
    raw_model_prediction: float =0.0
    predicted_base_price: float = 0.0 # Raw XGBoost output
    final_market_price: float = 0.0 
    all_individual_price:float=0.0
      # XGBoost * Demand Surge

    is_verified: bool = False
    agent_trace: List[str] = []
    operational_features: dict = {}
    operational_distance_km: float = 0.0 
    operational_duration_min: float = 0.0
    operational_vehicle_type:str="bicycle"
    operational_cost:float=0.0
    old_operational_cost:float=0.0
    pickup_latitude: float = 0.0
    pickup_longitude: float = 0.0
    dropoff_latitude: float = 0.0
    dropoff_longitude: float = 0.0
    
    
    guardrail_is_safe: bool = True
    guardrail_latency: float = 0.0
    guardrail_prompt_tokens: float = 0
    guardrail_completion_tokens: float = 0
    guardrail_cost_usd: float =0
    
   
    # 2. Token & Cost Tracking
    doc_prompt_tokens:int = 0
    doc_completion_tokens:int = 0
    doc_llm_cost_usd:float=0
    doc_latency: float = 0.0
    doc_ttft:float=0.0
    model_used:str="GPT-4o-mini"

    
    validation_latency:float=0.0
    validation_prompt_tokens:int = 0
    validation_completion_tokens:int = 0
    validation_llm_cost_usd:float = 0.0
    
    route_agent_latency:float=0.0
    pricing_agent_latency:float=0.0
    critic_agent_latency:float=0.0

    is_cached:bool = False
    
    # 3. Agent Performance
    critic_override_count:int = 0
   
    anomaly_score:float = 0.0
    is_anomaly:bool = False
    
    # 4. Economic ROI
    margin_savings:float = 0.0
    optimization_ratio:float =0.0
    audit_action:str = "none"
    theoretical_price:float=0.0
    optimized_theoretical_price:float=0.0


    @model_validator(mode='after')
    def validate_total_sum(self) -> 'ShipmentModel':
        """Senior Check: Cross-verify LLM summation math"""
        if self.items:
            print(f"DEBUG: First item type is {type(self.items[0])}")
            print(f"DEBUG: First item data: {self.items[0]}")
        expected_sum = sum(Decimal(str(item.unit_weight_kg)) * Decimal(str(item.quantity)) for item in self.items)
        print (round(expected_sum,2))
        total_weight_kg=Decimal(str(self.total_weight_kg))
        if abs(total_weight_kg - expected_sum) > Decimal(0.1):
            # We don't necessarily raise an error, but we flag it for the reflection agent
            self.total_weight_kg = float(expected_sum)
            msg = f"Math Warning: LLM total ({total_weight_kg}) != calculated sum ({expected_sum})"
            print(msg)
            self.agent_trace.append(msg)
        return self