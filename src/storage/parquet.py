import pandas as pd
from pathlib import Path

from .paths import PROCESSED_DIR, ensure_storage_dirs

def write_parquet(df: pd.DataFrame, dataset_name: str) -> Path:
    """
    Write a DataFrame to the processed zone as a Parquet file.
    
    Args:
        df: The pandas DataFrame to write.
        dataset_name: Name of the dataset (without .parquet extension).
        
    Returns:
        Path to the saved Parquet file.
    """
    if df.empty:
        raise ValueError("Cannot write an empty DataFrame to Parquet.")
        
    ensure_storage_dirs()
    filepath = PROCESSED_DIR / f"{dataset_name}.parquet"
    df.to_parquet(filepath, index=False)
    return filepath

def read_parquet(dataset_name: str) -> pd.DataFrame:
    """
    Read a Parquet file from the processed zone into a DataFrame.
    
    Args:
        dataset_name: Name of the dataset (without .parquet extension).
        
    Returns:
        The loaded pandas DataFrame.
        
    Raises:
        FileNotFoundError if the dataset does not exist.
    """
    filepath = PROCESSED_DIR / f"{dataset_name}.parquet"
    if not filepath.exists():
        raise FileNotFoundError(f"Dataset {dataset_name} not found at {filepath}")
    return pd.read_parquet(filepath)
