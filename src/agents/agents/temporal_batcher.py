from sklearn.cluster import DBSCAN
import numpy as np
from src.models.data_models import ShipmentModel
from typing import List
from sklearn.metrics.pairwise import haversine_distances

class SpatialTemporalBatcher:
    def __init__(self,max_distance_km=2,time_window_hours=2):
        self.max_dist= max_distance_km
        self.time_window= time_window_hours
        self.kms_per_radian = 6371.0088
    def group_shipments(self,shipments:List[ShipmentModel])->List[List[ShipmentModel]]:
        """
        Input: List of ShipmentModel objects
        Output: List of Groups (Each group is a truck load)
        """
        print("clustering started")
        temporal_groups={}
        for s in shipments:
            time_key= s.pickup_time.strftime("%Y-%m-%d-%H")
            print(time_key)

            if time_key not in temporal_groups:
                temporal_groups[time_key]=[]
            temporal_groups.setdefault(time_key, []).append(s)
        
        print(temporal_groups)
        #cluster wihtin ecah time bucket
        final_clusters=[]
        for time_key,bucket in temporal_groups.items():
            if len(bucket) < 2:
                print(f"Skipping DBSCAN for {time_key}: Only {len(bucket)} shipment(s).")
                final_clusters.append(bucket)
                continue
          
            coords= np.array([[s.dropoff_latitude, s.dropoff_longitude]for s in bucket])
            coords_radians = np.radians(coords) # CRITICAL FIX
            dist_matrix = haversine_distances(coords_radians) * self.kms_per_radian

            print(f"\n--- DEBUG: BUCKET {time_key} ---")
            print(f"Points in bucket: {len(bucket)}")
            print(f"Distance Matrix (km):\n{dist_matrix}")
            print(f"Epsilon Threshold (km): {self.max_dist}")

            # DBSCAN finds "clusters" of points that are close together
            # eps is the distance threshold

            epsilon = self.max_dist / self.kms_per_radian
            clustering = DBSCAN(eps=epsilon, 
                min_samples=2, # Require at least 2 to form a cluster
                metric='haversine',
                algorithm='ball_tree'
            ).fit(coords_radians)
        

            cluster_map={}

            for idx,label in enumerate(clustering.labels_):
                if label not in cluster_map:
                    cluster_map[label] =[]
    
                cluster_map[label].append(bucket[idx])

            if -1 in cluster_map:
                noise_shipments=cluster_map.pop(-1)
                for ns in noise_shipments:
                    final_clusters.append([ns])
                
            
            final_clusters.extend(list(cluster_map.values()))
            print(f"clusters_length:len{final_clusters}")

        return final_clusters
