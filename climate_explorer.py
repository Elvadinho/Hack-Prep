import requests
import pandas as pd
import matplotlib as plt

cities = {
    "Yaoundé":    (3.87, 11.52),
    "Douala":     (4.05, 9.70),
    "Bamenda":    (5.96, 10.15),
    "Buea":       (4.16, 9.24),
    "Bafoussam":  (5.48, 10.42),
    "Garoua":     (9.30, 13.40),
    "Maroua":     (10.59, 14.32),
    "Ngaoundéré": (7.32, 13.58),
    "Bertoua":    (4.58, 13.68),
    "Ebolowa":    (2.90, 11.15),
}

def download_nasa(city, lat, lon):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M",
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": "20230101",
        "end": "20231231",
        "format": "JSON",
    }
    
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()          # stop with a clear error if the request failed
    values = response.json()["properties"]["parameter"]

    df = pd.DataFrame(values)
    df.index.name = "date"
    df = df.reset_index()
    df["city"] = city
    df["lat"] = lat
    df["lon"] = lon
    return df

def clean(df):
    df = df.replace(-999, float("nan"))
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    df = df.rename(columns={
        "T2M": "temp",
        "T2M_MAX": "temp_max",
        "T2M_MIN": "temp_min",
        "PRECTOTCORR": "rain_mm",
        "RH2M": "humidity",
    })
    df["month"] = df["date"].dt.month
    return df

frames = []
for name, (lat, lon) in cities.items():
    print("Downloading", name, "...")
    df = clean(download_nasa(name, lat, lon))
    frames.append(df)

all_cities = pd.concat(frames, ignore_index=True)
all_cities.to_csv("all_cities_2023.csv", index=False)   # save raw clean data
print(all_cities.shape)
print(all_cities.isna().sum())

def rain_level(mm):
    if mm == 0:
        return "dry"
    elif mm < 10:
        return "light"
    elif mm < 30:
        return "moderate"
    else:
        return "heavy"

all_cities["rain_level"] = all_cities["rain_mm"].apply(rain_level)

summary = all_cities.groupby("city").agg(
    lat=("lat", "first"),
    lon=("lon", "first"),
    avg_temp=("temp", "mean"),
    max_temp=("temp_max", "max"),
    total_rain=("rain_mm", "sum"),
    hot_days=("temp_max", lambda x: (x > 35).sum()),
    heavy_rain_days=("rain_mm", lambda x: (x > 30).sum()),
    dry_days=("rain_mm", lambda x: (x < 0.1).sum()),
).round(1)

monthly_rain = all_cities.groupby(["city", "month"])["rain_mm"].sum().reset_index()
idx = monthly_rain.groupby("city")["rain_mm"].idxmax()     # row of the max for each city
rainiest = monthly_rain.loc[idx, ["city", "month"]].rename(columns={"month": "rainiest_month"})

summary = summary.reset_index().merge(rainiest, on="city", how="left")

summary = summary.sort_values("total_rain", ascending=False)
summary.to_csv("climate_summary.csv", index=False)
print(summary)

summary.plot(x="city", y="total_rain", kind="bar", legend=False,
             title="Total rainfall 2023 by city (NASA POWER)")
plt.ylabel("mm")
plt.tight_layout()
plt.show()

summary.sort_values("hot_days").plot(x="city", y="hot_days", kind="barh",
             legend=False, color="orange", title="Days above 35°C in 2023")
plt.tight_layout()
plt.show()
pivot = pd.pivot_table(all_cities, values="rain_mm", index="month",
                       columns="city", aggfunc="sum")
pivot[["Yaoundé", "Douala", "Maroua"]].plot(title="Monthly rainfall 2023")
plt.ylabel("mm")
plt.show()