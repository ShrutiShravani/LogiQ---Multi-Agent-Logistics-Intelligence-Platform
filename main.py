from src.agents.agents.critic_agent import CriticAgent
from src.agents.agents.document_processor import DocumentAgent
from src.agents.agents.pricing_agent import PricingAgent
from src.agents.agents.route_agent import RouteAgent
from src.agents.agents.validation import data_validator
from src.agents.agents.guardrail_agent import guardrail_agent
import fitz
from src.agents.agents.orchestrator import create_logisticsgraph
from openai import OpenAI
import os
import json
import mlflow
import glob
from langchain_openai import ChatOpenAI
from datetime import datetime,date
import numpy as np
import time
from src.utils.telemetry import  log_batch_summary,log_individual_shipment
import asyncio
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI","http://localhost:5000")
print(MLFLOW_TRACKING_URI)
if MLFLOW_TRACKING_URI != "local":
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment("Logistics_Pricing_New")

def extract_text(pdf_path):
        """Utility to turn the PDF file into a string the LLM can read"""
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        return text.strip()
       

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    # 1. Handle Dates and Times
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # 2. Handle Precision Weights (Decimal)
    if isinstance(obj, Decimal):
        return float(obj)
    
    # 3. FIX: Handle NumPy types (from DBSCAN/MLflow)
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist() # Convert arrays to lists
    
    # 4. Handle Pydantic ShipmentModels
    if isinstance(obj, BaseModel):
        return obj.model_dump()
        
    raise TypeError(f"Type {type(obj)} not serializable")


llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
    stream_usage=True,
    max_retries=3, # Automatic retries for rate limits/server errors
    timeout=30,
)

fallback_llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0,
    stream_usage=True,
    max_retries=3, # Automatic retries for rate limits/server errors
    timeout=30,
)

doc_agent = DocumentAgent(llm_client=llm,fallback_client=fallback_llm)
route_agent = RouteAgent()
pricing_agent = PricingAgent()
critic_agent = CriticAgent()
data_validation_agent= data_validator(llm_client=llm,fallback_client=fallback_llm)
security_gate=guardrail_agent(llm_client=llm,fallback_client=fallback_llm)
input_path= 'data/raw'


pdf_files = glob.glob(os.path.join(input_path,"*.pdf"))

stats_for_metrics = []
all_shipment_data=[]
all_audit_traces={}

    
async def run_waybill_task(app,pdf_path):
    client = mlflow.tracking.MlflowClient()
    with mlflow.start_run(run_name=f"Shipment_{os.path.basename(pdf_path)}", nested=True) as child:
        child_id_str = str(child.info.run_id)
        print(type(pdf_path))
        waybill_text = extract_text(pdf_path)
        initial_state = {
        "waybill_text": waybill_text,
        "pdf_path":pdf_path,
        "shipment": None,       
        "feedback": None,       
        "attempts": 0,  
        "extraction_attempts":0,
        "is_safe":False,
        "goto_dlq:bool":False,      
        "error_log": []      
        }
         
        # 4. Execute
        final_state = await app.ainvoke(initial_state)

        if final_state.get("goto_dlq"):
            mlflow.set_tag("status","failed_to_extract")
            return None

        shipment = final_state['shipment']

        doc_retries = final_state.get("extraction_attempts", 1) - 1
        val_retries = final_state.get("attempts", 1) - 1
    
        if final_state.get("goto_dlq") is True:
            is_verified=0
        else:
            is_verified=1
        
        client.log_metric(child_id_str, "doc_verified", is_verified)
        client.log_metric(child_id_str, "doc_retries", doc_retries)
        client.log_metric(child_id_str, "val_retries", val_retries)
        client.set_tag(child_id_str, "waybill_id", shipment.shipment_id)

        mlflow.set_tag("waybill_id", getattr(shipment, "shipment_id", "N/A"))
        return {"shipment":shipment,"state":final_state,"child_run_id":child_id_str}


async def main():
    # 2. Build the Graph
        app = create_logisticsgraph(security_gate,doc_agent,data_validation_agent)
        client = mlflow.tracking.MlflowClient()

        with mlflow.start_run(run_name="7_Waybill_Stress_Test")as parent_run:
            parent_id = parent_run.info.run_id
            start_time=time.time()
            all_processed_shipments = []
            total_shipments=len(pdf_files)
            tasks = [run_waybill_task(app,path) for path in pdf_files]

            # 3. EXECUTE: This is your worker queue in action
            processed_shipments = await asyncio.gather(*tasks)

            blocked_by_guardrail = [r for r in processed_shipments if r and r.get('is_safe') is False]

            valid_results = [r for r in processed_shipments  if r and r['shipment'] is not None and r['shipment'].is_verified]
            needs_review = [r['shipment'] for r in processed_shipments if r and r.get('shipment') and not r['shipment'].is_verified]

            all_processed_shipments = [r['shipment'] for r in valid_results]

        
            if not all_processed_shipments:
                print("No shipments were successfully processed.")
                return

            print(f"Routing Batch of {len(all_processed_shipments)}...")
            routed_list = route_agent.process_batch(all_processed_shipments)
            total_batch_revenue = 0.0
            cluster_operational_cost = 0.0
            total_verified = len(valid_results)
            # 5. Finalize Pricing
            for i,res in enumerate(valid_results):
                final_state =res['state']
                shipment = res['shipment']
                target_run_id = res['child_run_id']
                pricing_agent.process(shipment)
                critic_agent.process(shipment)
                all_shipment_data.append(shipment)
                

                if shipment.cluster_id!= "SINGLETON":
                    total_batch_revenue += shipment.predicted_base_price
                    print(total_batch_revenue)
                
                
                total_batch_latency = time.time() - start_time

                if hasattr(shipment, 'operational_cost') and shipment.operational_cost > 0:
                    # We only set this if we haven't found a cluster cost yet, 
                    # or if multiple clusters exist, you'd sum them.
                    cluster_operational_cost+= shipment.operational_cost
                print(cluster_operational_cost)

                
                with mlflow.start_run(run_id=target_run_id,nested=True):
                    log_individual_shipment(shipment)
                
           
                #calcualte theoretical price
                if shipment.operational_features:
                    theory_price= shipment.optimized_theoretical_price
                else:
                    theory_price = shipment.theoretical_price

                stats_for_metrics.append({
                    "pred": shipment.raw_model_prediction,
                    "actual_price": theory_price,
                    "overridden": any("Overriding"in trace and "Success" not in trace for trace in shipment.agent_trace)
                })
                print(stats_for_metrics)
                # Define the keys we want to extract from the Pydantic object
                keys_to_show = { 
                    "shipment_id",
                    "cluster_id",
                    "origin_address",
                    "destination_address",
                    "total_weight_kg",
                    "item_category",
                    "parcel_count",
                    "pickup_time",
                    "pickup_latitude",
                    "pickup_longitude",
                    "dropoff_latitude",
                    "dropoff_longitude",
                    "hour",
                    "day_of_week",
                    "is_rush_hour",
                    "is_holiday",  
                    "is_weekend",
                    "is_high_demand",
                    "traffic_density_score",
                    "distance_km",
                    "duration_min",
                    "predicted_base_price",
                    "final_market_price", 
                    "vehicle_type", 
                    "weather_condition",
                    "margin_savings",
                    "optimization_ratio",
                    "is_verified", 
                }

                # 5. Extract and Transform
                # Using a dictionary comprehension to pull data from the ShipmentModel object
                final_output = {k: getattr(shipment, k, "N/A") for k in keys_to_show}

                # Add Metadata & Formatting
                final_output["currency"] = "USD"

                # Safety check for duration_min before popping
                duration = final_output.pop("duration_min", 0)
                final_output["eta_minutes"] = duration if duration != "N/A" else 0

                final_output["status"] = "SUCCESS" if getattr(shipment, "is_verified", False) else "FAILED"
                
                final_output["system_errors"] = final_state.get("error_log", [])

                all_shipment_data.append(final_output)
                all_audit_traces[shipment.shipment_id] = shipment.agent_trace


            # --- AFTER THE LOOP: Calculate Batch Savings ---
            total_savings = round(total_batch_revenue-cluster_operational_cost ,2)
            optimzation_efficiency_gain = round((total_savings /cluster_operational_cost) * 100, 2) if total_batch_revenue > 0 else 0
            profit_margin_gain = round((total_savings /total_batch_revenue) * 100, 2) if total_batch_revenue > 0 else 0
            print(f"total_savings{total_savings},{optimzation_efficiency_gain}")

            client.log_metric(parent_id, "Batch_Total_Savings", total_savings)
            client.log_metric(parent_id, "Batch_Efficiency_Gain", optimzation_efficiency_gain)
            client.log_metric(parent_id, "profit_margin_gain", profit_margin_gain)
            client.log_metric(parent_id, "total_batch_latency", total_batch_latency)
    
            if stats_for_metrics:
                #calcualte mae
                MAE= sum(abs(r['pred']-r['actual_price']) for r in stats_for_metrics)/len(stats_for_metrics)

                #calcualte oevrrides count
                overrides_count= sum(1 for r in stats_for_metrics if r['overridden'])
                print(f"override_count:{overrides_count}")
                print(len(stats_for_metrics))
                overrides_rate= (overrides_count/len(stats_for_metrics))* 100

                verified_rate=(total_verified /total_shipments) * 100
                client.log_metric(parent_id, "Batch_Verification_Rate", verified_rate)
                client.log_metric(parent_id, "MAE_PRICE", round(MAE, 2))
                client.log_metric(parent_id, "Critic_Override_Percent", round(overrides_rate, 2))
                client.log_param(parent_id, "total_test_cases", len(pdf_files))
                client.log_param(parent_id, "model_version", "xgboost_v1")

                print(f"test_complete:{MAE},Override rate:{overrides_rate}%")

                
                # 4. BATCH TELEMETRY: Calculate P95, P96, P99
                log_batch_summary(all_processed_shipments,client, parent_id)
                client.log_metric(parent_id,"total_verified_shipments",len(all_processed_shipments))
                client.log_metric(parent_id,"blocked_by_guardrail",len(blocked_by_guardrail))
                client.log_metric(parent_id,"total_failed_shipments",len(needs_review))
                


                if overrides_rate>30.0:
                    mlflow.set_tag("alert", "Potential_Model_Drift_Detected")
                    print("WARNING: High override rate detected. Model may require retraining.")

                serializable_data=[s.model_dump() if hasattr(s,'model_dump') else s for s in all_shipment_data]

                with open("batch_results.json", "w") as f:
                    json.dump(serializable_data, f, indent=4,default=json_serial)
                with open("batch_full_audit.json","w") as f:
                    json.dump(all_audit_traces,f,indent=4)
            
                print("started")
      


if __name__=="__main__":
    asyncio.run(main())