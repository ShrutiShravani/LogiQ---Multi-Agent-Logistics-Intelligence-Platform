from src.utils.data_validation import statistical_audit,reflection_validator
from src.agents.agents.base_agent import BaseAgent
from src.models.data_models import ShipmentModel
import time

from src.utils.dead_letter_queue  import send_to_dlq

class data_validator(BaseAgent):
    def __init__(self,llm_client,fallback_client):
        super().__init__(name="DataValidtaion_Agent")
        self.llm=llm_client
        self.fallback=fallback_client
        self.reflection_validator=reflection_validator
        self.validation_cost_1k_input = 0.0005 
        self.validation_cost_output = 0.0015

  
    async def validator_node(self,state):
        start_time=time.time()
        anomalies=[]
        attempts = state.get("attempts",0)
        shipment=state["shipment"]
        pdf_path = state.get("pdf_path")
        waybill_text=state.get("waybill_text")
        # 1. Layer 1 (Pydantic) already ran when ShipmentModel was created.
        
        for item in shipment.items:
        # 2. Layer 2: Statistical Audit
            is_stat_valid, z_score = statistical_audit(
                item.unit_weight_kg, 
                item.category
            )
            print(f"DEBUG: Item: {item.product_name} | Weight: {item.unit_weight_kg} | Z:{z_score}")

            if not is_stat_valid:
                shipment.is_anomaly = True
                shipment.audit_action = "rejected"
                shipment.anomaly_score = max(float(shipment.anomaly_score), abs(float(z_score)))
                clean_z_score = float(z_score)
                print(f"Statistical Anomaly Detected (Z={z_score}). Triggering Reflection...")
                anomalies.append({"item": item.product_name, "z_score": round(clean_z_score,2), "cat": item.category, "w": item.unit_weight_kg})
            
        if not anomalies:
            shipment.is_verified = True
      
            shipment.audit_action = "none"
            shipment.validation_latency = time.time() - start_time
            print("validation done")
            return {"shipment": shipment, "is_verified": True}

        target = anomalies[0]
        print(f"target:{target}")
        try:
            resolution = await reflection_validator(self,target['w'], target['cat'], target['z_score'],waybill_text)
            prompt_tokens = resolution.get("p_tokens", 0)
            print(f"prompt_tokens:{prompt_tokens}")
            shipment.validation_prompt_tokens=prompt_tokens
            completion_tokens = resolution.get("c_tokens", 0)
            shipment.validation_completion_tokens= completion_tokens
            print(f"prompt_tokens:{completion_tokens}")
            shipment.validation_llm_cost_usd=(prompt_tokens/1000*self.validation_cost_1k_input)+(completion_tokens/1000*self.validation_cost_output)
        except Exception as e:
            # If BOTH Phi-3 and GPT fallback fail, move to DLQ
            send_to_dlq(pdf_path,f"Validation System Failure: {str(e)}")
            return {"goto_dlq": True}
    
    
        if resolution["decision"] == "REJECT":
            attempts+=1
            if attempts<2:
                print(f"attempts:{attempts}")
                reason= resolution.get('reason','General Error')
                feedback_note = (
                f"CRITIC_REJECT: Item '{target['item']}' (Category: {target['cat']}) has a suspicious weight of {target['w']}kg."
                f"Audit Issue: {reason}. "
                f"Instruction: Locate '{target['item']}' in the waybill text below. Check if the weight was misread (e.g., 0.20kg vs 20kg)."
                "Look specifically for decimal points (e.g., 0.5 vs 50)."
            )
                shipment.agent_trace.append(f"Error message:{reason} ,Critic feedback: {feedback_note}")
                
                return {
                "feedback": feedback_note, 
                "attempts": attempts # Attempts incremented in call_doc
            }

            else:
                shipment.audit_action = "human_review_required"
                print("Critical Failure: Moving to Human Review")
                send_to_dlq(pdf_path, "Logical Validation failed after max attempts.")
                
                return {"goto_dlq": True}
                
        
        else:

            print(f"Reflection Approved Outlier: {resolution['reason']}")
            shipment.audit_action = "verified_outlier"
        
            shipment.is_verified = True
        shipment.validation_latency = (time.time() - start_time)
        
        print("Capability Metrics successfully captured")


        return {"shipment": shipment}


