from src.models.data_models import ShipmentModel
import numpy as np
import json
from ollama import chat
import asyncio 

HISTORY = {
    "phone": [1.2, 2.5, 0.8, 4.0, 3.2, 2.1, 1.5],
    "laptop": [1.5, 2.2, 1.8, 2.0],
    "industrial_items":[5.0, 10.0, 15.0, 20.0] # Specifically for the laptop check!
}



def statistical_audit(weight: float, category: str):
    category=category.lower()
    if category in HISTORY:
        data = HISTORY[category]
        mean = np.mean(data)
        std = np.std(data)
        z_score = abs((weight - mean) / std)
        
        # If Z > 3, it's a 99.7% outlier
        if z_score > 3:
            return False, z_score
    return True, 0.0

async def reflection_validator(agent_instance,weight,category,score:float,manifest_text)->dict:
    """
    The main agent logic: Extract -> Convert -> Enrich.
    """
    user_message = (
        f"The auditor flagged {weight}kg for '{category}' (Z-Score: {score:.2f}).\n"
        f"MANIFEST TEXT:\n\"\"\"{manifest_text}\"\"\"\n\n"
        "Task: Check the MANIFEST TEXT. Did the extractor misread a decimal? "
        "Is it a bulk shipment? Or is this weight actually a hallucination?\n"
        "Return JSON: {'decision': 'PASS'/'REJECT', 'reason': '...'}"
    )

    for attempt in range(2):
        try:
            # We invoke the LLM (Phi-3) to see if the manifest justifies the outlier
            print("running_Refelciton_validation")
            response = chat(model="phi3",messages=[{"role":"user","content":user_message}],)
            
            result= json.loads(response.content)
            return result
        
        except Exception as e:
            print(f"Phi-3 attempt {attempt+1} failed or gave bad JSON. Retrying...")
            if attempt == 1:
                # 2. FALLBACK: Try GPT-4o-mini if local model keeps failing
                print("Phi-3 failed twice. Falling back to Cloud LLM for validation.")
                resp = await agent_instance.llm.ainvoke(user_message)
                p_tokens = resp.usage_metadata.get('input_tokens', 0)
                c_tokens = resp.usage_metadata.get('output_tokens', 0)
                content = resp.content.replace("```json", "").replace("```", "").strip()
                resolution= json.loads(content)
                resolution["p_tokens"] = p_tokens
                resolution["c_tokens"] = c_tokens
            
                return resolution
               

