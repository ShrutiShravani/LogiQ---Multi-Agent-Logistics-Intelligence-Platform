from traceback import print_stack
import numpy as np
import pandas as pd
import os
import pickle
import json

class NYCFeatureEngineer:
    def __init__(self, df):
        self.df = df.copy()

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        r = 6371 
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return 2 * r * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    def calculate_logistics_price(self, df):
        vehicle_base = {'e-scooter': 2.0, 'bicycle': 3.0, 'van': 15.0, 'truck': 45.0}
        vehicle_km_rate = {'e-scooter': 0.5, 'bicycle': 1.0, 'van': 2.5, 'truck': 5.0}
        
        df['base_cost'] = df['vehicle_type'].map(vehicle_base)
        df['km_rate'] = df['vehicle_type'].map(vehicle_km_rate)
        
        surge = 1.0 + (df['is_rush_hour'] * 0.3) + (df['is_weekend'] * 0.15)
        df['congestion_multiplier'] = df['traffic_density_score'].apply(lambda x: 1.2 if x < 0.5 else 1.0)
        
        df['target_price'] = (df['base_cost'] + 
                              (df['distance_km'] * df['km_rate']) +  (df['passenger_count'] * 1.50)+
                              (df['duration_min'] * 0.2)) * surge * df['congestion_multiplier']
        return df.round({'target_price': 2})

    def transform(self):
        print("Executing Senior Logistics Transformation...")
        
        # 1. Spatial & Temporal Features
        self.df['distance_km'] = self.haversine_distance(
            self.df['pickup_latitude'], self.df['pickup_longitude'],
            self.df['dropoff_latitude'], self.df['dropoff_longitude']
        )
        self.df['pickup_datetime'] = pd.to_datetime(self.df['pickup_datetime'])
        self.df['hour'] = self.df['pickup_datetime'].dt.hour
        self.df['day_of_week'] = self.df['pickup_datetime'].dt.dayofweek
        
        # Handle Duration (Only exists in train)
        if 'trip_duration' in self.df.columns:
            self.df['duration_min'] = self.df['trip_duration'] / 60
            self.df['actual_speed_kmh'] = self.df['distance_km'] / (self.df['duration_min'] / 60 + 0.001)
            hour_avg_speed = self.df.groupby('hour')['actual_speed_kmh'].transform('mean')
            self.df['traffic_density_score'] = (self.df['actual_speed_kmh'] / hour_avg_speed).round(2)
        
        # 2. Cleanup
        if 'store_and_fwd_flag' in self.df.columns:
            self.df.drop(columns=['store_and_fwd_flag'], inplace=True)

        # 3. Feature Engineering
        self.df['is_rush_hour'] = ((self.df['day_of_week'] < 5) & 
                                   ((self.df['hour'].between(8, 10)) | 
                                    (self.df['hour'].between(16, 19)))).astype(int)
        self.df['is_weekend'] = (self.df['day_of_week'] >= 5).astype(int)

        # 4. Vehicle Selection
        conditions = [
            (self.df['distance_km'] <= 2.0),
            (self.df['distance_km'] > 2.0) & (self.df['distance_km'] <= 5.0),
            (self.df['distance_km'] > 5.0) & (self.df['distance_km'] <= 15.0),
            (self.df['distance_km'] > 15.0)
        ]
        choices = ['e-scooter', 'bicycle', 'van', 'truck']
        self.df['vehicle_type'] = np.select(conditions, choices, default='van')

        # 5. Pricing
        self.df = self.calculate_logistics_price(self.df)
        
        # 6. Prepare Lookup and Encoding
        stats = self.df.groupby(['day_of_week', 'hour']).agg({
            'actual_speed_kmh': 'mean',
            'traffic_density_score': 'mean'
        }).to_dict('index')

        #convert vehicles type to 0/1 integers
        self.df = pd.get_dummies(self.df, columns=['vehicle_type'], prefix='type',dtype=int)
        cols= [c for c in self.df.columns if c!='target_price'] + ['target_price']
        self.df=self.df[cols]
        cols_to_drop=['id', 'vendor_id', 'pickup_datetime', 'actual_speed_kmh','dropoff_datetime', "trip_duration",# Raw strings
        'base_cost', 'km_rate', 'congestion_multiplier']
        self.df=self.df.drop(columns=cols_to_drop)
        print(list(self.df.columns))
        return self.df, stats

if __name__ == "__main__":
    # Load raw training data
    df_raw = pd.read_csv(r"data\raw\train.csv")
    
    engineer = NYCFeatureEngineer(df_raw)
    df_transformed, traffic_map = engineer.transform()
    
    # Save folder
    os.makedirs("data/transformed", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    
    # save CSV for Training
    df_transformed.to_csv("data/transformed/train_final.csv", index=False)
    

    # Save the Engineer Object as .pkl (optional, but good practice)
    with open("data/transformed/feature_engineer.pkl", "wb") as f:
        pickle.dump(engineer, f)\
        
    serializable_traffic_map = {f"{k[0]}_{k[1]}": v for k, v in traffic_map.items()}
        
    with open("data/transformed/traffic_mapping.json","w") as f:
        json.dump(serializable_traffic_map, f, indent=4)

    print("Done! CSV, JSON Lookup, and Pickle saved.")

    """
    1)complete data pipeline dvc2
    2)mole trianing mlflow mdoel verosining regsirty
    3)tets data raw upload na tranform4
    4)main.py end print_stack
    5)rest pahse 1 setup
    """