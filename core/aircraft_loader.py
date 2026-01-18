# core/aircraft_loader.py

"""
Aircraft data loading and management.
Handles loading JSON files from the aircraft_data folder and provides
access to the cached data.
"""

import os
import json
import sys
from .constants import DEBUG_LOG


def dprint(*args, **kwargs):
    """Debug print that can be globally toggled."""
    if DEBUG_LOG:
        print(*args, **kwargs)


def resource_path(filename):
    """Get the absolute path to a resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return filename


def load_aircraft_data_from_folder(folder_name="aircraft_data"):
    """
    Load all aircraft JSON files from the specified folder.

    Args:
        folder_name: Name of the folder containing aircraft JSON files

    Returns:
        Dict mapping aircraft names to their data
    """
    # Determine the base directory (where this module is located)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder_path = os.path.join(base_dir, folder_name)

    aircraft_data = {}

    if not os.path.exists(folder_path):
        print(f"[WARNING] Aircraft data folder not found: {folder_path}")
        return aircraft_data

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            filepath = os.path.join(folder_path, filename)
            with open(filepath, "r") as f:
                try:
                    data = json.load(f)
                    name = os.path.splitext(filename)[0].replace("_", " ")
                    aircraft_data[name] = data
                except Exception as e:
                    dprint(f"[ERROR] Failed to load {filename}: {e}")

    return aircraft_data


def extract_vmca_value(ac, preferred="clean_up"):
    """
    Extract Vmca value from aircraft data with preference handling.

    Args:
        ac: Aircraft data dict
        preferred: Preferred Vmca configuration ("clean_up", "gear_down", etc.)

    Returns:
        Vmca value or None if not found
    """
    vmca = ac.get("single_engine_limits", {}).get("Vmca", {})
    if isinstance(vmca, dict):
        return vmca.get(preferred) or next(iter(vmca.values()), None)
    return vmca if isinstance(vmca, (int, float)) else None


class DynamicAircraftData:
    """
    Wrapper around the boot-time AIRCRAFT_DATA dict.
    Provides dict-like access without disk I/O on access.
    """
    def __init__(self, data_dict):
        self._data = data_dict

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __len__(self):
        return len(self._data)

    def update_aircraft(self, name, data):
        """Update or add aircraft data (for runtime additions)."""
        self._data[name] = data

    def get_raw_dict(self):
        """Get the underlying dict (for dcc.Store)."""
        return self._data


# =============================================================================
# AIRPORT DATA LOADING
# =============================================================================

def load_airport_data(filename="airports/airports.json"):
    """
    Load airport data from JSON file.

    Args:
        filename: Path to airports JSON file

    Returns:
        List of airport dicts with id, name, elevation_ft, lat, lon
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(base_dir, filename)

    if not os.path.exists(filepath):
        print(f"[WARNING] Airport data file not found: {filepath}")
        return []

    try:
        with open(filepath, "r") as f:
            airports = json.load(f)
        return airports
    except Exception as e:
        print(f"[ERROR] Failed to load airports: {e}")
        return []


def get_airport_options(airports):
    """
    Convert airport list to dropdown options format.
    Format: "ICAO - Name (elev ft)"
    """
    options = []
    for ap in airports:
        elev = ap.get("elevation_ft", 0)
        label = f"{ap['id']} - {ap['name']} ({elev} ft)"
        options.append({"label": label, "value": ap["id"]})
    return options


def get_airport_by_id(airports, airport_id):
    """
    Find airport by ID.

    Args:
        airports: List of airport dicts
        airport_id: Airport identifier (e.g., "KJFK")

    Returns:
        Airport dict or None
    """
    for ap in airports:
        if ap["id"] == airport_id:
            return ap
    return None


# =============================================================================
# BOOT-TIME LOADING
# =============================================================================
print("[BOOT] Loading aircraft data from folder once...")
AIRCRAFT_DATA = load_aircraft_data_from_folder()
print(f"[BOOT] Loaded {len(AIRCRAFT_DATA)} aircraft")

print("[BOOT] Loading airport data...")
AIRPORT_DATA = load_airport_data()
AIRPORT_OPTIONS = get_airport_options(AIRPORT_DATA)
print(f"[BOOT] Loaded {len(AIRPORT_DATA)} airports")

# Create the dynamic wrapper
aircraft_data = DynamicAircraftData(AIRCRAFT_DATA)
