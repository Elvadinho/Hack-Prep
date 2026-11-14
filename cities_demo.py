import pandas as pd

cities = pd.DataFrame({
    "city": ["Yaoundé", "Douala", "Maroua"],
    "lat": [3.87, 4.05, 10.59],
    "lon": [11.52, 9.70, 14.32],
})

cities.head()                 # first rows
cities["lat"]                 # one column
cities[cities["lat"] > 5]     # filter rows
cities["lat"].mean()          # simple statistic