import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, mock_open
from src.data_pipeline.validation import DataValidator

# --- SCENARIO GENERATOR ---
def create_test_df(dataset_type, scenario_type):
    """
    Generates DataFrames based on your actual schema columns.
    Dataset-aware to handle both 'pickup' and 'delivery' scenarios.
    """
    if dataset_type == 'pickup':
        cols = {
            'order_id': range(100), 'region_id': [1]*100, 'city': ['Shanghai']*100,
            'courier_id': range(100), 'lng': [121.47]*100, 'lat': [31.23]*100,
            'pickup_time': pd.date_range("2026-01-01 10:00", periods=100, freq="H"),
            'accept_time': pd.date_range("2026-01-01 09:00", periods=100, freq="H"),
            'ds': [20260101]*100
        }
    else: # delivery
        cols = {
            'order_id': range(100), 'region_id': [1]*100, 'city': ['Shanghai']*100,
            'courier_id': range(100), 'lng': [121.47]*100, 'lat': [31.23]*100,
            'delivery_time': pd.date_range("2026-01-01 12:00", periods=100, freq="H"),
            'accept_time': pd.date_range("2026-01-01 09:00", periods=100, freq="H"),
            'ds': [20260101]*100
        }
    
    df = pd.DataFrame(cols)

    # Apply Failures
    if scenario_type == "missing_critical":
        df.loc[0:10, 'order_id'] = np.nan
    elif scenario_type == "out_of_range":
        df.loc[0, 'lat'] = 99.0  # Outside China (0-60)
    elif scenario_type == "logical_error":
        # Time travel error: Accept happens AFTER delivery/pickup
        target_col = 'pickup_time' if dataset_type == 'pickup' else 'delivery_time'
        df.loc[0, target_col] = pd.Timestamp("2020-01-01") 
    
    return df

# --- TEST CLASS ---
class TestDataValidatorProduction:

    @pytest.mark.parametrize("dataset, scenario, expected_status, check_method", [
        # Pickup Scenarios
        ("pickup", "perfect", "PASS", "structural_validation"),
        ("pickup", "missing_critical", "FAIL", "validate_missing"),
        ("pickup", "out_of_range", "WARN", "validate_ranges"),
        ("pickup", "logical_error", "FAIL", "validate_consistency"),
        # Delivery Scenarios
        ("delivery", "perfect", "PASS", "structural_validation"),
        ("delivery", "logical_error", "FAIL", "validate_consistency"),
    ])
    def test_logic_by_dataset(self, dataset, scenario, expected_status, check_method):
        """
        CI/CD Test: Validates that the core logic handles 
        dataset-specific columns correctly.
        """
        df = create_test_df(dataset, scenario)
        
        # Mocking the filesystem and config for CI/CD environment
        with patch("pandas.read_csv", return_value=df), \
             patch("builtins.open", mock_open(read_data="dummy: data")), \
             patch("yaml.safe_load") as mock_yaml:
            
            # We inject your ACTUAL schema structure here
            mock_yaml.return_value = {
                dataset: {
                    'columns': df.columns.tolist(),
                    'data_types': {c: 'integer' if 'id' in c else 'float' if c in ['lat','lng'] else 'string' for c in df.columns},
                    'critical_columns': ['order_id', 'lat', 'lng', 'courier_id', 
                                        'pickup_time' if dataset=='pickup' else 'delivery_time'],
                    'important_columns': ['accept_time', 'ds'],
                    'optional_columns': []
                }
            }

            validator = DataValidator("fake_path.csv", dataset)
            
            # Dynamically call the validation method
            method = getattr(validator, check_method)
            result = method()

            assert result['status'] == expected_status
            assert 'score' in result