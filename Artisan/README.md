# ArtisanConnect — NASA climate trends for Cameroon

NASA Space Apps Challenge 2026 · **Be An Earth System Trend Detective!**

ArtisanConnect looks at 45 years of NASA daily data (1981–2025) for Cameroon's 10 regions, several towns and neighbouring capitals. For each place it shows what is changing (heat, rain, drought, landslide risk), whether the change is statistically real, what to expect in the next years, and what local authorities can do about it. Everything is explained in plain French or English, and every number can be checked.

> **Data rule:** only official NASA data (NASA POWER, MERRA-2) and resources listed by the challenge. See [DATA_SOURCES.md](DATA_SOURCES.md).

## What the app does

| Page | What you get |
|---|---|
| **Accueil** (home) | 3D map of Cameroon coloured by risk score (/100) for the chosen hazard, and a search box for towns |
| **Synthèse** | Report for one place: statistics table, trend and linear regression, 5-year means, key facts, forecasts 2026–2030, recommendations, printable dated bulletin, CSV download |
| **Comparer** | 2–3 places side by side, year by year (default: Yaoundé, N'Djamena, Kousséri) |
| **Prévisions** | Forecast with an honest 80% range, the method chosen by testing on the past, and how reliable it is |
| **Découvertes** | Automatic findings across 200 series, with false-discovery control |
| **Fiabilité** | Proof page: 7 checks that the calculations and methods are correct (results match reference libraries and the NASA CSV exports) |
| **Assistant IA** | An AI agent that answers questions such as *"from 2012 to 2018, how did heat and humidity change?"* by calling prewritten calculation tools on the NASA data. It never invents numbers, and each answer lists the tools it used |

### The science in one paragraph

Trends are tested with **Mann-Kendall**, corrected for year-to-year memory (autocorrelation), and their size is measured with the **Sen slope**. A **linear regression** with its 95% interval is shown next to them. Each trend is re-checked on the years since 2000. Sudden jumps are separated from gradual change with **Pettitt** and a BIC test. When many series are tested at once, **Benjamini-Hochberg** limits false discoveries.

Forecasts come from a small "tournament": trend + memory, exponential smoothing, persistence and the 30-year mean are each scored on past years, and the best one is used. Their ranges come from the errors measured on those past years.

The **risk score /100** combines the trend (and how certain it is) with how far the last 3 years are from the 1991–2020 normal. The labels "weak signal / not proven" describe the climate signal, not the calculation: they mean the year-to-year ups and downs are too large to call the change a trend yet.

## Project structure

```
Artisan/
├── backend/          FastAPI server and all the analysis (Python)
│   ├── main.py         API routes + serves the website
│   ├── nasa_power.py   downloads and caches NASA POWER daily data
│   ├── stats.py        Mann-Kendall, Sen, regression, Pettitt, FDR
│   ├── risk.py         risk score /100
│   ├── forecast.py     forecast methods, back-tests, calibrated ranges
│   ├── report.py       the Synthèse report
│   ├── validation.py   the 7 proof checks (python -m backend.validation)
│   ├── agent.py        AI agent and its tools
│   └── chat.py         connection to the AI model (OpenRouter)
├── frontend/         website (plain JavaScript, Plotly, three.js), FR/EN
├── data/             NASA CSV exports + cache/ (downloaded NASA data, committed so the app starts fast)
├── tests/            63 automated tests (pytest)
├── run.py / run.bat  one-command local start
├── railway.json      Railway deploy settings
└── Procfile          start command (used by Railway and other hosts)
```

## Install and run locally

You need **Python 3.13** (3.11+ should work) and an internet connection the first time. The repository already includes the NASA data cache, so the first start is fast.

**Windows, easiest:** double-click `run.bat`. The first time, it creates the virtual environment and installs the packages.

**Any system, by hand** (from the `Artisan` folder):

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Then start the app (on macOS/Linux, use `.venv/bin/python`):

```bash
.venv\Scripts\python.exe run.py
```

The app opens at **http://127.0.0.1:8000**. Press Ctrl+C to stop it.

### AI features (optional)

The AI pages need a free [OpenRouter](https://openrouter.ai) key. Everything else works without one.

1. Copy `.env.example` to `.env`.
2. Put your key after `OPENROUTER_API_KEY=`.

Never commit `.env`; it is already in `.gitignore`.

| Variable | Required | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | for the AI pages | — |
| `OPENROUTER_MODEL` | no | `google/gemma-4-31b-it:free` |
| `OPENROUTER_FALLBACK_MODEL` | no | `nvidia/nemotron-3-ultra-550b-a55b:free` |

### Tests and checks

```bash
.venv\Scripts\python.exe -m pytest -q
```

```bash
.venv\Scripts\python.exe -m backend.validation
```

## Deploy (Railway)

The app lives in the `Artisan/` **subfolder** of the repository. The rest of the repository (`MVP/`, `research/`) is earlier prototype work and is not deployed.

1. On [railway.com](https://railway.com), sign in with GitHub and choose **New Project → Deploy from GitHub repo**, then pick this repository.
2. In the service, open **Settings** and set:
   - **Source → Root Directory:** `/Artisan`. Railway then builds only this folder: it finds `requirements.txt` and `.python-version` and installs Python.
   - **Config-as-code → Railway Config File:** `/Artisan/railway.json`. Railway does not look for this file inside the Root Directory on its own, so give it the full path. (If you skip this, the `Procfile` still gives Railway the right start command.)
   - **Source → Watch Paths:** `/Artisan/**`. Railway then redeploys only when the app changes, not when `MVP/` or `research/` change.
3. In **Variables**, add `OPENROUTER_API_KEY` (and the two model variables if you want to change them).
4. In **Settings → Networking**, click **Generate Domain** to get a public link.
5. Every push to `main` redeploys automatically. The deploy is live once `/api/regions` answers (the health check in `railway.json`).

The server starts with:

```
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Any host that can run Python can use this same command from the `Artisan` folder, for example Render or Fly.io.

## Team & credits

NASA Space Apps Challenge 2026 entry. Data: NASA POWER (NASA Langley Research Center), MERRA-2 (NASA GMAO). Full list of sources and methods: [DATA_SOURCES.md](DATA_SOURCES.md). Demo walkthrough: [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
