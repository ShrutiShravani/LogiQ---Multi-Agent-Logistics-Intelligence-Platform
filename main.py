from fastapi import FastAPI, UploadFile
from agent.understand_agent import UnderstandAgent
from core.file_loader import file_load

app = FastAPI()

@app.post("/upload_file")
async def upload_file(file: UploadFile = File(...)):
    agent=UnderstandAgent()
    agent.file_path=file.filename
    agent.file_load= file_load(agent.file_path)



# main.py
validator = DataValidator(df, "pickup")
report = validator.run_all_checks()

if report['results']['missing']['is_rejected']:
    print(f"!!! PIPELINE HALTED: {report['results']['missing']['status']}")
    # Log the failure and exit. Do NOT call Transformer or Feature Engineering.
    sys.exit(1) 
else:
    # Only if not rejected, we move to the next senior project stages
    transformer = DataTransformer(df)
    clean_df = transformer.transform()
    
    features = FeatureEngineer(clean_df)
    final_data = features.build_pricing_features()