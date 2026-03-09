import numpy as np
import pandas as pd
import os
import pickle
import json
import holidays


class NYCFeatureEngineer:
    def __init__(self, df):
        self.df = df.copy()
        # FIX: Simulate weights that actually cross our vehicle thresholds
        if 'total_weight_kg' not in self.df.columns:
            # 80% light/medium (1-50kg), 20% heavy (50-600kg)
            weights = np.where(
                np.random.rand(len(self.df)) < 0.8,
                np.random.uniform(1, 50, size=len(self.df)),
                np.random.uniform(50, 600, size=len(self.df))
            )
            self.df['total_weight_kg'] = weights
        self.us_holidays = holidays.US(state='NY')
       
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        r = 6371 
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return 2 * r * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    def calculate_logistics_price(self, df):
        # Base rates aligned with vehicle capacity
        vehicle_base = {'e_scooter': 2.0, 'bicycle': 3.0, 'van': 15.0, 'truck': 45.0}
        vehicle_km_rate = {'e_scooter': 0.5, 'bicycle': 1.0, 'van': 2.5, 'truck': 5.0}
        
        df['base_cost'] = df['vehicle_type'].map(vehicle_base)
        df['km_rate'] = df['vehicle_type'].map(vehicle_km_rate)
        
        # SURGE: Economic Pressure (Rush, Weekend, or Holiday)
        surge = 1.0 + (df['is_rush_hour'] * 0.2) + (df['is_weekend'] * 0.15) + (df['is_holiday'] * 0.4)
        
        # CONGESTION: Physical Reality (If speed is < 50% of average)
        df['congestion_multiplier'] = df['traffic_density_score'].apply(lambda x: 1.25 if x < 0.5 else 1.0)
        
        # WEIGHT FEE: Senior addition - $0.50 per kg over 5kg
        df['weight_surcharge'] = df['total_weight_kg'].apply(lambda x: (x - 5) * 0.5 if x > 5 else 0)
        
        # FINAL FORMULA
        df['target_price'] = (
            df['base_cost'] + 
            (df['distance_km'] * df['km_rate']) + 
            (df['passenger_count'] * 1.50) +
            (df['duration_min'] * 0.2) +
            df['weight_surcharge']
        ) * surge * df['congestion_multiplier']
        
        return df.round({'target_price': 2})

    def transform(self):
        print("Executing Senior Logistics Transformation...")
        
        # A. SPATIAL & TEMPORAL (Same as before)
        self.df['distance_km'] = self.haversine_distance(
            self.df['pickup_latitude'], self.df['pickup_longitude'],
            self.df['dropoff_latitude'], self.df['dropoff_longitude']
        )
        self.df['pickup_datetime'] = pd.to_datetime(self.df['pickup_datetime'])
        self.df['hour'] = self.df['pickup_datetime'].dt.hour
        self.df['day_of_week'] = self.df['pickup_datetime'].dt.dayofweek
        self.df['is_holiday'] = self.df['pickup_datetime'].dt.date.apply(
            lambda x: 1 if x in self.us_holidays else 0
        ).astype(int)
        
        # B. TRAFFIC LOGIC (Physics)
        if 'trip_duration' in self.df.columns:
            self.df['duration_min'] = self.df['trip_duration'] / 60
            self.df['actual_speed_kmh'] = self.df['distance_km'] / (self.df['duration_min'] / 60 + 0.001)
            group_cols = ['hour', 'day_of_week', 'is_holiday']
            hour_avg_speed = self.df.groupby(group_cols)['actual_speed_kmh'].transform('mean')
            self.df['traffic_density_score'] = (self.df['actual_speed_kmh'] / hour_avg_speed).fillna(1.0).round(2)

        # C. FEATURE ENGINEERING (Economics)
        self.df['is_rush_hour'] = ((self.df['hour'].between(8, 10)) | (self.df['hour'].between(16, 19))).astype(int)
        self.df['is_weekend'] = (self.df['day_of_week'] >= 5).astype(int)
        self.df['is_high_demand'] = (
            ((self.df['is_rush_hour'] == 1) & (self.df['is_weekend'] == 0)) | 
            (self.df['is_weekend'] == 1) | 
            (self.df['is_holiday'] == 1)
        ).astype(int)

        # D. VEHICLE SELECTION: Adjusted thresholds to be realistic for 1-600kg range
        conditions = [
            (self.df['distance_km'] <= 3.0) & (self.df['total_weight_kg'] <= 5.0),   # E-scooter
            (self.df['distance_km'] <= 7.0) & (self.df['total_weight_kg'] <= 20.0),  # Bicycle
            (self.df['total_weight_kg'] <= 150.0),                                  # Van
            (self.df['total_weight_kg'] > 150.0)                                    # Truck
        ]
        choices = ['e_scooter', 'bicycle', 'van', 'truck']
        self.df['vehicle_type'] = np.select(conditions, choices, default='truck')

        # E. PRICING
        self.df = self.calculate_logistics_price(self.df)
        
        stats = self.df.groupby(group_cols).agg({
            'actual_speed_kmh': 'mean',
            'traffic_density_score': 'mean'
        }).to_dict('index')

        # One-Hot Encoding for the XGBoost model
        self.df = pd.get_dummies(self.df, columns=['vehicle_type'], prefix='type', dtype=int)
        
        cols_to_drop = [
            'id', 'vendor_id', 'pickup_datetime', 'actual_speed_kmh', 
            'dropoff_datetime', "trip_duration", 'base_cost', 'km_rate', 
            'congestion_multiplier', 'weight_surcharge', 'store_and_fwd_flag'
        ]
        existing_drops = [c for c in cols_to_drop if c in self.df.columns]
        self.df.drop(columns=existing_drops, inplace=True)
        
        # Target Price always at the end
        cols = [c for c in self.df.columns if c != 'target_price'] + ['target_price']
        self.df = self.df[cols]
        
        print(f"Final Feature Set: {list(self.df.columns)}")
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
        
    serializable_traffic_map = {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in traffic_map.items()}
        
    with open("data/transformed/traffic_mapping.json","w") as f:
        json.dump(serializable_traffic_map, f, indent=4)

    print("Done! CSV, JSON Lookup, and Pickle saved.")

