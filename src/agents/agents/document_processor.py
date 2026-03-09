from src.agents.prompts.document_prompt import DOCUMENT_AGENT_PROMPT
from src.utils.converter import DocumentConverter
from src.agents.agents.base_agent import BaseAgent
from src.models.data_models import ShipmentModel
import json
from langchain_openai import ChatOpenAI

class DocumentAgent(BaseAgent):
    def __init__(self, llm_client):
        self.llm=llm_client
        # Inherit from BaseAgent to get tracking and feature engineering
        super().__init__(name="DocumentAgent")
        
    def process(self,way_bill_text:str,feedback: str = None)->ShipmentModel:
        """
        The main agent logic: Extract -> Convert -> Enrich.
        """
        user_message = f"Extract from this waybill: {way_bill_text}"
        
        # If this is a retry, tell the LLM what it did wrong last time
        if feedback:
            user_message = (
                f"### REVISION REQUEST ###\n"
                f"Your previous extraction was rejected by the auditor for: {feedback}\n"
                f"Please re-analyze and provide the correct JSON for this text: {way_bill_text}"
            )

        messages = [
            ("system", DOCUMENT_AGENT_PROMPT),
            ("user", user_message)
        ]
        
        response = self.llm.invoke(messages, response_format={"type": "json_object"})
        raw_data =json.loads(response.content)
        
        #get vehicle type
        #convert to pydantic structure
        shipment = DocumentConverter.to_shipment(raw_data)
        
        trace_entry = (
        f"[{self.name} Success] ->"
        f"shipment_id:{shipment.shipment_id},"
        f"pickup_address:{shipment.origin_address},"
        f"destination_address:{shipment.destination_address},"
        f"pacel_weight:{shipment.total_weight_kg}kg,"
        f"category:{shipment.item_category},"
        f"parcel_count:{shipment.parcel_count}"
      
    )

        shipment.agent_trace.append(f"\n{trace_entry}\n")
        return shipment

