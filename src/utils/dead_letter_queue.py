import os
import json
import shutil
from datetime import datetime

DLQ_PATH = "data/dlq"
os.makedirs(DLQ_PATH, exist_ok=True)

QUARANTINE_DIR = os.path.join(DLQ_PATH, "quarantine")
os.makedirs(QUARANTINE_DIR,exist_ok=True) # For viruses/corrupt files
manifest_path= os.path.join(QUARANTINE_DIR,"dlq_manifest.json")


def send_to_dlq(pdf_path,reason):
    # For viruses/corrupt files
    filename = os.path.basename(pdf_path)
    destination = QUARANTINE_DIR
  
    
    if os.path.exists(pdf_path):
        shutil.move(pdf_path, destination)
    entry={
        "filename": filename,
        "original_path": pdf_path,
        "moved_at": datetime.now().isoformat(),
        "reason": reason
        
    }

    with open(manifest_path ,"a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"ALERT: Shipment moved to DLQ. Reason: {reason}")