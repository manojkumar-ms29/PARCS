import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Union

from .paths import RAW_DIR, ensure_storage_dirs

def save_raw_data(data: Union[str, dict, list], source_name: str, ext: str = "json") -> Path:
    """
    Persists raw collector output to the raw data directory.
    
    Args:
        data: The raw data to save.
        source_name: Name of the collector or data source (e.g., 'eventlog').
        ext: File extension (default: 'json').
        
    Returns:
        Path to the saved file.
    """
    ensure_storage_dirs()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    filename = f"{source_name}-{timestamp}-{uid}.{ext}"
    filepath = RAW_DIR / filename
    
    if ext == "json" and not isinstance(data, str):
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        with filepath.open("w", encoding="utf-8") as f:
            if not isinstance(data, str):
                data = str(data)
            f.write(data)
            
    return filepath
