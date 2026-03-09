import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from src.agents.agents.pricing_agent import PricingAgent
from src.models.data_models import ShipmentModel
from datetime import datetime

@pytest.fixture
def pricing_agent():
    with patch('mlflow.pyfunc.load_model'):
        agent=PricingAgent()
        #create fake model predict method
        agent.model=MagicMock()
        agent.model.predict.return_value=np.array([np.log1p(20.0)])
        return agent

def test_pricing_surge_logic_rain(pricing_agent):
    shipment= ShipmentModel(
        shipment_id="PRICING-1",
        passenger_count=1,
        total_weight_kg=5.0,
        distance_km=10.0,
        weather_condition="Rain", # Should trigger +0.2 surge
        pickup_time=datetime.now(),
        origin_address="A",
        destination_address="B"
    )
    
    result=pricing_agent.process(shipment)

    #assert base price from our mck is 20.0 and surge is 1.2 for rain\
    assert result.predicted_base_price == 20.0
    assert result.final_market_price == 24.0
    assert result.weather_factor == 1.2 

def test_pricing_surge_logic_clear(pricing_agent):
    shipment= ShipmentModel(
        shipment_id="PRICING-2",
        passenger_count=1,
        weather_condition="Clear",
        pickup_time=datetime.now(),
        origin_address="A",
        destination_address="B"
    )

    result= pricing_agent.process(shipment)

    #price should stay 20.0 only 
    assert result.final_market_price==20.0
    assert result.weather_factor==1.0

