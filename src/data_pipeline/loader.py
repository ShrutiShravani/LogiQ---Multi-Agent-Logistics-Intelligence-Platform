import pandas as pd
import os 
import pandas as pd
import os 
from pathlib import Path

# Get the absolute path of the current file
BASE_DIR = Path(__file__).resolve().parent.parent.parent

def load_delivery(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Directory not found: {os.path.abspath(file_path)}")

   
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
        print(f"File {file_path} loaded successfully")
        print(df.head(5))
        return df  # RETURN the dataframe

    raise FileNotFoundError(f"No CSV file found in {file_path}")

