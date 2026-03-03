import json
import os
from pathlib import Path
import pandas as pd
from pandas.core.groupby.ops import extract_result
from core.file_loader import file_load
import load_dotenv
import os
from core.file_loader import file_load
load_dotenv()

class UnderstandAgent:
    def __init__(self,api_key=None):
        """Initialize with OpenAI (or Anthropic)"""
        self.client = os.getenv("OPENAI_API_KEY")
        self.file_path=""
        self.file_load = file_load(self.file_path)
        self.mapping_memory = {}  
    
    def analzye_file(self):
        """udnerstand single file"""
        df= self.file_load(self.file_path)
        # Prepare file info
        file_info = {
            "filename": Path(self.file_path).name,
            "format": Path(self.file_path).suffix,
            "rows": len(df),
            "columns": list(df.columns),
            "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "sample_rows": df.head(3).to_dict(orient='records'),
            "missing_values": df.isnull().sum().to_dict(),
            "numeric_stats": df.describe().to_dict() if len(df.select_dtypes(include='number').columns) > 0 else {}
        }


        #create prompt for llm
        prompt=f"""
          You are a data expert. Analyze this file and provide a detailed profile.

          FILE INFORMATION:
            - Name: {file_info['filename']}
            - Format: {file_info['format']}
            - Rows: {file_info['rows']}
            - Columns: {file_info['columns']}

             DATA TYPES:
        {json.dumps(file_info['data_types'], indent=2)}

        SAMPLE DATA (first 3 rows):
        {json.dumps(file_info['sample_rows'], indent=2)}

        MISSING VALUES:
        {json.dumps(file_info['missing_values'], indent=2)}

        Please provide:
        1. DOMAIN: What type of data is this? (retail, finance, IoT, healthcare, etc.)
        2. DESCRIPTION: What does this dataset represent?
        3. COLUMN MEANINGS: For each column, explain what it likely represents
        4. DATA QUALITY: Any issues you notice? (missing values, outliers, inconsistencies)
        5. TIME COVERAGE: If there's a date column, what time period?
        6. USE CASES: What could this data be used for?
        7. POTENTIAL CHALLENGES: What might be difficult to work with?

        Format your response in clear sections.
        """

        #ge llm response
        response= self.client.chat_completions.create(
              model="gpt-3.5-turbo",  # or "gpt-4" if you have access
            messages=[
                {"role": "system", "content": "You are a data analysis expert. Provide clear, accurate insights."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        analysis= response.choices[0].message.content

        return {
            "file_info": file_info,
            "analysis": analysis
        }
    
    def compare_files(self,file_path1,file_path2):
        """Phase 1 Week 2: Compare two files and suggest mappings"""
        
        # Load both files
        df1 = self.load_file(file_path1)
        df2 = self.load_file(file_path2)

        #prepare compariosn_info={
        comparison_info={

        "file1": {
                "name": Path(file_path1).name,
                "columns": list(df1.columns),
                "sample": df1.head(2).to_dict(orient='records')
            },
            "file2": {
                "name": Path(file_path2).name,
                "columns": list(df2.columns),
                "sample": df2.head(2).to_dict(orient='records')
            }
        }

        cache_key = f"{Path(file_path1).name}_{Path(file_path2).name}"
        if cache_key in self.mapping_memory:
            return self.mapping_memory[cache_key]
        
        prompt = f"""
        Compare these two files and determine if they contain similar data.

        FILE 1: {comparison_info['file1']['name']}
        Columns: {comparison_info['file1']['columns']}
        Sample: {json.dumps(comparison_info['file1']['sample'], indent=2)}

        FILE 2: {comparison_info['file2']['name']}
        Columns: {comparison_info['file2']['columns']}
        Sample: {json.dumps(comparison_info['file2']['sample'], indent=2)}

        Please answer:
        1. Are these files the same TYPE of data? (e.g., both sales, both customer data, etc.)
        2. If yes, suggest column mappings from File 2 to File 1
        3. What transformations would be needed to unify them?
        4. Confidence level (0-100%) in your mapping

        Format as JSON:
        {{
            "same_type": true/false,
            "data_type": "what kind of data",
            "mappings": {{"file2_column": "file1_column"}},
            "transformations": ["step1", "step2"],
            "confidence": 85,
            "reasoning": "explanation"
        }}
        """

        response= self.client.chat_completions.create(
            model= "gpt-3.5-tubro",
            messages=[
                {"role":"system","content":"You are a data integrtaione xpert.Provide acuurate mappings"},
                {"role":"user","content":prompt}
            ],
            response_format={"type":"json_object"}

        )

        result=json.loads(response.choices[0].message.content)

        #store in memory
        self.mapping_memory[cache_key]=result

        return result
    
    def save_mapping(self,file_name1,file_name2,mapping):
        """Persist mapping for future use"""
        memory_file = "data/mapping_memory.json"

        if Path(memory_file).exists():
            with open(memory_file)as f:
                memory= json.load(f)
        
        else:
            memory={}
        
        #save new mapping
        key= f"{file_name1}_{file_name2}"

        memory[key]={
             "mapping": mapping,
            "timestamp": str(pd.Timestamp.now()),
            "file1": file_name1,
            "file2": file_name2
        }

        with open(memory_file,"w") as f:
            json.dump(memory,f,idnent=2)
        
        print(f"Mapping saved to {memory_file}")

def run_agent():
    agent=UnderstandAgent()
    agent.file_path="data\Uci\Online Retail.xlsx"
    agent.file_load= file_load(agent.file_path)
    print(agent.analyze_file())
    agent.compare_files(r"data\Olist\olist_customers_dataset.csv","data\Olist\olist_orders_dataset.csv")
    agent.save_mapping(r"data\Olist\olist_customers_dataset.csv",r"data\Olist\olist_orders_dataset.csv",agent.compare_files(r"data\Olist\olist_customers_dataset.csv",r"data\Olist\olist_orders_dataset.csv"))
    print(agent.mapping_memory)

if __name__=="__main__":

    run_agent()



    
