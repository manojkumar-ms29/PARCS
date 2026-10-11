import pytest
import pandas as pd
import json
from pathlib import Path

from src.storage import (
    RAW_DIR,
    PROCESSED_DIR,
    ANALYTICS_DIR,
    ensure_storage_dirs,
    save_raw_data,
    write_parquet,
    read_parquet,
    get_db_connection
)

@pytest.fixture
def cleanup_data():
    """Fixture to clean up test files after tests run."""
    yield
    # Cleanup logic (optional, we could delete specific test files or let them be overwritten)
    # For a robust test, it's better to use pytest's monkeypatch to mock paths or just use a temporary directory.
    # However, since the paths are hardcoded to the real data dir, we can just use unique test names and clean them up.
    test_files = list(RAW_DIR.glob("test_*.json")) + list(PROCESSED_DIR.glob("test_*.parquet"))
    for f in test_files:
        try:
            f.unlink()
        except OSError:
            pass

def test_storage_paths():
    """Test that storage paths are defined correctly and ensure_dirs works."""
    ensure_storage_dirs()
    assert RAW_DIR.exists()
    assert PROCESSED_DIR.exists()
    assert ANALYTICS_DIR.exists()
    assert RAW_DIR.name == "raw"
    assert PROCESSED_DIR.name == "processed"
    assert ANALYTICS_DIR.name == "analytics"

def test_save_raw_data_json(cleanup_data):
    """Test saving raw JSON data."""
    test_data = {"key": "value", "list": [1, 2, 3]}
    filepath = save_raw_data(test_data, "test_source")
    
    assert filepath.exists()
    assert filepath.suffix == ".json"
    
    with open(filepath, "r") as f:
        loaded_data = json.load(f)
        
    assert loaded_data == test_data

def test_save_raw_data_text(cleanup_data):
    """Test saving raw text data."""
    test_data = "<html><body>Hello</body></html>"
    filepath = save_raw_data(test_data, "test_source", ext="html")
    
    assert filepath.exists()
    assert filepath.suffix == ".html"
    
    with open(filepath, "r") as f:
        loaded_data = f.read()
        
    assert loaded_data == test_data

def test_write_and_read_parquet(cleanup_data):
    """Test writing and reading a Parquet file."""
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    dataset_name = "test_dataset"
    
    filepath = write_parquet(df, dataset_name)
    assert filepath.exists()
    
    loaded_df = read_parquet(dataset_name)
    pd.testing.assert_frame_equal(df, loaded_df)

def test_write_empty_parquet(cleanup_data):
    """Test that writing an empty DataFrame raises an error."""
    df = pd.DataFrame()
    with pytest.raises(ValueError, match="Cannot write an empty DataFrame"):
        write_parquet(df, "test_empty_dataset")

def test_read_missing_parquet():
    """Test reading a non-existent dataset raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        read_parquet("non_existent_dataset_123")

def test_duckdb_query_parquet(cleanup_data):
    """Test querying a Parquet file via DuckDB."""
    df = pd.DataFrame({"id": [1, 2], "val": [10, 20]})
    dataset_name = "test_duckdb_dataset"
    write_parquet(df, dataset_name)
    
    db = get_db_connection()
    result_df = db.query_dataset(dataset_name, f"SELECT val FROM {dataset_name} WHERE id = 2").df()
    
    assert len(result_df) == 1
    assert result_df.iloc[0]["val"] == 20
    db.close()
