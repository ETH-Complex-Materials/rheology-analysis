"""
FastAPI backend for the Rheology Analysis Web App.
"""
import io
import json
import math
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
from analysis.relaxation import analyze_stress_relaxation, build_relaxation_figures
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
            'name':    name,
            't':       t_vals,
            'y':       y_vals,
            'y_label': f"{y_col_name} ({y_unit})" if y_unit else y_col_name,
        })
    return series


def _dispatch(test_type: str, dataframes_list: list, p: dict, units: dict) -> tuple[list, list]:
    """
    Run analysis for a given test_type and return (figures, labels).
    p contains analysis parameters (may be empty — defaults are applied per type).
    """
    if test_type == "creep_recovery":
        t_release_raw = p.get("t_release", "auto")
        t_release  = None if t_release_raw == "auto" else float(t_release_raw)
        en_maxwell = bool(p.get("enable_maxwell", False))
        en_kelvin  = bool(p.get("enable_kelvin", False))
        prune_win  = float(p.get("prune_window", 0.0))

        results = analyze_creep_recovery(
            dataframes_list, t_release,
            drop_index=p.get("drop_index", []),
            enable_maxwell=en_maxwell,
            enable_kelvin=en_kelvin,
            prune_window=prune_win,
            exclude_ranges=p.get("exclude_ranges", []),
            prune_start_n=int(p.get("prune_start_n", 0)),
            prune_release_n=int(p.get("prune_release_n", 0)),
        )
        overlay = bool(p.get("overlay", False))
        multi, table = build_creep_figures(results, units, en_maxwell, en_kelvin, overlay=overlay)
        components = evaluate_recovery_components(results)
        comp_bar, comp_table = build_recovery_component_figures(components)
        return (
            [multi, table, comp_bar, comp_table],
            ["Creep/Recovery Fits", "Regression Parameters",
             "Recovery Components", "Component Table"],
        )

    elif test_type == "amplitude_sweep":
        plateau_pts = int(p.get("plateau_points", 5))
        deviation   = float(p.get("deviation", 0.05))
        lver_results = analyze_lver(dataframes_list, plateau_pts, deviation)
        sweep_fig, lver_tbl = build_amplitude_figures(dataframes_list, units, lver_results)
        return [sweep_fig, lver_tbl], ["Amplitude Sweep", "LVER Results"]

    elif test_type == "stress_relaxation":
        en_maxwell = bool(p.get("enable_maxwell", False))
        en_kelvin  = bool(p.get("enable_kelvin", False))
        results = analyze_stress_relaxation(
            dataframes_list,
            drop_index=p.get("drop_index", []),
            enable_maxwell=en_maxwell,
            enable_kelvin=en_kelvin,
            exclude_ranges=p.get("exclude_ranges", []),
        )
        overlay = bool(p.get("overlay", False))
        multi, table = build_relaxation_figures(results, units, en_maxwell, en_kelvin, overlay=overlay)
        return [multi, table], ["Stress Relaxation Fits", "Regression Parameters"]

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
        return figs, labels

    elif test_type == "temperature_sweep":
        show_tan = bool(p.get("show_tan_delta", True))
        results  = analyze_temperature_sweep(dataframes_list)
        figs     = build_temperature_figures(results, units, show_tan)
        labels   = ["G\' and G\'\'"]
        if show_tan: labels.append("tan(δ)")
        return figs, labels

    else:
        raise HTTPException(status_code=400, detail=f"Unknown test_type: {test_type}")


def _combine_intervals(intervals: list) -> "pd.DataFrame":
    """
    Stack DataFrames (from consecutive intervals) with continuous time.
    - If a segment's time starts near zero (reset split), offset it by the
      cumulative time so far.
    - If a segment's time is already large (gap split — times are absolute),
      keep the times as-is; just advance the offset tracker.
    """
    dfs = []
    time_offset = 0.0
    for iv in intervals:
        df_c = iv.copy()
        if 'Time' in df_c.columns:
            t = pd.to_numeric(df_c['Time'], errors='coerce')
            t_valid = t.dropna()
            if t_valid.empty:
                dfs.append(df_c)
                continue
            t_first = float(t_valid.iloc[0])
            if t_first > time_offset + 1.0:
                # Gap split: times are already absolute, no offset needed
                time_offset = float(t_valid.max())
            else:
                # Reset split: add cumulative offset
                df_c['Time'] = t + time_offset
                time_offset += float(t_valid.max())
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
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported.")

    raw = await file.read()
    try:
        sheets = extract_sheet_data(raw)
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
        sheets = extract_sheet_data(raw)
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
                figs, labels = _dispatch(tt, group_list, {}, units)
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
            figs, labels = _dispatch(test_type, dataframes_list, p, units)
            raw_series = None
            if test_type in ('creep_recovery', 'stress_relaxation'):
                raw_series = _extract_raw_series(test_type, dataframes_list, units)
            return _jsonify({"test_type": test_type, "figures": figs,
                             "figure_labels": labels, "raw_series": raw_series})

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
):
    """
    Run analysis and return results as a downloadable Excel or CSV file.
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

    result_dfs: dict[str, pd.DataFrame] = {}

    if eff_tt == "creep_recovery":
        t_release_raw = p.get("t_release", "auto")
        t_release = None if t_release_raw == "auto" else float(t_release_raw)
        results = analyze_creep_recovery(
            dataframes_list, t_release,
            drop_index=p.get("drop_index", []),
            enable_maxwell=bool(p.get("enable_maxwell", False)),
            enable_kelvin=bool(p.get("enable_kelvin", False)),
            prune_start_n=int(p.get("prune_start_n", 0)),
            prune_release_n=int(p.get("prune_release_n", 0)),
        )
        rows = []
        for res in results:
            row = {"Sample": res["Sample"]}
            for model in ["burgers", "maxwell", "kelvin"]:
                pk = f"params_{model}"
                if pk in res and "Error" not in res[pk]:
                    for k, v in res[pk].items():
                        row[f"{model}_{k}"] = v
            rows.append(row)
        result_dfs["Creep_Recovery"] = pd.DataFrame(rows)
        components = evaluate_recovery_components(results, t_release)
        if components:
            result_dfs["Recovery_Components"] = pd.DataFrame(components)

    elif eff_tt == "amplitude_sweep":
        lver = analyze_lver(dataframes_list,
                             int(p.get("plateau_points", 5)),
                             float(p.get("deviation", 0.05)))
        result_dfs["LVER"] = pd.DataFrame(lver)

    elif eff_tt == "stress_relaxation":
        results = analyze_stress_relaxation(
            dataframes_list,
            drop_index=p.get("drop_index", []),
            enable_maxwell=bool(p.get("enable_maxwell", False)),
            enable_kelvin=bool(p.get("enable_kelvin", False)),
        )
        rows = []
        for res in results:
            row = {"Sample": res["Sample"]}
            for model in ["burgers", "maxwell", "kelvin"]:
                pk = f"params_{model}"
                if pk in res and "Error" not in res[pk]:
                    for k, v in res[pk].items():
                        row[f"{model}_{k}"] = v
            rows.append(row)
        result_dfs["Stress_Relaxation"] = pd.DataFrame(rows)

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
        first_df = next(iter(result_dfs.values()))
        buf = io.StringIO()
        first_df.to_csv(buf, index=False)
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={eff_tt}_results.csv"},
        )
    else:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet, df in result_dfs.items():
                df.to_excel(writer, sheet_name=sheet, index=False)
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
            seg_label = name if len(intervals) == 1 else f"{name} seg{seg_i + 1}"

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
