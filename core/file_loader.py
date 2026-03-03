from Pathlib import Path
from openai import OpenAI
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import json

def file_load(self,file_path):
    """load nay format (csv,xls,json and return Dataframe"""

    file_path=str(file_path)

    if file_path.endswith("csv"):
        return pd.read_csv(file_path,nrows=1000)
    elif file_path.endswith('.xlsx'):
        return pd.read_excel(file_path,nrows=1000)
    elif file_path.endswith('.json'):
        with open(file_path)as f:
            data=json.load(f)

            if isinstance(data,dict):
                flat_data=[]
                for key,value in list(data.items()):
                    if isinstance(value,list):
                        for item in value[:10]:
                            item_copy=item.copy()
                            item_copy['_group']=key
                            flat_data.append(item_copy)
                return pd.DataFrame(flat_data)
            else:
                return pd.DataFrame(data[:1000])
    else:
        raise ValueError(f"Unsupported format: {file_path}")
    