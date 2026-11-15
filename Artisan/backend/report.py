"""Climate synthesis report for one place and one period (like a consultant's brief).

  1. Statistics table: mean, median, min (year), max (year), std, trend per decade
     with significance, change between the first and last decade of the period
  2. 5-year averages + recent years
  3. Key facts written automatically from the numbers
  4. Recommendations for local authorities, grouped by axis, triggered by the results

Everything comes from NASA POWER daily data at the place's own grid point.
"""
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.stats import linregress, t as student_t

from backend import config
from backend.forecast import backtest, calibrate, forecast, hindcast
from backend.nasa_power import load_daily
from backend.regions import REGIONS, REGIONS_BY_ID
from backend.stats import MIN_YEARS, robustness, trend_line, trend_test
from backend.towns import PLACES, place_as_region

# key: (French label, English label, unit, how to build one value per year)
VARIABLES = {
    "T2M": ("Température moyenne annuelle", "Mean annual temperature", "°C"),
    "TXX": ("Jour le plus chaud de l'année (T2M_MAX)", "Hottest day of the year (T2M_MAX)", "°C"),
    "TNN": ("Nuit la plus froide de l'année (T2M_MIN)", "Coldest night of the year (T2M_MIN)", "°C"),
    "RAIN": ("Pluie annuelle totale (PRECTOTCORR)", "Total annual rainfall (PRECTOTCORR)", "mm"),
    "HOT": ("Jours de chaleur extrême (> 90e centile 1991-2020)", "Extreme-heat days (> 1991-2020 90th percentile)", "days"),
    "SOIL": ("Humidité du sol racinaire (GWETROOT)", "Root-zone soil moisture (GWETROOT)", "0-1"),
}
HIGHLANDS = {"nord_ouest", "ouest", "sud_ouest", "adamaoua"}
BORDERS = {
    "extreme_nord": ("le Tchad, le Nigeria et la Commission du Bassin du Lac Tchad", "Chad, Nigeria and the Lake Chad Basin Commission"),
    "nord": ("le Tchad, le Nigeria et la RCA", "Chad, Nigeria and CAR"),
    "est": ("la RCA et le Congo", "CAR and Congo"),
    "nord_ouest": ("le Nigeria", "Nigeria"), "sud_ouest": ("le Nigeria", "Nigeria"),
    "sud": ("le Gabon et la Guinée équatoriale", "Gabon and Equatorial Guinea"),
}


def yearly(daily: pd.DataFrame) -> pd.DataFrame:
    """One row per year with every report variable."""
    year = daily.index.year
    baseline = daily.loc[f"{config.BASELINE_START}":f"{config.BASELINE_END}"]
    hot_threshold = baseline["T2M_MAX"].quantile(0.90)
    table = pd.DataFrame({
        "T2M": daily["T2M"].groupby(year).mean(),
        "TXX": daily["T2M_MAX"].groupby(year).max(),
        "TNN": daily["T2M_MIN"].groupby(year).min(),
        "RAIN": daily["PRECTOTCORR"].groupby(year).sum(),
        "HOT": (daily["T2M_MAX"] > hot_threshold).groupby(year).sum().astype(float),
        "SOIL": daily["GWETROOT"].groupby(year).mean(),
    })
    table.index.name = "year"
    return table


@lru_cache(maxsize=128)
def place_yearly(place_id: str) -> pd.DataFrame:
    return yearly(load_daily(place_as_region(place_id)))


@lru_cache(maxsize=16)
def variable_calibration(key: str) -> dict:
    """Best forecast method for one report indicator and its past errors, from the 10 regional capitals."""
    return calibrate([r for region in REGIONS for r in hindcast(place_yearly(region.id)[key])])


FORECAST_YEARS = 5


def _outlook(key: str, series: pd.Series, full: pd.Series) -> dict:
    """Next 5 years for one indicator: expected value, range from past errors, and how reliable it was."""
    calibration = variable_calibration(key)
    normal = full.loc[config.BASELINE_START:config.BASELINE_END]
    return {
        "forecast": forecast(series, FORECAST_YEARS, calibration, VARIABLES[key][2]),
        "backtest": backtest(full, FORECAST_YEARS, calibration["method"]),
        "normal": float(normal.mean()) if len(normal) else float(full.mean()),
    }


def linear_regression(series: pd.Series) -> dict:
    """Classic least-squares line (what most reports use), shown next to our robust test.

    Its p-value assumes independent years, so it is usually too optimistic for
    climate series; the 'significant' verdict in the app comes from the
    autocorrelation-corrected Mann-Kendall test instead.
    """
    result = linregress(series.index.to_numpy(dtype=float), series.to_numpy(dtype=float))
    years = [int(series.index[0]), int(series.index[-1])]
    half_width = float(student_t.ppf(0.975, len(series) - 2) * result.stderr)  # 95% interval of the slope
    return {
        "slope_per_decade": float(result.slope * 10),
        "slope_per_year": float(result.slope),
        "ci95_per_decade": [float((result.slope - half_width) * 10), float((result.slope + half_width) * 10)],
        "intercept": float(result.intercept),
        "r2": float(result.rvalue**2),
        "p_value": float(result.pvalue),
        "years": years,
        "fitted": [float(result.intercept + result.slope * y) for y in years],
    }


def _variable_block(key: str, series: pd.Series, lang: str) -> dict:
    fr, en, unit = VARIABLES[key]
    trend = trend_test(series)
    years = series.index
    steps = np.arange(len(series))
    residuals = series - (trend["intercept"] + trend["slope_per_year"] * steps)  # distance from the trend line
    z = (residuals - residuals.mean()) / residuals.std(ddof=1)
    span = min(10, len(series) // 2)  # 10 years each, fewer on short periods so they never overlap
    first, last = series.iloc[:span], series.iloc[-span:]
    start = int(years[0])
    bins = []
    for b in range(start, int(years[-1]) + 1, 5):
        chunk = series.loc[b : b + 4]
        if len(chunk):
            bins.append({"label": f"{b}-{min(b + 4, int(years[-1]))}", "mean": float(chunk.mean())})
    return {
        "key": key, "label": fr if lang == "fr" else en, "unit": unit,
        "mean": float(series.mean()), "median": float(series.median()),
        "min": float(series.min()), "min_year": int(series.idxmin()),
        "max": float(series.max()), "max_year": int(series.idxmax()),
        "std": float(series.std(ddof=1)),
        "trend": trend, "robustness": robustness(series, trend),
        "first_period": [int(first.index[0]), int(first.index[-1])], "first_mean": float(first.mean()),
        "last_period": [int(last.index[0]), int(last.index[-1])], "last_mean": float(last.mean()),
        "change": float(last.mean() - first.mean()),
        "outliers": [{"year": int(y), "value": float(series[y])} for y in series.index[np.abs(z) > 2]],
        "five_year": bins,
        "series": {"years": [int(y) for y in years], "values": series.round(3).tolist()},
        "line": trend_line(series, trend),
        "ols": linear_regression(series),
    }


def _climate_type(rain_mm: float, lang: str) -> str:
    kinds = [(600, "sahélien", "Sahelian"), (1000, "soudano-sahélien", "Sudano-Sahelian"),
             (1600, "soudanien / soudano-guinéen", "Sudanian / Sudano-Guinean"),
             (2500, "tropical humide", "humid tropical"), (1e9, "équatorial très humide", "very wet equatorial")]
    for limit, fr, en in kinds:
        if rain_mm < limit:
            return fr if lang == "fr" else en
    return ""


def _sig(block: dict, lang: str) -> str:
    p = block["trend"]["p_value"]
    if p < 0.001:
        return "p < 0,001" if lang == "fr" else "p < 0.001"
    if p < 0.05:
        return f"p = {p:.3f}".replace(".", "," if lang == "fr" else ".")
    return "non significatif" if lang == "fr" else "not significant"


def _num(value: float, digits: int, lang: str) -> str:
    text = f"{value:,.{digits}f}"
    return text.replace(",", " ").replace(".", ",") if lang == "fr" else text


def build_report(place_id: str, start: int, end: int, lang: str) -> dict:
    if place_id not in PLACES:
        raise KeyError(place_id)
    place = PLACES[place_id]
    data = place_yearly(place_id).loc[start:end]
    if len(data) < MIN_YEARS:
        raise ValueError(f"Choose at least {MIN_YEARS} years.")
    start, end = int(data.index[0]), int(data.index[-1])  # years actually covered by the data
    full = place_yearly(place_id)
    blocks = {key: {**_variable_block(key, data[key], lang), **_outlook(key, data[key], full[key])} for key in VARIABLES}
    region = REGIONS_BY_ID.get(place["region"])
    if region:
        region_name = region.name_fr if lang == "fr" else region.name_en
    else:  # capital of a neighbouring country
        region_name = place["country_fr"] if lang == "fr" else place["country_en"]
    t2m, txx, tnn, rain, hot, soil = (blocks[k] for k in VARIABLES)
    fr = lang == "fr"
    n = lambda v, d=1: _num(v, d, lang)  # noqa: E731
    signed = lambda v, d=1: ("+" if v > 0 else "") + _num(v, d, lang)  # noqa: E731

    # national context: the 10 regional capitals over the same years
    national = []
    for r in REGIONS:
        y = place_yearly(r.id).loc[start:end]
        national.append({"id": r.id, "name": r.capital, "T2M": float(y["T2M"].mean()), "RAIN": float(y["RAIN"].mean())})
    nat_t, nat_r = np.mean([x["T2M"] for x in national]), np.mean([x["RAIN"] for x in national])
    others = [x for x in national if x["id"] != place_id]  # a capital is not compared with itself
    hotter = sum(x["T2M"] > t2m["mean"] for x in others)
    wetter = sum(x["RAIN"] > rain["mean"] for x in national)

    climate = _climate_type(rain["mean"], lang)
    facts = []
    if fr:
        facts.append(f"Climat {climate} : {n(t2m['mean'])} °C en moyenne et {n(rain['mean'], 0)} mm de pluie par an "
                     f"({n(rain['mean'] / 365.25, 2)} mm/jour), sur {len(data)} années ({start}–{end}).")
        warming = "hausse" if t2m["trend"]["slope_per_decade"] > 0 else "baisse"
        facts.append(f"Température moyenne : {warming} de {n(abs(t2m['trend']['slope_per_decade']), 2)} °C par décennie ({_sig(t2m, lang)}), "
                     f"soit {signed(t2m['change'], 2)} °C entre {t2m['first_period'][0]}–{t2m['first_period'][1]} ({n(t2m['first_mean'], 2)} °C) "
                     f"et {t2m['last_period'][0]}–{t2m['last_period'][1]} ({n(t2m['last_mean'], 2)} °C).")
        recent = " — record récent" if txx["max_year"] >= end - 4 else ""
        facts.append(f"Chaleur extrême : le jour le plus chaud atteint en moyenne {n(txx['mean'])} °C par an, record de "
                     f"{n(txx['max'], 2)} °C en {txx['max_year']}{recent} ; tendance {signed(txx['trend']['slope_per_decade'], 2)} °C/décennie ({_sig(txx, lang)}).")
        facts.append(f"Amplitude thermique : {n(txx['mean'] - tnn['mean'])} °C en moyenne entre la nuit la plus froide "
                     f"({n(tnn['mean'])} °C) et le jour le plus chaud de l'année.")
        cv = rain["std"] / rain["mean"] * 100
        dry = data["RAIN"].nsmallest(2)
        facts.append(f"Pluie : tendance {signed(rain['trend']['slope_per_decade'], 0)} mm/décennie ({_sig(rain, lang)}) ; variabilité "
                     f"{'forte' if cv > 20 else 'modérée' if cv > 12 else 'faible'} ({n(cv, 0)} % d'une année à l'autre). "
                     f"Années les plus sèches : {dry.index[0]} ({n(dry.iloc[0], 0)} mm) et {dry.index[1]} ({n(dry.iloc[1], 0)} mm) ; "
                     f"la plus pluvieuse : {rain['max_year']} ({n(rain['max'], 0)} mm).")
        facts.append(f"Jours de chaleur extrême : {n(hot['first_mean'], 0)} par an en {hot['first_period'][0]}–{hot['first_period'][1]} "
                     f"contre {n(hot['last_mean'], 0)} en {hot['last_period'][0]}–{hot['last_period'][1]} ({_sig(hot, lang)}).")
        rank = hotter + 1
        facts.append(f"Comparaison nationale : {'+' if t2m['mean'] > nat_t else ''}{n(t2m['mean'] - nat_t, 1)} °C par rapport à la moyenne des 10 capitales régionales "
                     f"({rank}{'re' if rank == 1 else 'e'} plus chaude sur {len(others) + 1} lieux) et {n(rain['mean'] / nat_r * 100, 0)} % de leur pluie moyenne.")
        if soil["trend"]["significant"]:
            facts.append(f"Humidité du sol : {'en baisse' if soil['trend']['slope_per_year'] < 0 else 'en hausse'} "
                         f"({signed(soil['trend']['slope_per_decade'] * 100, 1)} pts/décennie, {_sig(soil, lang)}).")
        if t2m["robustness"]["status"] == "not_robust":
            facts.append("Prudence : la hausse de température ne se confirme pas depuis 2000 ; elle peut venir en partie du saut de 1998 dans les données MERRA-2.")
    else:
        facts.append(f"{climate.capitalize()} climate: {n(t2m['mean'])} °C on average and {n(rain['mean'], 0)} mm of rain per year "
                     f"({n(rain['mean'] / 365.25, 2)} mm/day), over {len(data)} years ({start}–{end}).")
        warming = "rising" if t2m["trend"]["slope_per_decade"] > 0 else "falling"
        facts.append(f"Mean temperature: {warming} by {n(abs(t2m['trend']['slope_per_decade']), 2)} °C per decade ({_sig(t2m, lang)}), "
                     f"i.e. {signed(t2m['change'], 2)} °C between {t2m['first_period'][0]}–{t2m['first_period'][1]} ({n(t2m['first_mean'], 2)} °C) "
                     f"and {t2m['last_period'][0]}–{t2m['last_period'][1]} ({n(t2m['last_mean'], 2)} °C).")
        recent = " — a recent record" if txx["max_year"] >= end - 4 else ""
        facts.append(f"Extreme heat: the hottest day reaches {n(txx['mean'])} °C on average each year, record "
                     f"{n(txx['max'], 2)} °C in {txx['max_year']}{recent}; trend {signed(txx['trend']['slope_per_decade'], 2)} °C/decade ({_sig(txx, lang)}).")
        facts.append(f"Temperature range: {n(txx['mean'] - tnn['mean'])} °C on average between the coldest night "
                     f"({n(tnn['mean'])} °C) and the hottest day of the year.")
        cv = rain["std"] / rain["mean"] * 100
        dry = data["RAIN"].nsmallest(2)
        facts.append(f"Rainfall: trend {signed(rain['trend']['slope_per_decade'], 0)} mm/decade ({_sig(rain, lang)}); "
                     f"{'high' if cv > 20 else 'moderate' if cv > 12 else 'low'} year-to-year variability ({n(cv, 0)}%). "
                     f"Driest years: {dry.index[0]} ({n(dry.iloc[0], 0)} mm) and {dry.index[1]} ({n(dry.iloc[1], 0)} mm); "
                     f"wettest: {rain['max_year']} ({n(rain['max'], 0)} mm).")
        facts.append(f"Extreme-heat days: {n(hot['first_mean'], 0)} per year in {hot['first_period'][0]}–{hot['first_period'][1]} "
                     f"versus {n(hot['last_mean'], 0)} in {hot['last_period'][0]}–{hot['last_period'][1]} ({_sig(hot, lang)}).")
        facts.append(f"National comparison: {'+' if t2m['mean'] > nat_t else ''}{n(t2m['mean'] - nat_t, 1)} °C versus the average of the 10 regional capitals "
                     f"(#{hotter + 1} hottest of {len(others) + 1} places) and {n(rain['mean'] / nat_r * 100, 0)}% of their average rainfall.")
        if soil["trend"]["significant"]:
            facts.append(f"Soil moisture: {'falling' if soil['trend']['slope_per_year'] < 0 else 'rising'} "
                         f"({signed(soil['trend']['slope_per_decade'] * 100, 1)} pts/decade, {_sig(soil, lang)}).")
        if t2m["robustness"]["status"] == "not_robust":
            facts.append("Caution: the temperature rise is not confirmed since 2000; part of it may come from the 1998 jump in the MERRA-2 data.")

    overview = _overview(place["name"], region_name, climate, blocks, len(data), start, end, int(data.isna().sum().sum()), lang)
    recommendations = _recommendations(place, blocks, rain["mean"], lang)
    return {
        "place": {**place, "region_name": region_name},
        "period": [start, end], "n_years": len(data), "n_records": int(len(data) * len(VARIABLES)), "missing": int(data.isna().sum().sum()),
        "climate_type": climate,
        "variables": list(blocks.values()),
        "recent": {"years": [int(y) for y in data.index[-6:]],
                   "rows": {k: data[k].iloc[-6:].round(2).tolist() for k in VARIABLES}},
        "national": national,
        "overview": overview,
        "facts": facts,
        "recommendations": recommendations,
        "source": f"NASA POWER / MERRA-2, daily, point {place['lat']}°N {place['lon']}°E",
    }


def _overview(name: str, region: str, climate: str, blocks: dict, n_years: int, start: int, end: int,
              missing: int, lang: str) -> str:
    """The opening paragraph: what the data covers and what it shows, in plain words."""
    fr = lang == "fr"
    words = {"T2M": ("la température moyenne", "average temperature"), "TXX": ("les pics de chaleur", "heat peaks"),
             "TNN": ("les nuits les plus froides", "the coldest nights"), "RAIN": ("la pluie annuelle", "annual rainfall"),
             "HOT": ("le nombre de jours de forte chaleur", "the number of very hot days"), "SOIL": ("l'humidité du sol", "soil moisture")}
    up, down, unsure = [], [], []
    for key, block in blocks.items():
        trend, word = block["trend"], words[key][0 if fr else 1]
        if not trend["significant"]:
            continue
        if block["robustness"]["status"] == "not_robust":
            unsure.append(word)
        else:
            (up if trend["slope_per_year"] > 0 else down).append(word)

    def join(items: list[str]) -> str:
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + (" et " if fr else " and ") + items[-1]

    cv = blocks["RAIN"]["std"] / blocks["RAIN"]["mean"] * 100
    parts = []
    if fr:
        text = (f"Le point NASA de {name} ({region}) couvre {n_years} années ({start}–{end}) "
                f"{'sans valeur manquante' if missing == 0 else f'avec {missing} valeur(s) manquante(s)'}. Il décrit un climat {climate}")
        if up:
            parts.append(f"une hausse statistiquement significative pour {join(up)}")
        if down:
            parts.append(f"une baisse statistiquement significative pour {join(down)}")
        text += (", marqué par " + " et ".join(parts)) if parts else ", sans changement statistiquement significatif sur cette période"
        text += f". La pluie varie {'fortement' if cv > 20 else 'modérément' if cv > 12 else 'peu'} d'une année à l'autre ({cv:.0f} %)."
        if unsure:
            text += f" Le changement apparent pour {join(unsure)} reste à confirmer : il ne se retrouve pas depuis 2000."
    else:
        text = (f"The NASA point for {name} ({region}) covers {n_years} years ({start}–{end}) "
                f"{'with no missing value' if missing == 0 else f'with {missing} missing value(s)'}. It describes a {climate} climate")
        if up:
            parts.append(f"a statistically significant rise in {join(up)}")
        if down:
            parts.append(f"a statistically significant fall in {join(down)}")
        text += (", marked by " + " and ".join(parts)) if parts else ", with no statistically significant change over this period"
        text += f". Rainfall varies {'strongly' if cv > 20 else 'moderately' if cv > 12 else 'little'} from year to year ({cv:.0f}%)."
        if unsure:
            text += f" The apparent change in {join(unsure)} is still to be confirmed: it does not show up since 2000."
    return text


def _recommendations(place: dict, blocks: dict, rain_mean: float, lang: str) -> list[dict]:
    fr = lang == "fr"
    t2m, txx, rain, soil, hot = blocks["T2M"], blocks["TXX"], blocks["RAIN"], blocks["SOIL"], blocks["HOT"]
    dry = rain_mean < 1000 or (rain["trend"]["significant"] and rain["trend"]["slope_per_year"] < 0) \
        or (soil["trend"]["significant"] and soil["trend"]["slope_per_year"] < 0)
    wet = rain_mean > 1600
    hot_signal = (t2m["trend"]["significant"] and t2m["trend"]["slope_per_year"] > 0) or txx["mean"] >= 38 \
        or (hot["trend"]["significant"] and hot["trend"]["slope_per_year"] > 0)
    region_id = place["region"]

    axes = []
    water = []
    if dry:
        water += [("Sécuriser l'eau : forages profonds solaires, réhabilitation des mares et retenues pour la saison sèche.",
                   "Secure water: solar-powered deep boreholes, restore ponds and small reservoirs for the dry season.", "drought"),
                  ("Citernes de récupération d'eau de pluie dans les écoles, centres de santé et marchés.",
                   "Rainwater-harvesting tanks at schools, clinics and markets.", "drought"),
                  ("Irrigation goutte-à-goutte sur les périmètres maraîchers pour limiter le gaspillage.",
                   "Drip irrigation on market gardens to cut water waste.", "drought")]
    if wet or rain["max"] > rain_mean * 1.4:
        water += [("Curer et agrandir caniveaux et canaux de drainage avant la saison des pluies.",
                   "Clean and widen drains and channels before the rainy season.", "flood"),
                  ("Libérer les zones inondables et entretenir digues et berges des cours d'eau.",
                   "Keep flood-prone zones free of buildings; maintain dykes and riverbanks.", "flood")]
    axes.append(("A", "Gestion de l'eau : sécheresses et crues", "Water management: droughts and floods", water))

    heat = []
    if hot_signal:
        heat += [(f"Plan « canicule » communal : alertes radio quand les maximales dépassent {txx['mean'] - 1:.0f} °C, îlots de fraîcheur (ombre + eau) dans marchés, gares et centres de santé.",
                  f"Municipal heat plan: radio alerts when maximum temperatures exceed {txx['mean'] - 1:.0f} °C, cool spots (shade + water) in markets, stations and clinics.", "heat"),
                 ("Bâtiments adaptés : toits isolés et ventilés, briques de terre comprimée plutôt que tôle nue dans les écoles et dispensaires.",
                  "Climate-adapted buildings: insulated, ventilated roofs and compressed-earth bricks instead of bare metal sheets in schools and clinics.", "heat"),
                 ("Adapter les horaires du travail en plein air et protéger personnes âgées et enfants.",
                  "Shift outdoor work hours and protect elderly people and children.", "heat")]
    else:
        heat.append(("Surveiller chaque année les températures : pas de hausse significative détectée sur la période choisie.",
                     "Monitor temperatures every year: no significant rise detected over the chosen period.", "heat"))
    axes.append(("B", "Chaleur extrême et santé publique", "Extreme heat and public health", heat))

    land = []
    if dry:
        land += [("Variétés à cycle court (mil, sorgho, niébé) pour les années déficitaires comme "
                  f"{rain['min_year']}.", f"Short-cycle varieties (millet, sorghum, cowpea) for deficit years like {rain['min_year']}.", "drought"),
                 ("Ceintures vertes et reboisement avec des espèces résistantes (acacias, neem, moringa) contre l'avancée du désert.",
                  "Green belts and tree planting with hardy species (acacia, neem, moringa) against desertification.", "drought")]
    else:
        land.append(("Agroforesterie et calendrier cultural ajusté aux saisons qui se décalent.",
                     "Agroforestry and a crop calendar adjusted to shifting seasons.", "drought"))
    if region_id in HIGHLANDS:
        land.append(("Pentes : murs de soutènement, terrasses et revégétalisation contre les glissements de terrain.",
                     "Slopes: retaining walls, terraces and replanting against landslides.", "landslide"))
    axes.append(("C", "Agriculture, environnement et sols", "Agriculture, environment and soils", land))

    gov = [("Système d'alerte précoce : suivre ces indicateurs NASA chaque saison avec les services météorologiques.",
            "Early-warning system: track these NASA indicators every season with the meteorological services.", None),
           ("Comité local climat associant habitants, agriculteurs, éleveurs, artisans du bâtiment et services de santé.",
            "Local climate committee bringing together residents, farmers, herders, builders and health services.", None)]
    if region_id in BORDERS:
        partners = BORDERS[region_id][0 if fr else 1]
        gov.append((f"Coopération transfrontalière sur l'eau, les pâturages et les alertes avec {partners}.",
                    f"Cross-border cooperation on water, grazing and alerts with {partners}.", None))
    axes.append(("D", "Gouvernance et alerte précoce", "Governance and early warning", gov))

    return [{"axis": code, "title": title_fr if fr else title_en, "items": [f_ if fr else e_ for f_, e_, _ in items]}
            for code, title_fr, title_en, items in axes if items]


def place_label(place: dict, lang: str) -> str:
    if place.get("foreign"):
        return f"{place['name']} ({place['country_fr'] if lang == 'fr' else place['country_en']})"
    region = REGIONS_BY_ID[place["region"]]
    return f"{place['name']} ({region.name_fr if lang == 'fr' else region.name_en})"


def compare_places(place_ids: list[str], variable: str, start: int, end: int, lang: str) -> dict:
    """Same indicator, same years, 1-4 places side by side (for the animated comparison chart)."""
    if variable not in VARIABLES:
        raise ValueError(f"Unknown variable '{variable}'")
    rows = []
    for pid in place_ids:
        if pid not in PLACES:
            raise KeyError(pid)
        series = place_yearly(pid).loc[start:end, variable]
        if len(series) < MIN_YEARS:
            raise ValueError(f"Choose at least {MIN_YEARS} years.")
        block = _variable_block(variable, series, lang)
        rows.append({
            "place": {**PLACES[pid], "label": place_label(PLACES[pid], lang)},
            **{k: block[k] for k in ("mean", "min", "min_year", "max", "max_year", "std", "trend", "robustness",
                                     "first_period", "first_mean", "last_period", "last_mean", "change", "series", "line")},
        })
    fr_label, en_label, unit = VARIABLES[variable]
    return {"variable": variable, "label": fr_label if lang == "fr" else en_label, "unit": unit, "places": rows}


def report_context(report: dict) -> str:
    """Plain-text version of the report for the AI write-up."""
    lines = [f"Place: {report['place']['name']} ({report['place']['region_name']}), {report['source']}, "
             f"{report['period'][0]}-{report['period'][1]}, {report['n_years']} years, {report['missing']} missing values. Climate type: {report['climate_type']}."]
    for v in report["variables"]:
        t = v["trend"]
        lines.append(f"{v['label']} [{v['unit']}]: mean {v['mean']:.2f}, median {v['median']:.2f}, min {v['min']:.2f} ({v['min_year']}), "
                     f"max {v['max']:.2f} ({v['max_year']}), std {v['std']:.2f}, trend {t['slope_per_decade']:+.3f}/decade p={t['p_value']:.4f} "
                     f"({'significant' if t['significant'] else 'not significant'}, since-2000 check: {v['robustness']['status']}), "
                     f"{v['first_period'][0]}-{v['first_period'][1]} mean {v['first_mean']:.2f} vs {v['last_period'][0]}-{v['last_period'][1]} {v['last_mean']:.2f}; "
                     f"outliers {v['outliers']}; 5-year means {[(b['label'], round(b['mean'], 2)) for b in v['five_year']]}; "
                     f"forecast {v['forecast']['years'][-1]} (method {v['forecast']['method']}): {v['forecast']['mean'][-1]:.2f} "
                     f"(80% range {v['forecast']['lo80'][-1]:.2f} to {v['forecast']['hi80'][-1]:.2f}), 1991-2020 normal {v['normal']:.2f}")
    lines += ["Key facts: " + " | ".join(report["facts"])]
    for axis in report["recommendations"]:
        lines.append(f"Recommendations {axis['axis']} {axis['title']}: " + " | ".join(axis["items"]))
    return "\n".join(lines)
