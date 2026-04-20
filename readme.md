# Rheology Analysis Interface

Interactive web app for analysing rheometer data exported from **Anton Paar** and **TA Instruments** instruments. Upload an `.xlsx` file and get interactive Plotly charts and downloadable results — no Python installation required for end users.

> **Authors:** Gabriel David (PhD, HHU Düsseldorf) · Rafael Libanori (ETH Zurich) · 2026
> **License:** MIT

---

## Supported test types

| Test | What is analysed |
|------|-----------------|
| Creep Recovery | Burgers, Maxwell, Kelvin-Voigt, Zener (SLS) fits; elastic / viscoelastic / plastic fractions |
| Amplitude Sweep | G' and G'' vs strain; LVER detection (configurable deviation threshold) |
| Stress Relaxation | Burgers, Maxwell, Kelvin-Voigt, Zener (SLS) fits; ε₀ auto-inferred from data |
| Frequency Sweep | G', G'', \|η*\|, tan(δ) vs frequency; Cole-Cole plot |
| Temperature Sweep | G', G'', tan(δ) vs temperature; gel-point (crossover) detection |

---

## Quick start

### Prerequisites

- Python 3.11 or newer
- A virtual environment (recommended)

### venv install

To install the application:

```bash
cd rheology-webapp
python3 -m venv ../rheology-env
source ../rheology-env/bin/activate      # macOS / Linux
pip install -r requirements.txt
```

Then to run it:

```bash
uvicorn app:app --port 2719
```

Open **http://localhost:2719** in any browser.

**ETH setup shortcut** (uses the pre-built `rheology-env-modern` venv one level up):

```bash
VENV="../rheology-env-modern" && "$VENV/bin/uvicorn" app:app --port 2719
```

### Docker install and run

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

#### Creep Recovery

| Parameter | Description |
|-----------|-------------|
| t_release (s) | Time at which stress is removed. Leave blank to auto-detect (global maximum of Shear Strain for t > 5 s). |
| Include Maxwell model | Adds a 2-element Maxwell fit (single-exponential). |
| Include Kelvin-Voigt model | Adds a Kelvin-Voigt fit (predicts full elastic recovery). |
| Include Zener model (SLS) | Adds a Standard Linear Solid fit (permanent spring ∥ Maxwell branch). Predicts complete recovery (no permanent deformation). 3 free parameters: G_perm, G_trans, η_trans. |
| Overlay all samples | Plots all replicates on the same axes. |
| Combine segments | Merges multiple selected intervals (creep + recovery) into one continuous time series before fitting. |

Inferred values displayed **before analysis**:

- **σ₀** — applied stress, inferred as the median of the first 10 positive Shear Stress values. Falls back to a `<value>Pa` pattern in the filename.
- **t_release** — auto-detected as the time of the global Shear Strain maximum for t > 5 s.

**Pruning sliders** (point-index based, generalise across experiments with different time steps):

- **Zone 1 — Start prune (N pts)** — excludes the first N data points of the series (loading transient artefact). Range: 0 – 100 pts.
- **Zone 2 — After t_release (N pts)** — excludes the first N data points after t_release (stress-release oscillation spike). Range: 0 – 150 pts.

The **Shear Strain vs Time** preview plot is generated automatically when a Creep Recovery file is loaded, allowing you to validate σ₀ and t_release and set the pruning sliders before clicking Run Analysis.

**Output tabs:**

| Tab | Content |
|-----|---------|
| Data Table | Raw parsed data for the selected sheet(s). |
| Time Series | Shear Strain vs Time preview (same as pre-analysis plot). |
| Creep/Recovery Fits | Shear Strain (absolute) vs Time with Burgers fit and optional Maxwell / Kelvin-Voigt / Zener overlays. R² scores in the plot title. |
| Regression Parameters | Table of fitted parameters (G1, η1, G2, η2, G_perm, G_trans, η_trans, tauZ) for all models and replicates. |
| Recovery Components (Burgers) | Stacked bar chart + summary table (mean ± std) partitioning total creep deformation into elastic, viscoelastic, and plastic fractions (%) derived analytically from the Burgers fit. |
| Recovery Components (by hand) | Per-sample interactive view: define two Shear Strain thresholds per replicate — **ε₁** (end of elastic recovery) and **ε₂** (permanent deformation) — and fractions are computed in real time. A comparison column shows the corresponding Burgers fractions side-by-side. |

All parameter changes and slider adjustments auto-trigger a re-analysis after the first manual run.

#### Amplitude Sweep

| Parameter | Description |
|-----------|-------------|
| Plateau points (first N) | Number of low-strain points used to compute G'₀. |
| Deviation threshold (%) | LVER ends when G' deviates from G'₀ by more than this value. Default: 5 %. |

**Output tabs:** Data Table · Amplitude Sweep (G', G'' vs strain, log/log) · LVER Results.

#### Stress Relaxation

| Parameter | Description |
|-----------|-------------|
| Applied strain ε₀ | Imposed strain (absolute, dimensionless). Inferred from the modal value of the Shear Strain column ÷ 100. Override if the inferred value is incorrect. |
| Include Maxwell model | Single-exponential decay: σ(t) = G ε₀ exp(−t/τ). |
| Include Kelvin-Voigt model | Constant-stress prediction under strain control (elastic-only baseline). |
| Include Zener model (SLS) | σ(t) = ε₀ [G_perm + G_trans · exp(−t/τ_Z)]. Relaxes to a finite equilibrium plateau. 3 free parameters: G_perm, G_trans, η_trans. |
| Overlay all samples | Plots all replicates on the same axes. |

Inferred value displayed **before analysis**: **ε₀** — modal value of Shear Strain ÷ 100.

**Start prune slider** — discrete positions correspond to the first 100 actual Time values in the file, allowing precise exclusion of the initial loading ramp.

**Output tabs (in order):**

| Tab | Content |
|-----|---------|
| Data Table | Raw parsed data for the selected sheet(s). |
| Relaxation Plot | Shear Stress vs Time preview with shaded pruned region. |
| Stress Relaxation Fits | Shear Stress vs Time with Burgers fit and optional Maxwell / Kelvin-Voigt / Zener overlays. R² scores in the plot title. |
| Regression Parameters | Table of fitted parameters (G1, η1, G2, η2, tau1, tau2, G_perm, G_trans, η_trans, tauZ) for all models and replicates. |

#### Frequency Sweep

Toggle optional plots: tan(δ), |η*|, Cole-Cole.

**Output tabs:** G' and G'' · tan(δ) · |η*| · Cole-Cole (depending on selected options).

#### Temperature Sweep

Toggle optional plot: tan(δ).

**Output tabs:** G', G'', tan(δ) vs Temperature · optional tan(δ) panel.

### 5 — Run analysis

Click **Run Analysis**. Results appear as tabbed plots in the right panel.

Use the **Lin/Log axis toolbar** above the tabs to switch axis scales on any plot.

After the first run, any change to parameters, sliders, or sheet selection **automatically re-runs** the analysis (700 ms debounce).

### 6 — Download results

Click **Excel** or **CSV** to download the analysis results. For Creep Recovery, the export contains three sheets / files: **Fitted_Parameters** (σ₀, t_release, G1/η1/G2/η2, R² per model), **Recovery_Components_Burgers** (elastic / viscoelastic / plastic fractions with mean ± std), and **Recovery_Components_ByHand** (ε₁, ε₂, ε_total and fractions from the by-hand thresholds). The CSV format produces a **ZIP archive** containing one `.csv` per sheet; Excel produces a single multi-sheet `.xlsx`.

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
- There is a **large time gap** (> 20 s or > 15× the typical time step) — applies to most test types. **Creep Recovery data is intentionally kept as a single continuous segment** (no gap-based splitting) to avoid discarding data points around the creep → recovery transition.

---

## Project structure

```
rheology-webapp/
├── app.py                  # FastAPI app (all HTTP endpoints)
├── analysis/
│   ├── parser.py           # Excel parser; interval/gap detection
│   ├── creep.py            # Burgers / Maxwell / Kelvin-Voigt / Zener fitting
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
