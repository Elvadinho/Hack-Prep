import requests
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

api = "https://www.geoboundaries.org/api/current/gbOpen/CMR/ADM1/"
geojson_url = requests.get(api, timeout=60).json()["gjDownloadURL"]
regions = gpd.read_file(geojson_url)

regions = regions[["shapeName", "geometry"]].rename(columns={"shapeName": "region"})
regions.to_file("cameroon_regions.geojson", driver="GeoJSON")   # save a local copy

print(regions.crs)
print(regions["region"].tolist())
regions.plot(edgecolor="black", color="lightgrey")
plt.title("Cameroon - 10 regions")
plt.show()

regions_m = regions.to_crs("EPSG:32633")
regions["area_km2"] = (regions_m.area / 1_000_000).round(0)

summary = pd.read_csv("climate_summary.csv")
cities_gdf = gpd.GeoDataFrame(
    summary,
    geometry=gpd.points_from_xy(summary["lon"], summary["lat"]),
    crs="EPSG:4326",
)

joined = gpd.sjoin(cities_gdf, regions[["region", "geometry"]],
                   predicate="within", how="left")
print(joined[["city", "region"]])          # check every city found a region

def normalize(col):
    return (col - col.min()) / (col.max() - col.min())

joined["heat_risk"] = (
    0.5 * normalize(joined["hot_days"]) +
    0.5 * normalize(joined["dry_days"])
).round(2)

joined["flood_risk"] = (
    0.5 * normalize(joined["heavy_rain_days"]) +
    0.5 * normalize(joined["total_rain"])
).round(2)

def suggest_skills(row):
    skills = []
    if row["heat_risk"] >= 0.5:
        skills += ["well digger", "water tank repair", "heat-resistant builder (earth bricks)"]
    if row["flood_risk"] >= 0.5:
        skills += ["drainage mason", "roofer", "raised-foundation builder"]
    if not skills:
        skills = ["general maintenance"]
    return ", ".join(skills)

joined["artisan_skills"] = joined.apply(suggest_skills, axis=1)
# axis=1 → apply the function to each ROW (not each column)

cols = ["region", "city", "avg_temp", "total_rain", "hot_days",
        "heavy_rain_days", "dry_days", "heat_risk", "flood_risk", "artisan_skills"]
regions_risk = regions.merge(joined[cols], on="region", how="left")

regions_risk.to_file("cameroon_climate_risk.geojson", driver="GeoJSON")
regions_risk.drop(columns="geometry").to_csv("cameroon_climate_risk.csv", index=False)
print(regions_risk.drop(columns="geometry"))

fig, axes = plt.subplots(1, 2, figsize=(14, 7))

regions_risk.plot(column="heat_risk", cmap="OrRd", legend=True,
                  edgecolor="black", ax=axes[0])
cities_gdf.plot(ax=axes[0], color="black", markersize=15)
axes[0].set_title("Heat & drought risk (2023)")
axes[0].axis("off")

regions_risk.plot(column="flood_risk", cmap="Blues", legend=True,
                  edgecolor="black", ax=axes[1])
cities_gdf.plot(ax=axes[1], color="black", markersize=15)
axes[1].set_title("Flood risk (2023)")
axes[1].axis("off")

plt.suptitle("ArtisanConnect - Cameroon climate risk by region (NASA POWER data)")
plt.tight_layout()
plt.savefig("risk_maps.png", dpi=150)
plt.show()

m = regions_risk.explore(
    column="heat_risk",
    cmap="OrRd",
    tooltip=["region", "city", "avg_temp", "hot_days", "dry_days",
             "heat_risk", "flood_risk", "artisan_skills"],
    tiles="CartoDB positron",
    style_kwds={"color": "black", "weight": 1},
)
cities_gdf.explore(m=m, color="black", marker_kwds={"radius": 5},
                   tooltip=["city", "total_rain", "hot_days"])
m.save("artisanconnect_risk_map.html")
print("Open artisanconnect_risk_map.html in your browser")