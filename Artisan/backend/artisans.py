"""Suggest local artisans who can help prevent or repair damage for a hazard.

The directory in data/artisans.json is FICTIONAL demo data (no real people).
"""
import json
from functools import lru_cache

from backend import config

# What a community can do, and which trades help (shown in the app and given to the AI)
PREVENTION: dict[str, dict] = {
    "heat": {
        "fr": ["Isoler et ventiler les toits", "Créer de l'ombre (auvents, arbres)", "Prévoir des points d'eau potable"],
        "en": ["Insulate and ventilate roofs", "Add shade (awnings, trees)", "Plan drinking-water points"],
    },
    "flood": {
        "fr": ["Curer et agrandir les caniveaux", "Surélever les seuils et fondations", "Éviter de construire dans les bas-fonds"],
        "en": ["Clean and widen drains", "Raise doorsteps and foundations", "Avoid building in low-lying areas"],
    },
    "drought": {
        "fr": ["Récupérer l'eau de pluie (citernes)", "Creuser ou réhabiliter des puits", "Irrigation goutte-à-goutte"],
        "en": ["Harvest rainwater (tanks)", "Dig or repair wells", "Drip irrigation"],
    },
    "landslide": {
        "fr": ["Construire des murs de soutènement", "Drainer les pentes", "Replanter la végétation sur les talus"],
        "en": ["Build retaining walls", "Drain slopes", "Replant vegetation on embankments"],
    },
}


@lru_cache(maxsize=1)
def load_artisans() -> list[dict]:
    path = config.DATA_DIR / "artisans.json"
    return json.loads(path.read_text(encoding="utf-8"))


def find_artisans(region_id: str, hazard: str, limit: int = 5) -> list[dict]:
    """Artisans for a hazard: those in the region first, then others."""
    matching = [a for a in load_artisans() if hazard in a["hazards"]]
    local = [{**a, "local": True} for a in matching if a["region"] == region_id]
    others = [{**a, "local": False} for a in matching if a["region"] != region_id]
    return (local + others)[:limit]