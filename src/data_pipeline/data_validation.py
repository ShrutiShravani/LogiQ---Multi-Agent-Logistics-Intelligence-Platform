import pandas as pd
import numpy as np
import yaml
import os
from datetime import datetime
import json

class NYCValidator:
    def __init__(self,df, schema_path="config/schema.yaml"):
        self.results = {}
        self.df= df
        
        # Define columns from your specific schema
        self.critical = [
            'id', 'pickup_datetime', 'dropoff_datetime', 'pickup_longitude', 
            'pickup_latitude', 'dropoff_longitude', 'dropoff_latitude', 'trip_duration'
        ]
        self.important = ['vendor_id', 'passenger_count', 'store_and_fwd_flag']

    def run_validation(self):
        print("--- Starting Senior Project Validation (NYC Dataset) ---")
        
        # 1. Structural Check (Critical & Important Presence)
        all_req = self.critical + self.important
        found_cols = [c for c in all_req if c in self.df.columns]
        self.results['structural_pct'] = len(found_cols) / len(all_req)
        
        # 2. Critical Null Check (Pricing cannot have NaNs)
        # If any critical column is null, that row is useless for training.
        critical_nulls = self.df[self.critical].isnull().any(axis=1).sum()
        self.results['clean_rows_pct'] = (len(self.df) - critical_nulls) / len(self.df)

        # 3. Geo-Fencing (NYC Bounds Accuracy)
        # Real NYC coords: Lat (40.5 - 40.9), Lng (-74.2 - -73.7)
        # Outliers here represent GPS errors that will skew distance/pricing.
        lat_valid = self.df['pickup_latitude'].between(40.0, 42.0)
        lng_valid = self.df['pickup_longitude'].between(-75.0, -73.0)
        self.results['geo_accuracy'] = (lat_valid & lng_valid).mean()

        # 4. Temporal Logic (The "Anti-Cheat" Check)
        # Ensure trip_duration matches the timestamp delta
        self.df['pickup_datetime'] = pd.to_datetime(self.df['pickup_datetime'])
        self.df['dropoff_datetime'] = pd.to_datetime(self.df['dropoff_datetime'])
        actual_delta = (self.df['dropoff_datetime'] - self.df['pickup_datetime']).dt.total_seconds()
        
        # Accuracy check: Allow 10s variance for system lag
        time_consistency = (np.abs(actual_delta - self.df['trip_duration']) < 10).mean()
        self.results['time_consistency'] = time_consistency

        return self.display_report()

    def display_report(self):
        score = np.mean(list(self.results.values())) * 100
        print(f"1. Structural Integrity: {self.results['structural_pct']*100:.1f}%")
        print(f"2. Data Completeness:   {self.results['clean_rows_pct']*100:.1f}%")
        print(f"3. Geo-Spatial Bounds:  {self.results['geo_accuracy']*100:.1f}%")
        print(f"4. Temporal Logic:      {self.results['time_consistency']*100:.1f}%")
        print(f"--- TOTAL QUALITY SCORE: {score:.2f}% ---")
        self.results['total_score'] = score
        return self.results  

if __name__ == "__main__":
    # Ensure this points to your CLEANED file from the preprocessor
    raw_path = r"data\raw\train.csv"
    
    if os.path.exists(raw_path):
        # Load data first
        raw_df = pd.read_csv(raw_path)
        validator=NYCValidator(raw_df,)
        report_data=validator.run_validation()
        os.makedirs("logs", exist_ok=True)
        report_path = f"logs/unified_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        print(f"Report saved to {report_path}")
    
   

