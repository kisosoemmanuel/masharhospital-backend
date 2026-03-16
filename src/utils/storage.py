import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def load_db(filename: str, default: dict = None):
    """Load a JSON file from disk, return dict."""
    filepath = DATA_DIR / filename
    if default is None:
        default = {}
    if filepath.exists():
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            # Convert string keys back to int if needed
            if all(k.isdigit() for k in data.keys()):
                data = {int(k): v for k, v in data.items()}
            return data
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return default
    return default

def save_db(filename: str, data: dict):
    """Save a dict to a JSON file."""
    filepath = DATA_DIR / filename
    try:
        # Convert int keys to strings for JSON
        if data and isinstance(next(iter(data.keys())), int):
            data = {str(k): v for k, v in data.items()}
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving {filename}: {e}")