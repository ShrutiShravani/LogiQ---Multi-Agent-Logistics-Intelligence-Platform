import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.data_pipeline.loader import load_delivery

# --- TEST CLASS ---
class TestDataLoader:

    @patch("pandas.read_csv")
    def test_load_delivery_success(self, mock_read_csv):
        """
        Tests if the loader correctly reads a CSV and returns a DataFrame.
        We mock read_csv so we don't need a real file.
        """
        # 1. Setup: Create a fake dataframe that read_csv will return
        fake_data = pd.DataFrame({
            'order_id': [1, 2],
            'delivery_time': ['2026-01-01 10:00:00', '2026-01-01 11:00:00']
        })
        mock_read_csv.return_value = fake_data

        # 2. Execute: Call your actual loader function
        file_path = 'data/raw/delivery/delivery_sh.csv'
        df = load_delivery(file_path)

        # 3. Assert: Verify the results
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'order_id' in df.columns
        # Verify pandas.read_csv was called with the correct path
        mock_read_csv.assert_called_once_with(file_path)

    @patch("pandas.read_csv")
    def test_load_delivery_file_not_found(self, mock_read_csv):
        """
        Tests how the loader handles a missing file.
        A senior project must test for failures, not just successes.
        """
        # Tell the mock to raise a FileNotFoundError
        mock_read_csv.side_effect = FileNotFoundError

        with pytest.raises(FileNotFoundError):
            load_delivery("non_existent_file.csv")

    def test_load_delivery_integration(self, tmp_path):
        """
        This is a lightweight INTEGRATION test.
        It creates a real temporary file on disk to ensure 
        the loader works with the actual filesystem.
        """
        # Create a temporary directory and file
        d = tmp_path / "data"
        d.mkdir()
        p = d / "test_delivery.csv"
        p.write_text("order_id,city\n101,Shanghai")

        # Run the loader on the real (temp) file
        df = load_delivery(str(p))

        assert df.iloc[0]['order_id'] == 101
        assert df.iloc[0]['city'] == 'Shanghai'