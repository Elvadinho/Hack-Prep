"""Places you can build a climate report for: the 10 regional capitals + other towns.

Coordinates are public knowledge typed by hand (no external dataset). Each place is
analysed at its own NASA POWER point (MERRA-2 grid cell ~50 km), downloaded on demand.
"""
import re
import unicodedata

from backend.regions import REGIONS, Region

# (town, region id, lat, lon)
TOWNS: list[tuple[str, str, float, float]] = [
    ("Kousséri", "extreme_nord", 12.077, 15.031), ("Mokolo", "extreme_nord", 10.74, 13.80),
    ("Yagoua", "extreme_nord", 10.34, 15.23), ("Mora", "extreme_nord", 11.05, 14.14), ("Kaélé", "extreme_nord", 10.10, 14.45),
    ("Guider", "nord", 9.93, 13.95), ("Poli", "nord", 8.48, 13.24), ("Tcholliré", "nord", 8.40, 14.17),
    ("Touboro", "nord", 7.77, 15.36), ("Rey Bouba", "nord", 8.67, 14.18),
    ("Tibati", "adamaoua", 6.47, 12.63), ("Meiganga", "adamaoua", 6.52, 14.29), ("Banyo", "adamaoua", 6.75, 11.82),
    ("Tignère", "adamaoua", 7.37, 12.65),
    ("Wum", "nord_ouest", 6.38, 10.07), ("Nkambe", "nord_ouest", 6.63, 10.67), ("Kumbo", "nord_ouest", 6.20, 10.68),
    ("Ndop", "nord_ouest", 6.00, 10.42),
    ("Dschang", "ouest", 5.45, 10.05), ("Foumban", "ouest", 5.73, 10.90), ("Bangangté", "ouest", 5.15, 10.52),
    ("Mbouda", "ouest", 5.63, 10.25),
    ("Kumba", "sud_ouest", 4.64, 9.45), ("Mamfe", "sud_ouest", 5.76, 9.31), ("Limbe", "sud_ouest", 4.02, 9.21),
    ("Mundemba", "sud_ouest", 4.95, 8.87),
    ("Edéa", "littoral", 3.80, 10.13), ("Nkongsamba", "littoral", 4.95, 9.94), ("Yabassi", "littoral", 4.46, 9.97),
    ("Bafia", "centre", 4.75, 11.23), ("Nanga-Eboko", "centre", 4.68, 12.37), ("Mbalmayo", "centre", 3.52, 11.50),
    ("Yoko", "centre", 5.53, 12.32), ("Ntui", "centre", 4.45, 11.63),
    ("Batouri", "est", 4.43, 14.36), ("Yokadouma", "est", 3.51, 15.05), ("Abong-Mbang", "est", 3.98, 13.18),
    ("Garoua-Boulaï", "est", 5.88, 14.55), ("Moloundou", "est", 2.03, 15.21), ("Lomié", "est", 3.16, 13.62),
    ("Kribi", "sud", 2.94, 9.91), ("Sangmélima", "sud", 2.93, 11.98), ("Ambam", "sud", 2.38, 11.27),
    ("Djoum", "sud", 2.67, 12.67), ("Campo", "sud", 2.37, 9.82),
]


# Neighbouring countries, represented by their capital's NASA POWER point (no country boundaries used)
# (capital, country FR, country EN, lat, lon)
FOREIGN: list[tuple[str, str, str, float, float]] = [
    ("N'Djamena", "Tchad", "Chad", 12.11, 15.04),
    ("Abuja", "Nigeria", "Nigeria", 9.06, 7.49),
    ("Bangui", "République centrafricaine", "Central African Republic", 4.36, 18.56),
    ("Libreville", "Gabon", "Gabon", 0.39, 9.45),
    ("Malabo", "Guinée équatoriale", "Equatorial Guinea", 3.75, 8.78),
    ("Brazzaville", "Congo", "Congo", -4.27, 15.28),
]


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def all_places() -> list[dict]:
    """Capitals first (id = region id, already cached), then the other towns."""
    places = [{"id": r.id, "name": r.capital, "region": r.id, "lat": r.lat, "lon": r.lon, "capital": True} for r in REGIONS]
    places += [{"id": f"town_{_slug(name)}", "name": name, "region": region, "lat": lat, "lon": lon, "capital": False}
               for name, region, lat, lon in TOWNS]
    places += [{"id": f"country_{_slug(en)}", "name": name, "region": "foreign", "country_fr": fr, "country_en": en,
                "lat": lat, "lon": lon, "capital": False, "foreign": True}
               for name, fr, en, lat, lon in FOREIGN]
    return places


PLACES: dict[str, dict] = {p["id"]: p for p in all_places()}


def place_as_region(place_id: str) -> Region:
    """A Region-like object so the NASA POWER client can download this place."""
    p = PLACES[place_id]
    return Region(p["id"], p["name"], p["name"], p["name"], p["lat"], p["lon"])
