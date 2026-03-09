import json
from datetime import datetime
from src.models.data_models import ShipmentModel

class DocumentConverter:
    """
    Handles the transformation of raw LLM extractions into 
    the validated ShipmentModel.
    """

    @staticmethod
    def to_shipment(raw_extraction:dict)->ShipmentModel:
        """
        Converts raw dictionary from LLM to Pydantic Model.
        Maps waybill fields to training feature names.
        """
        try:
            # We use .get() with defaults to prevent crashes
            return ShipmentModel(
                shipment_id=str(raw_extraction.get("waybill_id", "UNKNOWN")),
                origin_address=raw_extraction.get("pickup_location", ""),
                destination_address=raw_extraction.get("delivery_location", ""),
                passenger_count=int(raw_extraction.get("quantity", 1)),
                # Ensure we handle the key 'total_weight' used in the prompt example
                total_weight_kg=float(raw_extraction.get("total_weight", 1.0)), 
                item_category=raw_extraction.get("category", "standard_parcels"),
                pickup_time=datetime.fromisoformat(
                    raw_extraction.get("pickup_date_time", datetime.now().isoformat())
                ),
                agent_trace=["DocumentAgent"]
            )
            
        except Exception as e:
            print(f"Critical Mapping Error: {e}")
            raise