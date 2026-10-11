import duckdb
from pathlib import Path
import pandas as pd

from .paths import PROCESSED_DIR

class DuckDBManager:
    """
    Manages DuckDB connections and provides access to Parquet datasets.
    DuckDB is used as an embedded analytical store querying Parquet directly.
    """
    
    def __init__(self, db_path: str = ':memory:'):
        self.conn = duckdb.connect(database=db_path)
        
    def query(self, sql: str) -> duckdb.DuckDBPyRelation:
        """
        Execute an arbitrary SQL query.
        """
        return self.conn.sql(sql)
        
    def query_dataset(self, dataset_name: str, sql: str) -> duckdb.DuckDBPyRelation:
        """
        Query a specific dataset in the processed zone.
        Registers the dataset as a view named `dataset_name` before executing the query.
        
        Args:
            dataset_name: Name of the dataset (without .parquet extension).
            sql: SQL query to execute, where the table name can be `dataset_name`.
        """
        filepath = PROCESSED_DIR / f"{dataset_name}.parquet"
        if not filepath.exists():
            raise FileNotFoundError(f"Dataset {dataset_name} not found at {filepath}")
            
        # Create a view to the parquet file so the user query can reference it by dataset_name
        self.conn.execute(f"CREATE OR REPLACE VIEW {dataset_name} AS SELECT * FROM '{filepath}'")
        
        return self.conn.sql(sql)
        
    def query_to_df(self, sql: str) -> pd.DataFrame:
        """
        Execute a query and return a pandas DataFrame.
        """
        return self.conn.sql(sql).df()

    def close(self):
        """Close the DuckDB connection."""
        self.conn.close()

def get_db_connection(db_path: str = ':memory:') -> DuckDBManager:
    """
    Get a managed DuckDB connection.
    """
    return DuckDBManager(db_path)
