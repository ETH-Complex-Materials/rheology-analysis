"""
FastAPI backend for the Rheology Analysis Web App.
"""
import io
import json
import math
import zipfile
from collections import defaultdict
from typing import Annotated

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from analysis.parser import (detect_test_type, extract_sheet_data, get_data_df,
                              get_interval_info, get_units, split_intervals)
from analysis.amplitude import analyze_lver, build_amplitude_figures
from analysis.creep import (analyze_creep_recovery, build_creep_figures,
                             build_recovery_component_figures, evaluate_recovery_components,
                             infer_sigma0, infer_t_release)
from analysis.frequency import analyze_frequency_sweep, build_frequency_figures
from analysis.relaxation import analyze_stress_relaxation, build_relaxation_figures, infer_eps0
from analysis.temperature import analyze_temperature_sweep, build_temperature_figures

app = FastAPI(title="Rheology Analysis API")

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Helper — make data JSON-serializable
# ---------------------------------------------------------------------------

def _sanitize(obj):
    """Recursively replace NaN/Inf (both Python native and numpy) with None."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, np.floating):
        return None if (np.isnan(obj) or np.isinf(obj)) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return _sanitize(obj.tolist())
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _jsonify(obj):
    return _sanitize(obj)


def _short_sample_name(full_name: str) -> str:
    """Extract relative name from Project:::Test (Type) format."""
    name_str = str(full_name)
    if ":::" in name_str:
        p = name_str.split(":::")[-1]
        if "(" in p:
            p = p.split("(")[0].strip()
        return p
    return name_str

def _build_blocked_export_df(results, test_type):
    """Build a non-tabular DataFrame with blocks per sample for easier reading."""
    rows = []
    y_label = "Strain (%)" if test_type == "creep_recovery" else "Stress (Pa)"
    y_key = "strain" if test_type == "creep_recovery" else "stress"
    
    models = [("Burgers Fit", "fitted_data_burgers"), 
              ("Maxwell Fit", "fitted_data_maxwell"), 
              ("Kelvin-Voigt Fit", "fitted_data_kelvin")]
    
    for res in results:
        rows.append(["Sample", _short_sample_name(res["Sample"])])
        rows.append([]) # empty
        
        headers = ["Time (s)", f"Experimental {y_label}"]
        active_keys = []
        for label, m_key in models:
            if res.get(m_key, {}).get(y_key) is not None:
                headers.append(f"{label} ({y_label})")
                active_keys.append(m_key)
        rows.append(headers)
        
        t = res["experimental_data"]["t"]
        y = res["experimental_data"][y_key]
        for i in range(len(t)):
            data_row = [t[i], y[i]]
            for k in active_keys:
                data_row.append(res[k][y_key][i])
            rows.append(data_row)
        
        rows.append([]) # spacer
        rows.append([]) # spacer
        
    return pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# Analysis dispatch helper
# ---------------------------------------------------------------------------

def _extract_raw_series(test_type: str, dataframes_list: list, units: dict) -> list[dict]:
    """Return unfiltered time-series data for the interactive exclusion-zone plot."""
    y_col_map = {
        'creep_recovery':    'Shear Strain',
        'stress_relaxation': 'Shear Stress',
    }
    y_col_name = y_col_map.get(test_type)
    if not y_col_name:
        return []
    series = []
    for name, df in dataframes_list:
        if 'Time' not in df.columns or y_col_name not in df.columns:
            continue
        t = pd.to_numeric(df['Time'], errors='coerce')
        y = pd.to_numeric(df[y_col_name], errors='coerce')
        mask = np.isfinite(t) & np.isfinite(y)
        t_vals = t[mask].tolist()
        y_vals = y[mask].tolist()
        if not t_vals:
            continue
        y_unit = units.get(y_col_name, '')
        series.append({
            'name':    _short_sample_name(name),
            't':       t_vals,
            'y':       y_vals,
            'y_label': f"{y_col_name} ({y_unit})" if y_unit else y_col_name,
        })
    return series


def _burgers_fracs(params: dict, t_rel: float) -> dict | None:
    """Compute elastic/viscoelastic/plastic fractions from fitted Burgers params."""
    try:
        G1   = max(float(params.get("G1 (Pa)",   0)), 1e-9)
        eta1 = max(float(params.get("η1 (Pa·s)", 0)), 1e-9)
        G2   = max(float(params.get("G2 (Pa)",   0)), 1e-9)
        eta2 = max(float(params.get("η2 (Pa·s)", 0)), 1e-9)
        tau2 = eta2 / G2
        eps_el = 1.0 / G1
        eps_pl = t_rel / eta1
        eps_vi = (1.0 / G2) * (1.0 - math.exp(-t_rel / tau2))
        total  = eps_el + eps_pl + eps_vi
        if total <= 0 or not math.isfinite(total):
            return None
        return {
            "elastic":      round(100 * eps_el / total, 2),
            "viscoelastic": round(100 * eps_vi / total, 2),
            "plastic":      round(100 * eps_pl / total, 2),
        }
    except Exception:
        return None


def _dispatch(test_type: str, dataframes_list: list, p: dict, units: dict) -> tuple:
    """
    Run analysis for a given test_type and return (figures, labels, extra).
    p contains analysis parameters (may be empty — defaults are applied per type).
    extra is a dict of additional data included in the API response (e.g. creep_samples).
    """
    if test_type == "creep_recovery":
        t_release_raw = p.get("t_release", "auto")
        t_release  = None if t_release_raw == "auto" else float(t_release_raw)
        en_maxwell = bool(p.get("enable_maxwell", False))
        en_kelvin  = bool(p.get("enable_kelvin", False))
        en_zener   = bool(p.get("enable_zener",  False))
        prune_win  = float(p.get("prune_window", 0.0))

        results = analyze_creep_recovery(
            dataframes_list, t_release,
            drop_index=p.get("drop_index", []),
            enable_maxwell=en_maxwell,
            enable_kelvin=en_kelvin,
            enable_zener=en_zener,
            prune_window=prune_win,
            exclude_ranges=p.get("exclude_ranges", []),
            prune_start_n=int(p.get("prune_start_n", 0)),
            prune_release_n=int(p.get("prune_release_n", 0)),
        )
        overlay = bool(p.get("overlay", False))
        multi, table = build_creep_figures(results, units, en_maxwell, en_kelvin,
                                           enable_zener=en_zener, overlay=overlay)
        components = evaluate_recovery_components(results)
        comp_fig = build_recovery_component_figures(components)

        # Build per-sample data for the "by hand" recovery components tab.
        # Uses raw (unpruned) dataframes so the full recovery curve is visible.
        res_by_name = {r["Sample"]: r for r in results}
        creep_samples = []
        for sample_name, df in dataframes_list:
            sname = str(sample_name)
            res = res_by_name.get(sname)
            if res is None:
                continue
            t_rel = float(res.get("t_release", 0))

            t_ser = pd.to_numeric(df["Time"],        errors="coerce")
            s_ser = pd.to_numeric(df["Shear Strain"], errors="coerce") / 100.0
            valid = t_ser.notna() & s_ser.notna()
            t_arr = t_ser[valid].tolist()
            s_arr = s_ser[valid].tolist()
            if not t_arr:
                continue

            # ε_total = max strain during the creep phase
            creep_s = [s for t, s in zip(t_arr, s_arr) if t <= t_rel]
            eps_total = max(creep_s) if creep_s else (max(s_arr) if s_arr else 0.0)

            # Default ε₂ = last data point (asymptotic permanent deformation)
            eps2_def = float(s_arr[-1])

            # Default ε₁ = strain 10 % into recovery duration, else midpoint
            t_max     = float(t_arr[-1])
            t_eps1    = t_rel + 0.10 * (t_max - t_rel)
            after_idx = [s for t, s in zip(t_arr, s_arr) if t >= t_eps1]
            eps1_def  = float(after_idx[0]) if after_idx else (eps_total + eps2_def) / 2.0

            # Clamp defaults to physical bounds
            eps2_def = max(0.0, eps2_def)
            eps1_def = max(eps2_def, min(eps1_def, eps_total))

            # Burgers fractions (for the comparison column in the by-hand table)
            bp = res.get("params_burgers", {})
            bf = _burgers_fracs(bp, t_rel) if "G1 (Pa)" in bp else None

            creep_samples.append({
                "sample":       sname,
                "t_release":    t_rel,
                "t_max":        t_max,
                "eps_total":    round(eps_total, 6),
                "eps1_default": round(eps1_def,  6),
                "eps2_default": round(eps2_def,  6),
                "t":            t_arr,
                "strain":       s_arr,
                "burgers_fracs": bf,
            })

        return (
            [multi, table, comp_fig],
            ["Creep/Recovery Fits", "Regression Parameters",
             "Recovery Components (Burgers)"],
            {"creep_samples": creep_samples},
        )

    elif test_type == "amplitude_sweep":
        plateau_pts = int(p.get("plateau_points", 5))
        deviation   = float(p.get("deviation", 0.05))
        lver_results = analyze_lver(dataframes_list, plateau_pts, deviation)
        sweep_fig, lver_tbl = build_amplitude_figures(dataframes_list, units, lver_results)
        return [sweep_fig, lver_tbl], ["Amplitude Sweep", "LVER Results"], {}

    elif test_type == "stress_relaxation":
        en_maxwell = bool(p.get("enable_maxwell", False))
        en_kelvin  = bool(p.get("enable_kelvin", False))
        en_zener   = bool(p.get("enable_zener",  False))
        eps0_ov    = p.get("eps0_override")
        results = analyze_stress_relaxation(
            dataframes_list,
            drop_index=p.get("drop_index", []),
            enable_maxwell=en_maxwell,
            enable_kelvin=en_kelvin,
            enable_zener=en_zener,
            exclude_ranges=p.get("exclude_ranges", []),
            eps0_override=float(eps0_ov) if eps0_ov is not None else None,
        )
        overlay = bool(p.get("overlay", False))
        multi, table = build_relaxation_figures(results, units, en_maxwell, en_kelvin,
                                                enable_zener=en_zener, overlay=overlay)
        return [multi, table], ["Stress Relaxation Fits", "Regression Parameters"], {}

    elif test_type == "frequency_sweep":
        show_tan = bool(p.get("show_tan_delta", True))
        show_eta = bool(p.get("show_eta_star", False))
        show_cc  = bool(p.get("show_cole_cole", False))
        results  = analyze_frequency_sweep(dataframes_list)
        figs     = build_frequency_figures(results, units, show_tan, show_eta, show_cc)
        labels   = ["G\' and G\'\'"]
        if show_tan: labels.append("tan(δ)")
        if show_eta: labels.append("|η*|")
        if show_cc:  labels.append("Cole-Cole")
        return figs, labels, {}

    elif test_type == "temperature_sweep":
        show_tan = bool(p.get("show_tan_delta", True))
        results  = analyze_temperature_sweep(dataframes_list)
        figs     = build_temperature_figures(results, units, show_tan)
        labels   = ["G\' and G\'\'"]
        if show_tan: labels.append("tan(δ)")
        return figs, labels, {}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown test_type: {test_type}")


def _combine_intervals(intervals: list) -> "pd.DataFrame":
    """
    Stack DataFrames (from consecutive intervals) into a single continuous time series.
    Normalizes the starting time of the first segment to 0.0, and ensures
    subsequent segments continue from the end of the previous one.
    """
    dfs = []
    cumulative_time = 0.0
    for iv in intervals:
        df_c = iv.copy()
        if 'Time' in df_c.columns:
            t_raw = pd.to_numeric(df_c['Time'], errors='coerce')
            t_valid = t_raw.dropna()
            if t_valid.empty:
                dfs.append(df_c)
                continue
            
            t_start = float(t_valid.iloc[0])
            t_max   = float(t_valid.max())
            t_dur   = t_max - t_start
            
            # Normalize this segment to start at current cumulative offset
            df_c['Time'] = (t_raw - t_start) + cumulative_time
            cumulative_time += max(0, t_dur)
            
        dfs.append(df_c)
    return pd.concat(dfs, ignore_index=True)


def _build_items(sheets, selected_names, iv_sel, stt_overrides, combine: bool = False):
    """
    Build list of (sample_name, DataFrame, effective_test_type) and merged units dict.
    Applies interval filtering and per-sheet type overrides.

    combine=True: merge all selected intervals for each sheet into one DataFrame
    with continuous time (creep + recovery as a single time series).
    """
    items = []
    units = {}
    for name in selected_names:
        if name not in sheets:
            raise HTTPException(status_code=404, detail=f"Sheet '{name}' not found.")
        df = sheets[name]
        data_df = get_data_df(df)
        eff_tt = stt_overrides.get(name) or detect_test_type(data_df)
        split_on_gaps = eff_tt != "creep_recovery"
        intervals = split_intervals(data_df, split_on_gaps=split_on_gaps)

        # Apply interval selection
        sel = iv_sel.get(name)
        if sel is not None:
            intervals = [iv for i, iv in enumerate(intervals) if i in sel]
        if not intervals:
            intervals = [data_df]

        units.update(get_units(df))

        if combine and len(intervals) > 1:
            combined = _combine_intervals(intervals)
            items.append((name, combined, eff_tt))
        elif len(intervals) > 1:
            for i, iv in enumerate(intervals, 1):
                items.append((f"{name}_seg{i}", iv, eff_tt))
        else:
            items.append((name, intervals[0], eff_tt))

    return items, units


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")


@app.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    """
    Upload an Excel file and return sheet names + detected test type per sheet.
    """
    # Support both .xlsx and .csv
    ext = file.filename.lower()
    if not (ext.endswith(".xlsx") or ext.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx and .csv files are supported.")

    raw = await file.read()
    try:
        sheets = extract_sheet_data(raw, filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {e}")

    if not sheets:
        raise HTTPException(status_code=422,
                            detail="No recognisable rheology data found in this file. "
                                   "The app supports Anton Paar and TA Instruments exports. "
                                   "Check that the file contains numeric data columns such as "
                                   "'Storage Modulus', 'Shear Stress', or 'Creep Compliance'.")

    result = {}
    for name, df in sheets.items():
        data_df = get_data_df(df)
        tt = detect_test_type(data_df)
        split_on_gaps = tt != "creep_recovery"
        ivs = split_intervals(data_df, split_on_gaps=split_on_gaps)
        full_data = pd.concat(ivs, ignore_index=True) if ivs else data_df
        sample = full_data.where(pd.notna(full_data), None).to_dict('records')

        inferred: dict = {}
        if tt == "creep_recovery":
            s0  = infer_sigma0(full_data)
            t_r = infer_t_release(full_data)
            inferred = {
                "sigma0":    s0,
                "t_release": t_r,
            }
        elif tt == "stress_relaxation":
            eps0_val = infer_eps0(full_data)
            inferred = {"eps0": eps0_val}

        result[name] = {
            "columns":     list(df.columns),
            "n_rows":      len(full_data),
            "n_intervals": len(ivs),
            "intervals":   get_interval_info(data_df, split_on_gaps=split_on_gaps),
            "test_type":   tt,
            "units":       get_units(df),
            "sample_data": sample,
            "inferred":    inferred,
        }

    return _jsonify({"sheets": result, "file_size_kb": round(len(raw)/1024, 1)})


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    sheet_names: str = Form(...),
    test_type: str = Form(...),
    params: str = Form(default="{}"),
    interval_selections: str = Form(default="{}"),   # {sheetName: [0,1,2]}
    sheet_test_types: str = Form(default="{}"),       # {sheetName: "frequency_sweep"}
):
    """
    Analyze one or more sheets. Supports interval selection, per-sheet type overrides,
    and test_type='auto' (detects type per sheet and analyses each group).
    """
    raw = await file.read()
    try:
        sheets = extract_sheet_data(raw, filename=file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Parse error: {e}")

    selected_names = json.loads(sheet_names)
    p          = json.loads(params)
    iv_sel     = json.loads(interval_selections)
    stt_over   = json.loads(sheet_test_types)

    combine = bool(p.get("combine_segments", False))
    items, units = _build_items(sheets, selected_names, iv_sel, stt_over, combine=combine)
    if not items:
        raise HTTPException(status_code=422, detail="No valid data found in selected sheets.")

    try:
        if test_type == "auto":
            groups: dict[str, list] = defaultdict(list)
            for name, df, tt in items:
                groups[tt].append((name, df))

            all_figures, all_labels = [], []
            for tt, group_list in groups.items():
                if tt == "unknown":
                    continue
                figs, labels, _ = _dispatch(tt, group_list, {}, units)
                prefix = tt.replace("_", " ").title()
                all_figures.extend(figs)
                all_labels.extend([f"{prefix} — {l}" for l in labels])

            if not all_figures:
                raise HTTPException(status_code=422,
                                    detail="No recognisable test types found in selected sheets.")
            return _jsonify({"test_type": "auto", "figures": all_figures,
                             "figure_labels": all_labels})

        else:
            dataframes_list = [(n, df) for n, df, _ in items]
            figs, labels, extra = _dispatch(test_type, dataframes_list, p, units)
            raw_series = None
            if test_type in ('creep_recovery', 'stress_relaxation'):
                raw_series = _extract_raw_series(test_type, dataframes_list, units)
            return _jsonify({"test_type": test_type, "figures": figs,
                             "figure_labels": labels, "raw_series": raw_series,
                             **extra})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")


@app.post("/api/download")
async def download_results(
    file: UploadFile = File(...),
    sheet_names: str = Form(...),
    test_type: str = Form(...),
    params: str = Form(default="{}"),
    download_format: str = Form(default="excel"),
    interval_selections: str = Form(default="{}"),
    sheet_test_types: str = Form(default="{}"),
    by_hand_thresholds: str = Form(default="{}"),
):
    """
    Run analysis and return results as a downloadable Excel or CSV archive.
    """
    raw = await file.read()
    try:
        sheets = extract_sheet_data(raw)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    selected_names = json.loads(sheet_names)
    p        = json.loads(params)
    iv_sel   = json.loads(interval_selections)
    stt_over = json.loads(sheet_test_types)

    items, units = _build_items(sheets, selected_names, iv_sel, stt_over,
                                combine=bool(p.get("combine_segments", False)))

    # Resolve effective test type for download (use first detected if "auto")
    if test_type == "auto":
        eff_tt = items[0][2] if items else "unknown"
    else:
        eff_tt = test_type

    dataframes_list = [(n, df) for n, df, _ in items]
    bh = json.loads(by_hand_thresholds)

    result_dfs: dict[str, pd.DataFrame] = {}

    if eff_tt == "creep_recovery":
        t_release_raw = p.get("t_release", "auto")
        t_release = None if t_release_raw == "auto" else float(t_release_raw)
        results = analyze_creep_recovery(
            dataframes_list, t_release,
            drop_index=p.get("drop_index", []),
            enable_maxwell=bool(p.get("enable_maxwell", False)),
            enable_kelvin=bool(p.get("enable_kelvin", False)),
            enable_zener=bool(p.get("enable_zener", False)),
            prune_start_n=int(p.get("prune_start_n", 0)),
            prune_release_n=int(p.get("prune_release_n", 0)),
        )

        # ── Sheet 1: Fitted Parameters ──────────────────────────────────────
        rows = []
        for res in results:
            row: dict = {
                "Sample":        res["Sample"],
                "σ₀ (Pa)":       round(float(res.get("sigma0") or 0), 4),
                "t_release (s)": round(float(res.get("t_release") or 0), 3),
            }
            bp = res.get("params_burgers", {})
            if bp and "Error" not in bp:
                row["G1 (Pa)"]      = round(float(bp.get("G1 (Pa)",   float("nan"))), 4)
                row["η1 (Pa·s)"]    = round(float(bp.get("η1 (Pa·s)", float("nan"))), 4)
                row["G2 (Pa)"]      = round(float(bp.get("G2 (Pa)",   float("nan"))), 4)
                row["η2 (Pa·s)"]    = round(float(bp.get("η2 (Pa·s)", float("nan"))), 4)
                row["R² (Burgers)"] = round(float(bp.get("R2 Score",  float("nan"))), 4)
            mp = res.get("params_maxwell", {})
            if mp and "Error" not in mp:
                row["G_Maxwell (Pa)"]   = round(float(mp.get("G (Pa)",   float("nan"))), 4)
                row["η_Maxwell (Pa·s)"] = round(float(mp.get("η (Pa·s)", float("nan"))), 4)
                row["R² (Maxwell)"]     = round(float(mp.get("R2 Score", float("nan"))), 4)
            kp = res.get("params_kelvin", {})
            if kp and "Error" not in kp:
                row["G_KV (Pa)"]   = round(float(kp.get("G (Pa)",   float("nan"))), 4)
                row["η_KV (Pa·s)"] = round(float(kp.get("η (Pa·s)", float("nan"))), 4)
                row["R² (KV)"]     = round(float(kp.get("R2 Score", float("nan"))), 4)
            zp = res.get("params_zener", {})
            if zp and "Error" not in zp:
                row["G_perm_Zener (Pa)"]    = round(float(zp.get("G_perm (Pa)",    float("nan"))), 4)
                row["G_trans_Zener (Pa)"]   = round(float(zp.get("G_trans (Pa)",   float("nan"))), 4)
                row["η_trans_Zener (Pa·s)"] = round(float(zp.get("η_trans (Pa·s)", float("nan"))), 4)
                row["τ_ret_Zener (s)"]      = round(float(zp.get("τ_ret (s)",      float("nan"))), 4)
                row["R² (Zener)"]           = round(float(zp.get("R2 Score",       float("nan"))), 4)
            rows.append(row)
        result_dfs["Fitted_Parameters"] = pd.DataFrame(rows)

        # ── Sheet 2: Recovery Components (Burgers) ───────────────────────────
        components = evaluate_recovery_components(results, t_release)
        if components:
            num_cols = ["Elastic (%)", "Viscoelastic (%)", "Plastic (%)"]
            df_comp = (pd.DataFrame(components)
                         [["Sample", "frac_elastic", "frac_visco", "frac_plastic"]]
                         .copy()
                         .rename(columns={"frac_elastic": "Elastic (%)",
                                          "frac_visco":   "Viscoelastic (%)",
                                          "frac_plastic": "Plastic (%)"}))
            means_c = df_comp[num_cols].mean().round(2)
            stds_c  = df_comp[num_cols].std(ddof=0).fillna(0).round(2)
            df_comp = pd.concat([df_comp,
                                  pd.DataFrame([{"Sample": "Mean",    **means_c}]),
                                  pd.DataFrame([{"Sample": "Std Dev", **stds_c}])],
                                 ignore_index=True)
            result_dfs["Recovery_Components_Burgers"] = df_comp

        # ── Sheet 3: Recovery Components (by hand) ───────────────────────────
        if bh:
            bh_rows = []
            for sample_name, _ in dataframes_list:
                sname = str(sample_name)
                th = bh.get(sname)
                if not th:
                    continue
                eps1      = float(th.get("eps1",      0))
                eps2      = float(th.get("eps2",      0))
                eps_total = float(th.get("eps_total", 0))
                if eps_total <= 0:
                    continue
                eps2 = max(0.0, min(eps2, eps_total))
                eps1 = max(eps2,  min(eps1, eps_total))
                bh_rows.append({
                    "Sample":           sname,
                    "ε₁":               round(eps1,      6),
                    "ε₂":               round(eps2,      6),
                    "ε_total":          round(eps_total, 6),
                    "Elastic (%)":      round(100 * (eps_total - eps1) / eps_total, 2),
                    "Viscoelastic (%)": round(100 * (eps1 - eps2)      / eps_total, 2),
                    "Plastic (%)":      round(100 *  eps2               / eps_total, 2),
                })
            if bh_rows:
                num_cols = ["Elastic (%)", "Viscoelastic (%)", "Plastic (%)"]
                df_bh    = pd.DataFrame(bh_rows)
                means_bh = df_bh[num_cols].mean().round(2)
                stds_bh  = df_bh[num_cols].std(ddof=0).fillna(0).round(2)
                df_bh = pd.concat([df_bh,
                                    pd.DataFrame([{"Sample": "Mean",    **means_bh}]),
                                    pd.DataFrame([{"Sample": "Std Dev", **stds_bh}])],
                                   ignore_index=True)
                result_dfs["Recovery_Components_ByHand"] = df_bh

        # ── Sheet 4: Fitted Time Series Data (Blocked) ─────────────────────
        result_dfs["Fitted_Data_Points"] = _build_blocked_export_df(results, "creep_recovery")

    elif eff_tt == "amplitude_sweep":
        lver = analyze_lver(dataframes_list,
                             int(p.get("plateau_points", 5)),
                             float(p.get("deviation", 0.05)))
        result_dfs["LVER"] = pd.DataFrame(lver)

    elif eff_tt == "stress_relaxation":
        eps0_ov = p.get("eps0_override")
        results = analyze_stress_relaxation(
            dataframes_list,
            drop_index=p.get("drop_index", []),
            enable_maxwell=bool(p.get("enable_maxwell", False)),
            enable_kelvin=bool(p.get("enable_kelvin", False)),
            enable_zener=bool(p.get("enable_zener", False)),
            exclude_ranges=p.get("exclude_ranges", []),
            eps0_override=float(eps0_ov) if eps0_ov is not None else None,
        )
        rows = []
        for res in results:
            row = {"Sample": res["Sample"]}
            for model in ["burgers", "maxwell", "kelvin", "zener"]:
                pk = f"params_{model}"
                if pk in res and "Error" not in res[pk]:
                    for k, v in res[pk].items():
                        row[f"{model}_{k}"] = v
            rows.append(row)
        result_dfs["Stress_Relaxation"] = pd.DataFrame(rows)

        # ── Sheet 2: Fitted Time Series Data (Blocked) ─────────────────────
        result_dfs["Fitted_Data_Points"] = _build_blocked_export_df(results, "stress_relaxation")

    elif eff_tt == "frequency_sweep":
        results = analyze_frequency_sweep(dataframes_list)
        rows = [{"Sample": r["Sample"], **r.get("params_powerlaw", {}),
                 "gel_point_omega": r.get("gel_point", {}).get("omega"),
                 "gel_point_G": r.get("gel_point", {}).get("G")} for r in results]
        result_dfs["Frequency_Sweep"] = pd.DataFrame(rows)

    elif eff_tt == "temperature_sweep":
        results = analyze_temperature_sweep(dataframes_list)
        rows = [{"Sample": r["Sample"],
                 "gel_point_T": r.get("gel_point", {}).get("T"),
                 "gel_point_G": r.get("gel_point", {}).get("G")} for r in results]
        result_dfs["Temperature_Sweep"] = pd.DataFrame(rows)

    if not result_dfs:
        raise HTTPException(status_code=422, detail="No results to download.")

    if download_format == "csv":
        if len(result_dfs) == 1:
            buf = io.StringIO()
            next(iter(result_dfs.values())).to_csv(buf, index=False)
            buf.seek(0)
            return StreamingResponse(
                iter([buf.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={eff_tt}_results.csv"},
            )
        else:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, df in result_dfs.items():
                    csv_io = io.StringIO()
                    header = False if name == "Fitted_Data_Points" else True
                    df.to_csv(csv_io, index=False, header=header)
                    zf.writestr(f"{name}.csv", csv_io.getvalue())
            zip_buf.seek(0)
            return StreamingResponse(
                iter([zip_buf.read()]),
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={eff_tt}_results.zip"},
            )
    else:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet, df in result_dfs.items():
                header = False if sheet == "Fitted_Data_Points" else True
                df.to_excel(writer, sheet_name=sheet, index=False, header=header)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.read()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={eff_tt}_results.xlsx"},
        )


@app.post("/api/rawplot")
async def raw_plot(
    file: UploadFile = File(...),
    sheet_names: str = Form(...),
    interval_selections: str = Form(default="{}"),
    x_col: str = Form(...),
    y_cols: str = Form(...),           # JSON array of column names
    mode: str = Form(default="lines+markers"),
):
    """
    Build a Plotly figure from raw (unanalysed) data with user-selected X/Y columns.
    """
    import plotly.graph_objects as go

    raw = await file.read()
    try:
        sheets = extract_sheet_data(raw)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    selected_names = json.loads(sheet_names)
    y_cols_list    = json.loads(y_cols)
    iv_sel         = json.loads(interval_selections)

    if not y_cols_list:
        raise HTTPException(status_code=400, detail="Select at least one Y column.")

    COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
              '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf']

    fig       = go.Figure()
    color_idx = 0
    all_units: dict[str, str] = {}

    for name in selected_names:
        if name not in sheets:
            continue
        df      = sheets[name]
        data_df = get_data_df(df)
        tt = detect_test_type(data_df)
        intervals = split_intervals(data_df, split_on_gaps=(tt != "creep_recovery"))
        all_units.update(get_units(df))

        sel = iv_sel.get(name)
        if sel is not None:
            intervals = [iv for i, iv in enumerate(intervals) if i in sel]
        if not intervals:
            intervals = [data_df]

        for seg_i, seg in enumerate(intervals):
            if x_col not in seg.columns:
                continue
            x = pd.to_numeric(seg[x_col], errors='coerce')
            short_name = _short_sample_name(name)
            seg_label = short_name if len(intervals) == 1 else f"{short_name} seg{seg_i + 1}"

            for y_col in y_cols_list:
                if y_col not in seg.columns:
                    continue
                y = pd.to_numeric(seg[y_col], errors='coerce')
                color = COLORS[color_idx % len(COLORS)]
                trace_name = f"{seg_label} | {y_col}" if len(y_cols_list) > 1 else seg_label
                fig.add_trace(go.Scatter(
                    x=x.tolist(), y=y.tolist(),
                    mode=mode, name=trace_name,
                    line=dict(color=color),
                    marker=dict(color=color, size=5),
                ))
                color_idx += 1

    x_unit = all_units.get(x_col, '')
    y_units = sorted({all_units.get(c, '') for c in y_cols_list} - {''})

    fig.update_layout(
        xaxis_title=f"{x_col} ({x_unit})" if x_unit else x_col,
        yaxis_title=(f"{', '.join(y_cols_list)} ({', '.join(y_units)})"
                     if y_units else ', '.join(y_cols_list)),
        legend_title_text="Sample",
    )

    label = f"{', '.join(y_cols_list)} vs {x_col}"
    return _jsonify({"figure": fig.to_dict(), "figure_label": label})
