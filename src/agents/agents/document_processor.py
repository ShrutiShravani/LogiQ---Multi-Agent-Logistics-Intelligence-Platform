from src.agents.prompts.document_prompt import DOCUMENT_AGENT_PROMPT
from src.utils.converter import DocumentConverter
from src.agents.agents.base_agent import BaseAgent
from src.models.data_models import ShipmentModel
import json
from langchain_openai import ChatOpenAI
import time
from src.utils.dead_letter_queue  import send_to_dlq
import mlflow

class DocumentAgent(BaseAgent):
    def __init__(self, llm_client,fallback_client):
        # Inherit from BaseAgent to get tracking and feature engineering
        super().__init__(name="DocumentAgent")
        self.llm=llm_client
        self.fallback = fallback_client
        self.cost_per_1k_input = 0.15 
        self.cost_per_1k_output = 0.60
    

    async def get_stream(self,messages,state)->ShipmentModel:
        """
        The main agent logic: Extract -> Convert -> Enrich.
        """
        full_content=""
        ttft = None
        final_usage = None
        start_time = time.time() # Must define start_time here for TTFT calculation
       
       
        try:
            async for chunk in self.llm.astream(messages,response_format={"type": "json_object"}):
                if ttft is None:
                    ttft=time.time()-start_time
                
                if chunk.content:
                    full_content+=chunk.content

                if hasattr(chunk,'usage_metadata') and chunk.usage_metadata:
                    final_usage=chunk.usage_metadata
            
            return full_content, ttft, final_usage
        except Exception as e:
            print(f"Primary llm failed for {self.name}:{str(e)} ")
            mlflow.set_tag("fallback_triggered","true")
            mlflow.log_param(f"llm api error",str(e)[:100])
            full_content = ""
            ttft = None
            start_time = time.time()
            async for chunk in self.fallback.astream(messages, response_format={"type": "json_object"}):
                if ttft is None:
                    ttft = time.time() - start_time
                if chunk.content:
                    full_content += chunk.content
                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                    final_usage = chunk.usage_metadata
            return full_content, ttft, final_usage
    

    async def process(self,state,feedback:None):
        start_time=time.time()
        pdf_path=state.get("pdf_path")
        waybill_text=state.get("waybill_text","")

        feedback = state.get("feedback", "")
        user_message = f"Extract from this waybill: {waybill_text}"
        

        # If this is a retry, tell the LLM what it did wrong last time
        if feedback:
            user_message = (
                f"### AUDIT REJECTION - ACTION REQUIRED ###\n"
                f"The previous extraction for this document failed validation.\n"
                f"FEEDBACK FROM AUDITOR: {feedback}\n\n"
                f"SOURCE TEXT TO RE-EXAMINE:\n{waybill_text}\n\n"
                f"Please provide a corrected JSON. Ensure the 'unit_weight_kg' for the flagged item is accurate."
                "1. Re-read the text. If you made a typo, fix it.\n"
                "2. If the text truly says this weight, keep it but add 'VERIFIED BY AGENT' to the trace."
            )

        messages = [
            ("system", DOCUMENT_AGENT_PROMPT),
            ("user", user_message)
        ]
        
        try:
            #call  the streaming helper
            content,ttft,final_usage= await self.get_stream(messages,state)
           
            #parse json
            # Parse JSON and Convert
            raw_data = json.loads(content)
          
            shipment = DocumentConverter.to_shipment(raw_data)
           
            if final_usage:
                print(final_usage)
                p_tokens = final_usage.get('input_tokens', 0)
                c_tokens = final_usage.get('output_tokens', 0) 
                
                print(f"p_tokens:{p_tokens}")
                print(f"c_tokens:{c_tokens}")
                
                #capture metrics
                shipment.doc_prompt_tokens += p_tokens
                shipment.doc_completion_tokens += c_tokens
                
                # Calculate Cost
                shipment.doc_llm_cost_usd += (
                    (p_tokens / 1000 * self.cost_per_1k_input) +
                    (c_tokens / 1000 * self.cost_per_1k_output)
                )

                
                shipment.doc_ttft = ttft
                shipment.doc_latency = (time.time() - start_time)
                shipment.model_used="gpt-4o-mini"

                shipment.agent_trace.append(f"[{self.name} Success] extracted {shipment.shipment_id}")

                return {"shipment": shipment, "extraction_attempts": state.get("extraction_attempts", 0)+1}
        
        except Exception as e:
            error_msg = f"Document Extraction Failed: {str(e)}"
            send_to_dlq(pdf_path,error_msg)
            return {"goto_dlq": True, "error_log": [error_msg]}


