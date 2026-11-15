"""Client for the NASA POWER daily point API, with a disk cache.

One request per region returns 45 years of daily data for 5 variables.
The JSON is cached in data/cache/ so we only call NASA once per region.
"""
import json

import httpx
import pandas as pd

from backend import config
from backend.regions import Region

FILL_VALUE = -999.0  # NASA POWER marks missing data with -999


def _cache_path(region: Region):
    # the variable list is part of the name, so adding a variable triggers a fresh download
    variables = "-".join(config.POWER_PARAMETERS)
    return config.CACHE_DIR / f"power_{region.id}_{config.START_YEAR}_{config.END_YEAR}_{variables}.json"


def fetch_power_json(region: Region, refresh: bool = False) -> dict:
    """Download (or read from cache) the raw NASA POWER JSON for a region."""
    path = _cache_path(region)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    params = {
        "parameters": ",".join(config.POWER_PARAMETERS),
        "community": "AG",
        "latitude": region.lat,
        "longitude": region.lon,
        "start": f"{config.START_YEAR}0101",
        "end": f"{config.END_YEAR}1231",
        "format": "JSON",
    }
    response = httpx.get(config.POWER_URL, params=params, timeout=120)
    response.raise_for_status()
    payload = response.json()

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def power_to_dataframe(payload: dict) -> pd.DataFrame:
    """Turn the POWER JSON into a table: one row per day, one column per variable."""
    parameters = payload["properties"]["parameter"]
    frame = pd.DataFrame(parameters)  # index = "YYYYMMDD" strings
    frame.index = pd.to_datetime(frame.index, format="%Y%m%d")
    frame.index.name = "date"
    frame = frame.replace(FILL_VALUE, float("nan"))
    return frame.sort_index()


def load_daily(region: Region, refresh: bool = False) -> pd.DataFrame:
    """Daily NASA POWER data for a region (cached)."""
    return power_to_dataframe(fetch_power_json(region, refresh=refresh))


if __name__ == "__main__":
    # Quick manual check: python -m backend.nasa_power
    from backend.regions import get_region

    df = load_daily(get_region("centre"))
    print(df.head())
    print(df.tail())
    print(f"{len(df)} days, missing values per column:\n{df.isna().sum()}")