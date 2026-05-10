import mlflow
import numpy as np
import os
import fitz
from langchain_openai import ChatOpenAI
from src.agents.agents.document_processor import DocumentAgent
from src.agents.agents.validation import data_validator # Ensure correct import
import time

# 1. Define Ground Truth Labels for your 4 test PDFs
# This is how the script knows if the agent is "correct"
test_metadata = {
    "clean_waybill.pdf": {"flag": False, "action": "none"},
    "error_500kg.pdf": {"flag": True, "action": "human_review_required"},
    "outlier_heavy.pdf": {"flag": True, "action": "verified_outlier"},
    "invalid_data.pdf": {"flag": True, "action": "rejected"}
}

def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    return "".join([page.get_text() for page in doc])

def run_validation_test(pdf_files):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    doc_agent = DocumentAgent(llm_client=llm)
    validator_agent = data_validator()
    
    scores = []
    
    with mlflow.start_run(run_name="Agentic_Capability_Stress_Test"):
        for pdf_path in pdf_files:
            file_name = os.path.basename(pdf_path)
            if file_name not in test_metadata: continue
            
            truth = test_metadata[file_name]
            text = extract_text(pdf_path)
            
            # --- ATTEMPT 1 ---
            extract_res = doc_agent.process({
                "waybill_text": text, 
                "extraction_attempts": 0
            })
            val_res = validator_agent.validator_node(extract_res)
            
            # --- ATTEMPT 2 (Feedback Loop) ---
            if "feedback" in val_res:
                print(f"Refinement triggered for {file_name}: {val_res['feedback']}")
                res = doc_agent.process({
                    "waybill_text": text,
                    "feedback": val_res["feedback"],
                    "extraction_attempts": 1
                })
                val_res = validator_agent.validator_node(res)

            final_shipment = val_res["shipment"]

            # --- METRICS CALCULATION ---
            det_hit = (final_shipment.is_anomaly == truth["flag"])
            ver_hit = (final_shipment.audit_action == truth["action"])
            
            scores.append({"det": det_hit, "ver": ver_hit})
            mlflow.log_metrics({
                f"{file_name}_det_ok": 1 if det_hit else 0,
                f"{file_name}_ver_ok": 1 if ver_hit else 0
            })

        # Summary Metrics
        mlflow.log_metrics({
            "Detection_Recall": np.mean([s["det"] for s in scores]),
            "Verification_Precision": np.mean([s["ver"] for s in scores])
        })
        print("Success: Capability Metrics Logged to MLflow.")

if __name__ == "__main__":
    # Import your list from main or define it here
 
    run_validation_test(pdf_files)