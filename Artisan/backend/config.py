"""Central settings for Artisan, read once from the .env file."""
from pathlib import Path
import os

from dotenv import load_dotenv

# Artisan/ folder (this file lives in Artisan/backend/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
EXPORTS_DIR = DATA_DIR / "exports"
FRONTEND_DIR = BASE_DIR / "frontend"

# Study period: NASA POWER daily meteorology (MERRA-2) begins 1981-01-01,
# so 1981 is the earliest possible year. 1991-2020 = WMO climate "normal" (baseline)
START_YEAR = 1981
END_YEAR = 2025
BASELINE_START = 1991
BASELINE_END = 2020
# Robustness check: MERRA-2 shows a simultaneous jump around 1998 in all regions
# (likely an observing-system change, e.g. new satellite inputs). Every trend is
# re-tested from this year on to see if it survives without that jump.
ROBUST_FROM = 2000

# NASA POWER daily point API (official NASA, no key needed)
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMETERS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "GWETROOT"]

# AI chatbot via OpenRouter (key stays on the server, never sent to the browser)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
OPENROUTER_FALLBACK_MODEL = os.getenv(
    "OPENROUTER_FALLBACK_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"
)