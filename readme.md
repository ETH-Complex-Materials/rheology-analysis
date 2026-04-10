# Rheology Analysis Interface

Interactive web app for analysing rheometer data exported from **Anton Paar** and **TA Instruments** instruments. Upload an `.xlsx` file and get interactive Plotly charts and downloadable results — no Python installation required for end users.

> **Authors:** Gabriel David (PhD, HHU Düsseldorf) · Rafael Libanori (ETH Zurich) · 2025
> **License:** MIT

---

## Supported test types

| Test | What is analysed |
|------|-----------------|
| Creep Recovery | Burgers (4-element), Maxwell, Kelvin-Voigt fits; elastic/viscoelastic/plastic fractions |
| Amplitude Sweep | G' and G'' vs strain; LVER detection (configurable deviation threshold) |
| Stress Relaxation | Burgers bi-exponential and Maxwell single-exponential fits |
| Frequency Sweep | G', G'', |eta*|, tan(delta) vs frequency; power-law fit; gel-point detection |
| Temperature Sweep | G', G'', tan(delta) vs temperature; gel-point (crossover) detection |

---

## Quick start

### Prerequisites

- Python 3.11 or newer
- A virtual environment (recommended)

### Install

```bash
cd rheology-webapp
python3 -m venv ../rheology-env
source ../rheology-env/bin/activate      # macOS / Linux
pip install -r requirements.txt
```

### Run

```bash
uvicorn app:app --port 2719
```

Open **http://localhost:2719** in any browser.

**ETH setup shortcut** (uses the pre-built `rheology-env-modern` venv one level up):

```bash
VENV="../rheology-env-modern" && "$VENV/bin/uvicorn" app:app --port 2719
```

### Docker

```bash
docker build -t rheology-app .
docker run -p 2719:8080 rheology-app
# open http://localhost:2719
```

---

## How to use the app

### 1 — Upload a file

Drag and drop an `.xlsx` file onto the upload zone, or click to browse.
The file is parsed in memory and never written to disk.

### 2 — Sheet selection

The sheet list is organised in a **three-level hierarchy**:

```
Material  (e.g. "Agarose5pct")
  └── Replicate  (e.g. "S1", "S2", "S3")
        ├── Creep phase       (segment 0, t = 0 – 285 s)
        └── Recovery phase    (segment 1, t = 330 – 900 s)
```

Click the **chevron (▶)** next to a material or replicate to expand it.
Ticking/unticking a parent checkbox cascades to all children.

> Sheets are grouped as `<Material>_<Replicate>` (e.g. `Agarose5_S1`).
> Sheets that do not match this pattern appear as standalone entries.

### 3 — Choose the test type

Select the correct test type from the **Test type** dropdown.
Always confirm this matches your experiment — the app does not force auto-detection.

### 4 — Set parameters

**Creep Recovery**

| Parameter | Description |
|-----------|-------------|
| t_release (s) | Time at which stress is removed. Leave blank to auto-detect from the strain peak. |
| Transition prune window (s) | Data removed around t_release to exclude the transient oscillation spike. Typical: 2–5 s. |
| Include Maxwell model | Adds a 2-element Maxwell fit (single-exponential). |
| Include Kelvin-Voigt model | Adds a Kelvin-Voigt fit (predicts full elastic recovery). |
| Overlay all samples | Plots all replicates on the same axes. |

**Fitting window sliders** (Creep Recovery and Stress Relaxation):

- **Start prune** — drag right to exclude the first N seconds of a segment (remove loading artefacts).
- **End prune** — drag left to exclude the last N seconds of a segment.
- **Around t_release** — double-ended slider to exclude a window centred on the stress release (the orange spike). Appears automatically when both Creep and Recovery segments are selected.

All slider changes auto-trigger a re-analysis after the first manual run.

**Amplitude Sweep**

| Parameter | Description |
|-----------|-------------|
| Plateau points (first N) | Number of low-strain points used to compute G'_0. |
| Deviation threshold (%) | LVER ends when G' deviates from G'_0 by more than this value. Default: 5 %. |

**Frequency / Temperature Sweep** — toggle optional plots (tan delta, |eta*|, Cole-Cole).

### 5 — Run analysis

Click **Run Analysis**. Results appear as tabbed plots in the right panel.

Use the **Lin/Log axis toolbar** above the tabs to switch axis scales on any plot.

After the first run, any change to parameters, sliders, or sheet selection **automatically re-runs** the analysis (700 ms debounce).

### 6 — Download results

Click **Excel** or **CSV** to download the fitted parameter table for the current analysis.

### 7 — Custom plot

Expand the **Custom Plot** card to plot any two columns from the raw data against each other (useful for inspecting raw time-series before analysis).

### 8 — Data preview

Click **Data Preview** to inspect the raw parsed table for any sheet.

---

## File format

The app accepts standard rheometer exports (`.xlsx`):

- **Anton Paar:** default export with the `"Interval data:"` row marker.
- **TA Instruments:** any export where the header row contains recognisable column names.

### Recognised column names

| Canonical | Accepted aliases |
|-----------|-----------------|
| Time | Time, time, t (s), t(s) |
| Storage Modulus | G', G′, G' (Pa), Storage modulus |
| Loss Modulus | G'', G″, G'' (Pa), Loss modulus |
| Shear Strain | Strain, gamma, Strain (%) |
| Shear Stress | Stress, tau, Stress (Pa) |
| Creep Compliance | J(t), Compliance |
| Angular Frequency | omega, Frequency (rad/s) |
| Temperature | Temp, T (°C) |
| Complex Viscosity | |eta*|, Eta* (Pa.s) |

### Interval / segment detection

The parser automatically splits each sheet into segments when:

- The time column **resets** (decreases) — standard between consecutive measurement intervals.
- There is a **large time gap** (> 20 s or > 15× the typical time step) — used for creep/recovery data where creep ends at ~285 s and recovery resumes at ~330 s without a time reset.

---

## Project structure

```
rheology-webapp/
├── app.py                  # FastAPI app (all HTTP endpoints)
├── analysis/
│   ├── parser.py           # Excel parser; interval/gap detection
│   ├── creep.py            # Burgers / Maxwell / Kelvin-Voigt fitting
│   ├── amplitude.py        # LVER detection
│   ├── relaxation.py       # Stress relaxation fitting
│   ├── frequency.py        # Frequency sweep analysis
│   └── temperature.py      # Temperature sweep analysis
├── static/
│   ├── index.html          # Single-page app shell (Bootstrap 5)
│   ├── app.js              # All frontend logic
│   └── style.css           # Custom styles
├── requirements.txt
├── Dockerfile
└── README.md
```

## API reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the frontend |
| `/api/parse` | POST | Upload `.xlsx`, return sheet metadata + segment info |
| `/api/analyze` | POST | Run analysis, return Plotly figure JSON |
| `/api/download` | POST | Run analysis, return Excel or CSV results |
| `/api/rawplot` | POST | Build a custom plot from raw (unanalysed) data |
