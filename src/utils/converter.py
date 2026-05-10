import json
from datetime import datetime
from src.models.data_models import ShipmentModel
from pydantic import ValidationError

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
            print("mapping raw_data to pydantic shipment model")
            raw_items = raw_extraction.get("items", [])
            print(raw_items)
            mapped_items=[]

            for  item in raw_items:
                weight= float(item.get("unit_weight_kg",0.0))
                mapped_items.append({
                "product_name": item.get("product_name", "Unknown"),
                "unit_weight_kg": weight,  # Forced Float
                "quantity": int(item.get("quantity", 1)),
                "category": item.get("category", "general")
            })
            print(mapped_items)
            return ShipmentModel(
                shipment_id=raw_extraction.get("waybill_id", "UNKNOWN"),
                items=mapped_items,
                origin_address=raw_extraction.get("pickup_location", ""),
                destination_address=raw_extraction.get("delivery_location", ""),
                passenger_count=raw_extraction.get("total_quantity", 1),
                # Ensure we handle the key 'total_weight' used in the prompt example
                total_weight_kg=float(raw_extraction.get("total_weight", 1.0)), 
                pickup_time=datetime.fromisoformat(
                    raw_extraction.get("pickup_date_time", datetime.now().isoformat())
                ),
                agent_trace=["DocumentAgent"] 
            )
        
        except ValidationError as ve:
            print("\n" + "!"*30 + " VALIDATION FAILED " + "!"*30)
            # This prints the specific error for every field
            for error in ve.errors():
                # 'loc' tells you the exact field, 'msg' tells you why (e.g., 'field required')
                print(f"LOCATION: {error['loc']}")
                print(f"MESSAGE:  {error['msg']}")
                print(f"INPUT:    {error.get('input', 'N/A')}")
                print("-" * 60)
            print("!"*79 + "\n")
            raise
        except Exception as e:
            print(f"Critical Mapping Error: {e}")
            raise