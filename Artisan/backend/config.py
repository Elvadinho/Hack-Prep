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

# Study period: 1991-2020 is the WMO standard climate "normal" (baseline)
START_YEAR = 1991
END_YEAR = 2025
BASELINE_START = 1991
BASELINE_END = 2020

# NASA POWER daily point API (official NASA, no key needed)
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMETERS = ["T2M", "T2M_MAX", "PRECTOTCORR", "GWETROOT"]

# AI chatbot via OpenRouter (key stays on the server, never sent to the browser)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
OPENROUTER_FALLBACK_MODEL = os.getenv(
    "OPENROUTER_FALLBACK_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free"
)