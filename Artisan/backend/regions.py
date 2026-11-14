"""The 10 regions of Cameroon, located by their regional capital.

Coordinates are typed by hand (no external boundary files, per our NASA-only
data rule). The map shows the NASA POWER / MERRA-2 grid cell around each
capital, which is the real spatial resolution of the data we analyse.
"""
from dataclasses import dataclass, asdict

# MERRA-2 native grid used by NASA POWER meteorology
GRID_LAT_STEP = 0.5
GRID_LON_STEP = 0.625


@dataclass(frozen=True)
class Region:
    id: str
    name_fr: str
    name_en: str
    capital: str
    lat: float
    lon: float


REGIONS: list[Region] = [
    Region("adamaoua", "Adamaoua", "Adamawa", "Ngaoundéré", 7.32, 13.58),
    Region("centre", "Centre", "Centre", "Yaoundé", 3.87, 11.52),
    Region("est", "Est", "East", "Bertoua", 4.58, 13.68),
    Region("extreme_nord", "Extrême-Nord", "Far North", "Maroua", 10.59, 14.32),
    Region("littoral", "Littoral", "Littoral", "Douala", 4.05, 9.70),
    Region("nord", "Nord", "North", "Garoua", 9.30, 13.40),
    Region("nord_ouest", "Nord-Ouest", "Northwest", "Bamenda", 5.96, 10.15),
    Region("ouest", "Ouest", "West", "Bafoussam", 5.48, 10.42),
    Region("sud", "Sud", "South", "Ebolowa", 2.90, 11.15),
    Region("sud_ouest", "Sud-Ouest", "Southwest", "Buea", 4.16, 9.24),
]

REGIONS_BY_ID: dict[str, Region] = {r.id: r for r in REGIONS}


def get_region(region_id: str) -> Region:
    """Return a region or raise KeyError with a helpful message."""
    try:
        return REGIONS_BY_ID[region_id]
    except KeyError:
        raise KeyError(f"Unknown region '{region_id}'. Valid: {list(REGIONS_BY_ID)}")


def grid_cell(lat: float, lon: float) -> dict:
    """Bounds of the MERRA-2 grid cell that contains (lat, lon).

    Grid points sit at lat = -90 + k*0.5 and lon = -180 + k*0.625; each
    cell is centred on its grid point.
    """
    center_lat = round((lat + 90) / GRID_LAT_STEP) * GRID_LAT_STEP - 90
    center_lon = round((lon + 180) / GRID_LON_STEP) * GRID_LON_STEP - 180
    return {
        "center": [round(center_lat, 4), round(center_lon, 4)],
        "south": round(center_lat - GRID_LAT_STEP / 2, 4),
        "north": round(center_lat + GRID_LAT_STEP / 2, 4),
        "west": round(center_lon - GRID_LON_STEP / 2, 4),
        "east": round(center_lon + GRID_LON_STEP / 2, 4),
    }


def region_to_dict(region: Region) -> dict:
    """JSON-friendly version of a region, with its grid cell."""
    data = asdict(region)
    data["cell"] = grid_cell(region.lat, region.lon)
    return data