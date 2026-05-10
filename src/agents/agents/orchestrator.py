from typing import TypedDict, List, Optional
from src.models.data_models import ShipmentModel
from langgraph.graph import StateGraph, END
from geopy.geocoders import Nominatim
import mlflow
import json
import os

DLQ_PATH = "data/dlq"
os.makedirs(DLQ_PATH, exist_ok=True)

QUARANTINE_DIR = os.path.join(DLQ_PATH, "quarantine")
os.makedirs(QUARANTINE_DIR,exist_ok=True) # For viruses/corrupt files
manual_review_path= os.path.join(QUARANTINE_DIR,"manual_review.json")


#mlflow.set_tracking_uri("http://localhost:5000") # or your local path
#mlflow.set_experiment("Agentic_Pricing_Audit") #this sets only for local run

class AgentState(TypedDict):
    waybill_text: str
    pdf_path:str
    shipment: Optional[ShipmentModel]
    feedback: Optional[str]
    attempts: int 
    extraction_attempts: int
    error_log: List[str] 
    is_safe:False
    goto_dlq:False
    guardrail_latency:float
    guardrail_prompt_tokens:float
    guardrail_completion_tokens:float
    guardrail_cost_usd:float

geolocator = Nominatim(user_agent="nyc_logistics_auditor")
def create_logisticsgraph(guardrail_agent,doc_agent,data_validation_agent,checkpointer=None):
    workflow=StateGraph(AgentState)

    #call guradrail
    def waybill_guardrail(state):
        if state.get("goto_dlq") is True:
            return "dlq"
        if state["is_safe"] is True:
            return "is_safe"
        else:
            return "end"
    
    def doc_extraction(state):
        shipment=state["shipment"]
        if shipment is None or state.get("goto_dlq"):
            return "dlq"
        if shipment:
            return "validator"
        return "end"
    
    def check_validation(state):
        shipment=state["shipment"]
        if state.get("goto_dlq"):
            return "dlq"
        if shipment and shipment.is_verified:
            return "verified"
        if shipment["is_verified"] is False and state["attempts"] < 2:
            return "retry"
        else:
            return "end"
    

    def call_human_review(state):
      
        review_entry = {
                "pdf_path":state.get('pdf_path'),
                "raw_text":state.get('waybill_text'),
                "system_errors": state.get("error_log")
            }
        with open(manual_review_path,"a") as f:
                f.write(json.dumps(review_entry) + "\n")
        mlflow.log_metric("manual_intervention_required", 1)
        print(f"!!! ALERT: Shipment sent to DLQ/Human Review.")

    async def call_guardrail(state):
        result= await guardrail_agent.check_security(state)
        if  isinstance(result,dict):
            print(result)
        return result
    
    #document extraction
    async def call_doc(state):
            res= await doc_agent.process(state, feedback=state.get("feedback"))
            shipment=res.get("shipment")
            # DEBUG PRINTS
            shipment.guardrail_latency = state.get("guardrail_latency", 0.0)
            shipment.guardrail_prompt_tokens=state.get("guardrail_prompt_tokens",0.0)
            shipment.guardrail_completion_tokens=state.get("guardrail_completion_tokens",0.0)
            shipment.guardrail_cost_usd=state.get("guardrail_cost_usd",0.0)
            print(f"DEBUG: Raw Extracted Pickup adress: {shipment.origin_address} ")
            print(f"Raw Extracted Delivery adress: {shipment.destination_address}")
            print(f"weight: {shipment.total_weight_kg} ,parcel_count: {shipment.parcel_count}")
            print(f"pickup_time: {shipment.pickup_time}")
            return {"shipment": shipment, "extraction_attempts": state["extraction_attempts"] + 1,"feedback": None}
      
    async def call_validator(state):
        # Use the logic from your data_validator class
        # Note: validation_agent is the instance of your class
        if state["shipment"] is None:
            # Pydantic already failed, so we don't run Z-Score or Phi-3
        # We just pass the feedback through
            return {"is_verified": False}
        print("validtaion started")
        result = await data_validation_agent.validator_node(state)
        
        # This will return either:
        # 1. {"feedback": "...", "attempts": X} -> triggers "retry"
        # 2. {"next": "route_agent", "is_verified": True, "shipment": shipment} -> triggers "valid"
        return result
        
    
    def check_validation(state):
        shipment=state["shipment"]
        if shipment and shipment.is_verified:
            return "valid"
        if state["attempts"] < 3:
            return "retry"
        return "fail"

    # Define the Graph
    workflow.add_node("security_gate",call_guardrail)
    workflow.add_node("document_agent", call_doc)
    workflow.add_node("validator", call_validator)
    workflow.add_node("human_review", call_human_review)

    workflow.set_entry_point("security_gate")
    workflow.add_edge("human_review", END)

    
    workflow.add_conditional_edges(
        "security_gate",
        waybill_guardrail,
        {
            "is_safe": "document_agent",
            "dlq":"human_review",
            "end": END
        }
    )

    workflow.add_conditional_edges(
        "document_agent",
        doc_extraction,
        {
            "validator": "validator",
            "dlq":"human_review",
            "end": END
        }
    )

    workflow.add_conditional_edges(
        "validator",
        check_validation,
        {
            "valid": END,
            "retry": "document_agent",
            "dlq":"human_review",
            "fail": END # In prod, this goes to Human Review
        }
    )

    return workflow.compile(checkpointer=checkpointer)