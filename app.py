from src.agents.agents.critic_agent import CriticAgent
from src.agents.agents.document_processor import DocumentAgent
from src.agents.agents.pricing_agent import PricingAgent
from src.agents.agents.route_agent import RouteAgent
import fitz
from src.agents.agents.orchestrator import create_logisticsgraph
from dotenv import load_dotenv
import os
import asyncio
import json
from langchain_openai import ChatOpenAI
from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn
import time
import sys
from datetime import datetime
import mlflow
from collections import deque
import numpy as np
from src.agents.agents.validation import data_validator
from src.agents.agents.guardrail_agent import guardrail_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from contextlib import asynccontextmanager
import json
from psycopg.types.json import Json
from fastapi import Header
from src.models.data_models import ShipmentModel
import selectors
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime,date


load_dotenv()
checkpointer = None
DB_URI = "postgresql://user:password@localhost:5432/logistics_db"
pool = AsyncConnectionPool(conninfo=DB_URI, open=False)
PARENT_RUN_ID = None



@asynccontextmanager
async def lifespan(app: FastAPI):
    global PARENT_RUN_ID,checkpointer, logistics_app
    """
    try:
        with psycopg.connect(DB_URI, autocommit=True) as conn:
            # We pass the raw connection to a temporary checkpointer for setup
            from langgraph.checkpoint.postgres import PostgresSaver
            setup_saver = PostgresSaver(conn)
            setup_saver.setup()
            print("LangGraph Checkpointer tables verified/created.")
    except Exception as e:
        print(f"Checkpointer setup failed: {e}")
        # We continue anyway, or you can raise e if it's critical
    """
    await pool.open()
    # 2. Initialize the checkpointer
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    
    logistics_app = create_logisticsgraph(
        security_gate, 
        doc_agent, 
        data_validation_agent, 
        checkpointer=checkpointer
    )

    with mlflow.start_run(run_name="Logistics_Intelligence_Service") as parent_run:
        PARENT_RUN_ID = parent_run.info.run_id
        mlflow.set_tag("version", "1.0.0")
        print(f"MLflow Parent Run Started: {PARENT_RUN_ID}")
        yield
  
    await pool.close()

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

async def save_to_staged(shipment_obj, user_id):
    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            shipment_dict = shipment_obj.model_dump()
            clean_json_str= json.dumps(shipment_dict,default=json_serial)
            
            # Ensure the query matches the 3 placeholders exactly
            query = """
            INSERT INTO staged_shipments (shipment_id, data, user_id) 
            VALUES (%s, %s, %s)
            ON CONFLICT (shipment_id) DO UPDATE SET 
                data = EXCLUDED.data,
                user_id = EXCLUDED.user_id;
            """
            # user_id MUST be the third item in this tuple!
            await cursor.execute(query, (shipment_obj.shipment_id, clean_json_str, user_id))
          
async def fetch_staged(user_id):
    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT data FROM staged_shipments WHERE status='staged' AND user_id=%s", (user_id,))
            rows=await cursor.fetchall()

            #turn raw json into shipment modle objects
            return [ShipmentModel.model_validate(row[0]) for row in rows]


override_window = deque(maxlen=100)
failure_window = deque(maxlen=100)
app = FastAPI(title="LogiQ Logistics Intelligence API",lifespan=lifespan)


llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY")
)

fallback_llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0,
    stream_usage=True,
    max_retries=3, # Automatic retries for rate limits/server errors
    timeout=30,
)

doc_agent = DocumentAgent(llm_client=llm, fallback_client=fallback_llm)
data_validation_agent = data_validator(llm_client=llm, fallback_client=fallback_llm)
security_gate = guardrail_agent(llm_client=llm, fallback_client=fallback_llm)

# Post-Graph Agents
route_agent = RouteAgent()
pricing_agent = PricingAgent()
critic_agent = CriticAgent()

input_path= 'data/raw'


MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI","http://localhost:5000")
if MLFLOW_TRACKING_URI != "local":
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment("Logistics_API_Live")


def extract_text(content:bytes):
    """Utility to turn the PDF file into a string the LLM can read"""
    doc = fitz.open(stream=content,filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

logistics_app = create_logisticsgraph(security_gate, doc_agent, data_validation_agent,checkpointer=checkpointer)

#api endpoints
@app.get("/health")
def healthcheck():
    return {"status":"healthy","model":"gpt-40-mini"}
@app.get("/")
def home():
    return {"status": "success", "message": "Pricing API is running without MLflow!"}

@app.post("/upload_shipment")
async def process_Waybill(file: UploadFile = File(...),x_user_id: str = Header(default="guest_user")):
    try:
        start_time = time.time()
        LANDING_DIR="data/landing"
        os.makedirs(LANDING_DIR,exist_ok=True)
        temp_pdf_path = os.path.join(LANDING_DIR, file.filename)
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400,detail="Only pdf files s are supported.")

        pdf_bytes = await file.read()
        with open(temp_pdf_path,"wb") as f:
            f.write(pdf_bytes)

        #read file content
        waybill_text= extract_text(pdf_bytes)

        #intialize state
        initial_state={
                "waybill_text": waybill_text,
                "pdf_path": temp_pdf_path ,
                "shipment": None,       
                "feedback": None,       
                "attempts": 0,
                "extraction_attempts":0,        
                "error_log": [],
                "is_safe": False,           # Initialized as False
                "goto_dlq": False,          # Initialized as False
                "guardrail_latency": 0,     # Default to 0
                "guardrail_prompt_tokens": 0,
                "guardrail_completion_tokens": 0,
                "guardrail_cost_usd": 0.0    
        }

        run_id = f"shipment_{int(time.time())}"

        # Define the config with thread_id for Postgres
        config = {"configurable": {"thread_id": run_id}}

        final_state =await logistics_app.ainvoke(initial_state,config=config)
        shipment = final_state['shipment']
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        await save_to_staged(shipment,x_user_id)
        latency = time.time() - start_time

        
        with mlflow.start_run(run_name=f"Extracted_{shipment.shipment_id}", nested=True):
            mlflow.log_param("status", "staged")
            mlflow.log_metric("latency",latency)
    
        return {"shipment_id": shipment.shipment_id, "status": "staged","owner": x_user_id}

        
    except  Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"CRITICAL ERROR:\n{error_details}")
        with mlflow.start_run(run_name="Document not saved",nested=True):
            mlflow.log_param("error", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run-optimization")
async def run_optimization(user_id:str):
    start_time = time.time()
    
    # 1. Fetch from DB
    valid_results = await fetch_staged(user_id) 
    if not valid_results:
        return {"status": "error", "message": "No shipments found to optimize"}

    # Extract shipment objects for the route agent
    all_processed_shipments = valid_results

    # 2. RUN ROUTE AGENT
    route_agent.process_batch(all_processed_shipments)

    # Initialize batch counters
    total_batch_revenue = 0.0
    cluster_operational_cost = 0.0
    stats_for_metrics = []
    all_shipment_output = []

    # 3. PRICING LOOP
    for shipment in valid_results:  
        pricing_agent.process(shipment)
        critic_agent.process(shipment)

        # Revenue is what we would have charged WITHOUT optimization
        total_batch_latency = time.time() - start_time
        if shipment.cluster_id != "SINGLETON":
            total_batch_revenue += shipment.predicted_base_price
            
        # Operational cost is the actual cost after clustering
        if hasattr(shipment, 'operational_cost') and shipment.operational_cost > 0:
            cluster_operational_cost += float(shipment.operational_cost)
     

        # Logic for MAE (Accuracy)
        theory_price = (shipment.optimized_theoretical_price 
                        if shipment.operational_features 
                        else shipment.theoretical_price)
      
        is_overridden = any("Overriding" in trace and "Success" not in trace 
                            for trace in shipment.agent_trace)
        
        stats_for_metrics.append({
            "pred": shipment.raw_model_prediction,
            "actual_price": theory_price,
            "overridden": is_overridden
        })

        # --- Extraction Logic ---
        keys_to_show = { 
            "shipment_id","cluster_id","origin_address", "destination_address",
            "total_weight_kg", "item_category", "parcel_count",
            "pickup_time", "distance_km", "duration_min",
            "predicted_base_price", "final_market_price", 
            "vehicle_type", "margin_savings","operational_cost","is_verified","agent_trace"
        }

        # Pull data and fix NumPy types for JSON
        final_output = {}
        for k in keys_to_show:
            val = getattr(shipment, k, "N/A")
            if isinstance(val, (np.float32, np.float64)):
                val = float(val)
            elif isinstance(val, (np.int32, np.int64)):
                val = int(val)
            final_output[k] = val

        final_output["currency"] = "USD"
        final_output["status"] = "SUCCESS" if getattr(shipment, "is_verified", False) else "FAILED"
        
        # IMPORTANT: Append to the output list!
        all_shipment_output.append(final_output)

    # --- 4. BATCH CALCULATIONS ---
    print(cluster_operational_cost)
    print(total_batch_revenue)
        

    total_savings = round(total_batch_revenue - cluster_operational_cost, 2)
    efficiency_gain = round((total_savings / cluster_operational_cost * 100), 2) if total_batch_revenue > 0 else 0
    margin_gain = round((total_savings / total_batch_revenue * 100), 2) if total_batch_revenue > 0 else 0
    
    mae_price = (sum(abs(r['pred'] - r['actual_price']) for r in stats_for_metrics) / len(stats_for_metrics) 
                 if stats_for_metrics else 0)

    # --- 5. LOG TO MLFLOW ---
    with mlflow.start_run(run_id=PARENT_RUN_ID,nested=True):
        mlflow.log_metric("latency",total_batch_latency)
        mlflow.log_metric("Batch_Total_Savings", total_savings)
        mlflow.log_metric("Batch_Efficiency_Gain", efficiency_gain)
        mlflow.log_metric("MAE_PRICE", round(mae_price, 2))
        
        overrides_rate = (sum(1 for r in stats_for_metrics if r['overridden']) / len(stats_for_metrics)) * 100
        print(overrides_rate)
        if overrides_rate > 30.0:
            mlflow.set_tag("alert", "High_Override_Rate")

    return {
        "status": "SUCCESS",
        "batch_metrics": {
            "total_savings": float(total_savings),
            "efficiency_gain_percent": f"{float(efficiency_gain)}%",
            "profit_margin_gain_percent": f"{float(margin_gain)}%",
            "mae": round(float(mae_price), 2)
        },
        "shipments": all_shipment_output
    }
        
if __name__ == "__main__":
    if sys.platform == 'win32':
        selector = selectors.SelectSelector()
        loop = asyncio.SelectorEventLoop(selector)
        asyncio.set_event_loop(loop)
 
    config=uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop="asyncio")
    server = uvicorn.Server(config)

    #runs erve ron manually configured loop
    loop.run_until_complete((server.serve()))


        




