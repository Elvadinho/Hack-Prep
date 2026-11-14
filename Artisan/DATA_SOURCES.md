# Artisan — Data Sources & References

NASA Space Apps Challenge 2026 · Challenge: **Be An Earth System Trend Detective!**
Project: **ArtisanConnect Geo Intelligence (Artisan)** — natural-hazard trend detection and prevention for Cameroon's 10 regions.

> **Data rule:** this project uses **only NASA official data** and resources listed by the challenge. No other data source is imported.
> Keep this file updated whenever a dataset, variable or date range changes. Copy the tables below into the submission's "Resources used" field.

---

## 1. Data used (all NASA official)

| # | Resource | Listed by challenge? | What we use | Why we use it | Access |
|---|---|---|---|---|---|
| 1 | **NASA POWER API** — Prediction Of Worldwide Energy Resources (NASA Langley Research Center); meteorology from **MERRA-2** | NASA official (not on the list) | Daily `T2M` (air temperature 2 m), `T2M_MAX`, `PRECTOTCORR` (precipitation), `GWETROOT` (root-zone soil wetness), 1991–2025, one point per region | Free, no key, global, daily → powers the **live / dynamic** part of the app | https://power.larc.nasa.gov/ — API docs: https://power.larc.nasa.gov/docs/services/api/ |
| 2 | **Giovanni** (NASA GES DISC) | ✅ Yes | Area-averaged monthly time series per region, exported as CSV: **GPM IMERG** precipitation, **MODIS NDVI** (vegetation), optional **MODIS LST** (land surface temperature) | Satellite observations that cross-check POWER (model) and add vegetation stress for drought → the **exported data** part | https://giovanni.gsfc.nasa.gov/ |
| 3 | **Hydrology Time Series** (NASA GES DISC) | ✅ Yes | **GLDAS** soil moisture and runoff series for flood / drought regions | Hydrological evidence for the flood and drought scores | https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Time%20Series |
| 4 | **AppEEARS** (NASA LP DAAC / Earthdata) | ✅ Yes | Backup extraction of MODIS NDVI / LST per region if Giovanni area export is unavailable | Same MODIS products, point / area extraction | https://appeears.earthdatacloud.nasa.gov/ |
| 5 | **NASA Global Landslide Catalog** (NASA GSFC, COOLR) | NASA official (not on the list) | Recorded landslide events in Cameroon (date, coordinates, trigger) | Only NASA record of real landslide occurrences; validates the rainfall-trigger indicator | NASA Landslides / data.nasa.gov — exact URL recorded in Lesson 6 when downloaded |

Region locations: the coordinates of the 10 regional capitals (Maroua, Garoua, Ngaoundéré, Bertoua, Yaoundé, Douala, Buea, Bamenda, Bafoussam, Ebolowa) are entered manually; the map displays the **NASA POWER / MERRA-2 grid cell (0.5° × 0.625°)** around each one. No external boundary files are used.

---

## 2. Methods & references (cited, no data imported)

| Resource | Listed? | How it is used |
|---|---|---|
| *Time-Series Analysis of Remotely-Sensed SeaWiFS Chlorophyll in River-Influenced Coastal Regions* — NASA NTRS 20090042747 — https://ntrs.nasa.gov/api/citations/20090042747/downloads/20090042747.pdf | ✅ Yes | NASA precedent for building time series and testing significance; basis of our method |
| *Statistical test methods to detect trends in time series data* — https://medium.com/@snp.kriss/statistical-test-methods-to-detect-trends-in-time-series-data-b361a0ec530b | ✅ Yes | Mann-Kendall test and Sen's slope |
| *A Comprehensive Guide to Statistical Significance* — https://www.statsig.com/perspectives/a-comprehensive-guide-to-statistical-significance | ✅ Yes | Plain-language wording of p-values in the app |
| Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica*, 13, 245–259; Kendall, M. G. (1975). *Rank Correlation Methods*. | — | Mann-Kendall trend test (via `pymannkendall`) |
| Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *JASA*, 63, 1379–1389. | — | Robust trend magnitude (per decade) |
| Santer, B. D. et al. (2000). Statistical significance of trends and trend differences in layer-average atmospheric temperature time series. *JGR*, 105(D6), 7337–7356. | — | Effective-sample-size correction for autocorrelation: variance × (1+r₁)/(1−r₁) |
| Marriott, F. H. C. & Pope, J. A. (1954). Bias in the estimation of autocorrelations. *Biometrika*, 41, 390–402. | — | Small-sample bias correction of r₁: r₁ + (1+4r₁)/n |

**Method validation (in `tests/test_stats.py`):** 500 simulated no-trend series × 35 years with autocorrelation 0 / 0.3 / 0.6 → false-alarm rate 3–5 % (target 5 %). We tested and rejected `pymannkendall`'s Hamed-Rao (12.7 % at r=0.3, 20 % at r=0.6), trend-free pre-whitening (12.6 % / 32.8 %) and Yue-Wang (> 40 %) because they flag false trends far too often on 35-year series.

---

## 3. Challenge resources reviewed but not used in v1 (and why)

| Resource | Reason |
|---|---|
| NOAA Climate Data Online — https://www.ncei.noaa.gov/cdo-web/ | Few Cameroon stations with long records; may be used later only to validate one city |
| KNMI Climate Explorer — https://climexp.knmi.nl/ | Used at most to manually cross-check trends; no data imported |
| CSA RADARSAT Constellation Mission — https://donnees-data.asc-csa.gc.ca/en/dataset/rcm | SAR processing out of scope for v1; candidate for flood-extent mapping later |
| Geo.ca — http://geo.ca/ | Canada-only data |
| SWOT mission — https://www.asc-csa.gc.ca/eng/satellites/swot/ | Future work: Lake Chad and river water levels |
| CSA ecosystem monitoring — https://www.asc-csa.gc.ca/eng/satellites/everyday-lives/monitoring-and-protecting-our-ecosystems-from-space.asp | Background reading |
| CSA SAR Python tutorial — https://github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial | Future SAR extension |

---

## 4. Software & services (not data)

FastAPI, Uvicorn, httpx, pandas, NumPy, SciPy, pymannkendall, python-dotenv, Leaflet, Plotly, and **OpenRouter** (AI language model for the explanatory chatbot — it only rephrases results computed from the NASA data above).

## 5. Other content

- **Artisan directory** (`data/artisans.json`): fictional demonstration entries only — no real people or personal data.
- **Pre-existing work:** an earlier independent prototype (`MVP/`, created 2026-11-07) explored the same challenge; to be declared per Space Apps rules. `Artisan/` is the new implementation.
