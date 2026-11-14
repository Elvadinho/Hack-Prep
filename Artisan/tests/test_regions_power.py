import math

from backend.nasa_power import power_to_dataframe
from backend.regions import REGIONS, get_region, grid_cell


def test_ten_regions_inside_cameroon():
    assert len(REGIONS) == 10
    for region in REGIONS:
        assert 1.6 <= region.lat <= 13.1 and 8.4 <= region.lon <= 16.2


def test_grid_cell_contains_point():
    yaounde = get_region("centre")
    cell = grid_cell(yaounde.lat, yaounde.lon)
    assert cell["south"] <= yaounde.lat <= cell["north"]
    assert cell["west"] <= yaounde.lon <= cell["east"]
    assert cell["north"] - cell["south"] == 0.5


def test_power_json_is_parsed_and_fill_values_become_nan():
    payload = {"properties": {"parameter": {
        "T2M": {"20240101": 24.1, "20240102": -999.0},
        "PRECTOTCORR": {"20240101": 0.0, "20240102": 12.5},
    }}}
    df = power_to_dataframe(payload)
    assert list(df.columns) == ["T2M", "PRECTOTCORR"]
    assert df.loc["2024-01-01", "T2M"] == 24.1
    assert math.isnan(df.loc["2024-01-02", "T2M"])