import pandas as pd
import numpy as np

class NYCFeatureEngineer:
    def __init__(self, df):
        self.df = df.copy()

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculates the great-circle distance between two points on Earth.
        Essential for pricing in routing apps.
        """
        r = 6371 # Earth's radius in km
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return 2 * r * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    def transform(self):
        print("Transforming NYC data for Route Agent...")
        
        # 1. Calculate Distance
        self.df['distance_km'] = self.haversine_distance(
            self.df['pickup_latitude'], self.df['pickup_longitude'],
            self.df['dropoff_latitude'], self.df['dropoff_longitude']
        )
        
        # 2. Duplicate Check (Cleaning step before training)
        # Drops rows where ID is repeated or exact same trip details exist
        self.df.drop_duplicates(subset=['id'], keep='first', inplace=True)
        
        # 3. Create Pricing Target (The 'Y' for your ML model)
        # Pricing Logic: $2.50 (Base) + ($1.20 * km) + ($0.40 * (duration/60))
        # This makes the price sensitive to both distance and traffic time.
        duration_min = self.df['trip_duration'] / 60
        self.df['target_price'] = 2.50 + (self.df['distance_km'] * 1.20) + (duration_min * 0.40)
        
        # 4. Assign Vehicle Type
        # Logic: Short trips = Scooter, Medium = Bike, Long = Moto
        conditions = [
            (self.df['distance_km'] <= 1.5),
            (self.df['distance_km'] > 1.5) & (self.df['distance_km'] <= 5.0),
            (self.df['distance_km'] > 5.0)
        ]
        choices = ['e-scooter', 'bicycle', 'motorcycle']
        self.df['vehicle_type'] = np.select(conditions, choices, default='bicycle')
        
        # 5. Extract Time Features
        self.df['pickup_datetime'] = pd.to_datetime(self.df['pickup_datetime'])
        self.df['hour'] = self.df['pickup_datetime'].dt.hour
        self.df['day_of_week'] = self.df['pickup_datetime'].dt.dayofweek
        
        print(f"Transformation complete. New features: {list(self.df.columns[-5:])}")
        return self.df

    def fit_transform(self, df):
        print(f"Scaling {len(self.cols_to_scale)} features...")
        
        # We only scale the numeric features, not 'id' or 'vehicle_type'
        df_scaled = df.copy()
        df_scaled[self.cols_to_scale] = self.scaler.fit_transform(df[self.cols_to_scale])
        
        return df_scaled, self.scaler

# In your main block:
# scaler_tool = NYCScaler()
# final_train_df, fitted_scaler = scaler_tool.fit_transform(transformed_df)