import os
import json
import asyncio
from src.agents.agents.orchestrator import create_logisticsgraph
from src.agents.agents.pricing_agent import PricingAgent
from src.agents.agents.critic_agent import CriticAgent
from src.agents.agents.guardrail_agent import guardrail_agent
from src.agents.agents.document_processor import DocumentAgent
from src.agents.agents.validation import data_validator
from src.agents.agents.route_agent import RouteAgent
from langchain_openai import ChatOpenAI
import fitz

llm = ChatOpenAI(
    model="gpt-4o-mini", 
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
    stream_usage=True,
    max_retries=3, # Automatic retries for rate limits/server errors
    timeout=30,
)

test_folder="data/transformed"
doc_agent = DocumentAgent(llm_client=llm)
route_agent = RouteAgent()
pricing_agent = PricingAgent()
critic_agent = CriticAgent()
data_validation_agent= data_validator(llm_client=llm)
security_gate=guardrail_agent(llm_client=llm)


THRESHOLDS = {
    "MAX_OVERRIDE_RATE": 15.0,  # Fails if more than 15% need correction
    "MAX_MAE": 10.0,            # Fails if average price error > $10
    "MIN_VERIFICATION": 90.0    # Fails if extraction fails on > 10% of files
}

def extract_text(pdf_path):
        """Utility to turn the PDF file into a string the LLM can read"""
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        return text.strip()
       

async def run_regression():
    print("Starting Pricing Regression Test...")
    pdf_files=[file for file in os.listdir(test_folder) if file.endswith(".pdf")]
    
    stats_for_metrics = []
    total_files = len(pdf_files)
    logistics_app = create_logisticsgraph(security_gate,doc_agent,data_validation_agent)

    for file in pdf_files:
        #read file content
        file_path=os.path.join(test_folder,file)
       
        waybill_text= extract_text(file_path)

        #intialize state
        initial_state={
                "waybill_text": waybill_text,
                "shipment": None,       
                "feedback": None,       
                "attempts": 0,        
                "error_log": []      
        }
       
        final_state = await logistics_app.ainvoke(initial_state)
        shipment = final_state['shipment']

        guardrail_blocks = 0
        #we look for the guardrail failure
        is_blocked = final_state.get("is_safe") 
        if is_blocked:
            guardrail_blocks += 1
            print(f"Guardrail blocked file: {file}")

        else:
            print(f"Guardrail passed file: {file}")
            

        if shipment:
            # Route agent usually adds distance_km and duration_min
            # Since it's a single shipment, we pass it in a list or use a single-item method
            route_agent.process_batch([shipment]) 
            
            pricing_agent.process(shipment)
            critic_agent.process(shipment)
            
            if shipment.operational_features:
                    theory_price= shipment.optimized_theoretical_price
            else:
                theory_price = shipment.theoretical_price

            stats_for_metrics.append({
                "pred": shipment.raw_model_prediction,
                "actual_price": theory_price,
                "overridden": any("Overriding"in trace and "Success" not in trace for trace in shipment.agent_trace)
            })

    
    Guardrail_rate= (guardrail_blocks/total_files)* 100
    print(f"Guardrail rate: {Guardrail_rate:.2f}%")
    print(f"Guardrail blocks: {guardrail_blocks}")
    print(f"Total files: {total_files}")

    if not stats_for_metrics:
        print("No shipments were successfully processed.")
        return False

    MAE= sum(abs(r['pred']-r['actual_price']) for r in stats_for_metrics)/len(stats_for_metrics)

    
    #calcualte oevrrides count
    overrides_count= sum(1 for r in stats_for_metrics if r['overridden'])
    print(f"override_count:{overrides_count}")
    print(len(stats_for_metrics))
    overrides_rate= (overrides_count/len(stats_for_metrics))* 100

    
    print(f"\n--- Regression Results ---")
    print(f"MAE: ${MAE:.2f} (Threshold: ${THRESHOLDS['MAX_MAE']})")
    print(f"Override Rate: {overrides_rate:.2f}% (Threshold: {THRESHOLDS['MAX_OVERRIDE_RATE']}%)")
    print(f"test_complete:{MAE},Override rate:{overrides_rate}%")

    errors=[]
    if MAE>THRESHOLDS["MAX_MAE"]:
        errors.append(f"MAE Threshold Exceeded: {MAE:.2f} > {THRESHOLDS['MAX_MAE']:.2f}")
    if overrides_rate>THRESHOLDS["MAX_OVERRIDE_RATE"]:
        errors.append(f"Override Rate Threshold Exceeded: {overrides_rate:.2f}% > {THRESHOLDS['MAX_OVERRIDE_RATE']:.2f}%")

    if errors:
        print("\n--- Regression Failed ---")
        print("\n".join(errors))
        return False
    else:
        print("\n--- Regression Passed ---")
        return True


if __name__=="__main__":
    asyncio.run(run_regression())