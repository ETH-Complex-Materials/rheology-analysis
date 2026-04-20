"""
Stress Relaxation analysis — Burgers, Maxwell, Kelvin-Voigt fitting.
Ported from interface.py (Gabriel David, 2025).
"""
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.optimize import curve_fit


# ---------------------------------------------------------------------------
# Physical models
# ---------------------------------------------------------------------------

def _r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    return 1.0 if ss_tot == 0 else 1 - ss_res / ss_tot


def infer_eps0(df: pd.DataFrame) -> float | None:
    """
    Infer the imposed strain ε₀ from the Shear Strain column.

    The column is expected to be in percent (instrument convention) → value ÷ 100.
    Returns the modal (most frequent) value as an absolute dimensionless strain,
    or None if the column is absent / empty.
    """
    if "Shear Strain" not in df.columns:
        return None
    col = pd.to_numeric(df["Shear Strain"], errors="coerce").dropna()
    if len(col) == 0:
        return None
    mode_val = float(col.round(4).mode().iloc[0])
    return mode_val / 100.0  # percent → absolute


def _parse_eps0_from_name(sample_name: str) -> float:
    """Fallback: parse eps0 from the last '_'-separated token of the sample name."""
    try:
        chunk = sample_name.split("_")[-1] if "_" in sample_name else sample_name
        return float(re.sub(r'[^0-9.]', '', chunk)) * 100
    except (ValueError, IndexError):
        return 1.0


def _burgers_relax(t, G1, eta1, G2, eta2, eps0):
    p1 = eta1/G1 + eta1/G2 + eta2/G2
    p2 = eta1*eta2/(G1*G2)
    disc = p1**2 - 4*p2
    if disc < 0:
        disc = 0.0
    A  = np.sqrt(disc)
    q1 = eta1
    q2 = eta1*eta2/G2
    denom = A if A > 1e-15 else 1e-15
    r1 = (p1 - A)/(2*p2) if p2 > 1e-12 else 0
    r2 = (p1 + A)/(2*p2) if p2 > 1e-12 else 0
    return eps0 * ((q1 - q2*r1)/denom * np.exp(-r1*t) - (q1 - q2*r2)/denom * np.exp(-r2*t))


def _maxwell_relax(t, G, eta, eps0):
    G = max(G, 1e-9); eta = max(eta, 1e-9)
    return eps0 * G * np.exp(-t / (eta/G))


def _kv_relax(t, G, eps0):
    return np.full_like(t, eps0 * max(G, 1e-9), dtype=float)


def _zener_relax(t, G_perm, G_trans, eta_trans, eps0):
    """
    Zener / Standard Linear Solid stress relaxation.
    Parallel spring G_perm in series with Maxwell branch (G_trans + eta_trans).
    σ(t) = ε₀ · [G_perm + G_trans · exp(−t / τ)]  where τ = eta_trans / G_trans.
    """
    G_perm    = max(G_perm,    1e-9)
    G_trans   = max(G_trans,   1e-9)
    eta_trans = max(eta_trans, 1e-9)
    tau = eta_trans / G_trans
    return eps0 * (G_perm + G_trans * np.exp(-t / tau))


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def analyze_stress_relaxation(
    dataframes_list: list[tuple[str, pd.DataFrame]],
    drop_index=None,
    enable_maxwell: bool = False,
    enable_kelvin: bool = False,
    enable_zener: bool = False,
    exclude_ranges: list | None = None,
    eps0_override: float | None = None,
) -> list[dict]:
    """
    Fit viscoelastic models to stress-relaxation data.

    Parameters
    ----------
    dataframes_list : list of (sample_name, DataFrame)
        Each DataFrame must have columns 'Time' and 'Shear Stress'.
    drop_index : array-like, optional
        DataFrame index values to remove before fitting.

    Returns
    -------
    list of result dicts (one per sample).
    """
    results = []

    for sample_name, df in dataframes_list:
        if 'Time' not in df.columns or 'Shear Stress' not in df.columns:
            continue

        # Determine ε₀: user override → Shear Strain column (mode ÷ 100) → name parsing
        if eps0_override is not None:
            eps0 = float(eps0_override)
        else:
            inferred = infer_eps0(df)
            eps0 = inferred if (inferred is not None and inferred > 0) \
                   else _parse_eps0_from_name(sample_name)

        df_p = df.copy()
        if drop_index is not None and len(drop_index):
            df_p = df_p.drop(drop_index, errors='ignore')

        t = pd.to_numeric(df_p["Time"], errors='coerce').to_numpy()
        s = pd.to_numeric(df_p["Shear Stress"], errors='coerce').to_numpy()
        mask = np.isfinite(t) & np.isfinite(s)
        t, s = t[mask], s[mask]

        # Apply user-defined exclusion ranges (e.g. initial non-equilibrium loading ramp)
        if exclude_ranges:
            keep = np.ones(len(t), dtype=bool)
            for t_lo, t_hi in exclude_ranges:
                keep &= ~((t >= float(t_lo)) & (t <= float(t_hi)))
            t, s = t[keep], s[keep]

        if len(t) == 0:
            continue

        dt = np.diff(np.concatenate(([t[0]], t)))
        dt_mean = dt.mean()
        if dt_mean > 0 and np.isfinite(dt_mean):
            w = dt / dt_mean
            sigma_raw = 1 / np.sqrt(np.abs(w) + 1e-16)
            sigma_w = sigma_raw if np.all(np.isfinite(sigma_raw)) else None
        else:
            sigma_w = None

        res = {"Sample": sample_name, "experimental_data": {"t": t.tolist(), "stress": s.tolist()}}

        # Burgers (always)
        def _b(t, G1, eta1, G2, eta2):
            return _burgers_relax(t, G1, eta1, G2, eta2, eps0)
        try:
            p, _ = curve_fit(_b, t, s, p0=[10000, 1e8, 10000, 1e6],
                             sigma=sigma_w, bounds=(0,np.inf), maxfev=10000)
            fit = _b(t, *p)
            G1f, eta1f, G2f, eta2f = p
            p1 = eta1f/G1f + eta1f/G2f + eta2f/G2f
            p2 = eta1f*eta2f/(G1f*G2f)
            A  = np.sqrt(max(p1**2 - 4*p2, 0))
            r1 = (p1-A)/(2*p2) if p2>1e-12 else 0
            r2 = (p1+A)/(2*p2) if p2>1e-12 else 0
            res["params_burgers"] = {
                "G1 (Pa)": G1f, "η1 (Pa·s)": eta1f,
                "G2 (Pa)": G2f, "η2 (Pa·s)": eta2f,
                "tau1 (s)": 1/r1 if r1>1e-12 else float('inf'),
                "tau2 (s)": 1/r2 if r2>1e-12 else float('inf'),
                "R2 Score": _r2(s, fit)
            }
            res["fitted_data_burgers"] = {"stress": fit.tolist()}
        except (RuntimeError, ValueError):
            res["params_burgers"] = {"Error": "Fit failed"}
            res["fitted_data_burgers"] = {"stress": None}

        # Maxwell (optional)
        if enable_maxwell:
            def _m(t, G, eta):
                return _maxwell_relax(t, G, eta, eps0)
            try:
                p, _ = curve_fit(_m, t, s, p0=[10000, 1e8], sigma=sigma_w,
                                 bounds=(0,np.inf), maxfev=5000)
                fit = _m(t, *p)
                res["params_maxwell"] = {
                    "G (Pa)": p[0], "η (Pa·s)": p[1],
                    "tau (s)": p[1]/p[0] if p[0]>1e-9 else float('inf'),
                    "R2 Score": _r2(s, fit)
                }
                res["fitted_data_maxwell"] = {"stress": fit.tolist()}
            except RuntimeError:
                res["params_maxwell"] = {"Error": "Fit failed"}
                res["fitted_data_maxwell"] = {"stress": None}

        # Kelvin-Voigt (optional — constant stress for KV under strain control)
        if enable_kelvin:
            def _k(t, G):
                return _kv_relax(t, G, eps0)
            try:
                p, _ = curve_fit(_k, t, s, p0=[10000], sigma=sigma_w,
                                 bounds=(0,np.inf), maxfev=5000)
                fit = _k(t, p[0])
                res["params_kelvin"] = {"G (Pa)": p[0], "R2 Score": _r2(s, fit)}
                res["fitted_data_kelvin"] = {"stress": fit.tolist()}
            except RuntimeError:
                res["params_kelvin"] = {"Error": "Fit failed"}
                res["fitted_data_kelvin"] = {"stress": None}

        # Zener / SLS (optional)
        if enable_zener:
            def _z(t, G_perm, G_trans, eta_trans):
                return _zener_relax(t, G_perm, G_trans, eta_trans, eps0)
            try:
                p, _ = curve_fit(_z, t, s, p0=[10000, 10000, 1e6],
                                 sigma=sigma_w, bounds=(0, np.inf), maxfev=10000)
                fit = _z(t, *p)
                G_perm_f, G_t_f, eta_t_f = p
                tauZ = eta_t_f / G_t_f
                res["params_zener"] = {
                    "G_perm (Pa)":    G_perm_f,
                    "G_trans (Pa)":   G_t_f,
                    "η_trans (Pa·s)": eta_t_f,
                    "tauZ (s)":       tauZ,
                    "R2 Score":       _r2(s, fit),
                }
                res["fitted_data_zener"] = {"stress": fit.tolist()}
            except (RuntimeError, ValueError):
                res["params_zener"] = {"Error": "Fit failed"}
                res["fitted_data_zener"] = {"stress": None}

        results.append(res)
    return results


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

_OVERLAY_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]


def build_relaxation_figures(
    analysis_results: list[dict],
    units: dict,
    enable_maxwell: bool = False,
    enable_kelvin: bool = False,
    enable_zener: bool = False,
    overlay: bool = False,
) -> tuple[dict, dict]:
    """
    Build Plotly figures for stress relaxation.

    Returns
    -------
    (multi_plot_json, table_json)
    """
    time_unit   = units.get("Time", "s")
    stress_unit = units.get("Shear Stress", "Pa")

    multi = go.Figure()
    all_traces = []
    buttons    = []
    traces_per = 0

    for i, res in enumerate(analysis_results):
        t  = res["experimental_data"]["t"]
        s  = res["experimental_data"]["stress"]
        vis   = True if overlay else (i == 0)
        color = _OVERLAY_COLORS[i % len(_OVERLAY_COLORS)] if overlay else '#1f77b4'
        cur = []

        exp_name = res["Sample"] if overlay else 'Experimental'
        cur.append(go.Scatter(x=t, y=s, mode='markers', name=exp_name,
                              legendgroup=res["Sample"], visible=vis,
                              marker=dict(color=color, symbol='circle-open')))

        if res.get("fitted_data_burgers", {}).get("stress") is not None:
            fit_name  = f"{res['Sample']} fit" if overlay else 'Burgers'
            fit_color = color if overlay else '#ff7f0e'
            cur.append(go.Scatter(x=t, y=res["fitted_data_burgers"]["stress"],
                                  mode='lines', name=fit_name, legendgroup=res["Sample"],
                                  visible=vis, line=dict(color=fit_color, width=2)))

        if enable_maxwell and res.get("fitted_data_maxwell", {}).get("stress") is not None:
            cur.append(go.Scatter(x=t, y=res["fitted_data_maxwell"]["stress"],
                                  mode='lines', name='Maxwell', legendgroup=res["Sample"],
                                  visible=vis, line=dict(color=color if overlay else '#2ca02c',
                                                         dash='dash')))

        if enable_kelvin and res.get("fitted_data_kelvin", {}).get("stress") is not None:
            cur.append(go.Scatter(x=t, y=res["fitted_data_kelvin"]["stress"],
                                  mode='lines', name='Kelvin-Voigt', legendgroup=res["Sample"],
                                  visible=vis, line=dict(color=color if overlay else '#d62728',
                                                         dash='dot')))

        if enable_zener and res.get("fitted_data_zener", {}).get("stress") is not None:
            cur.append(go.Scatter(x=t, y=res["fitted_data_zener"]["stress"],
                                  mode='lines', name='Zener', legendgroup=res["Sample"],
                                  visible=vis, line=dict(color=color if overlay else '#9467bd',
                                                         dash='dashdot')))

        all_traces.extend(cur)
        if i == 0:
            traces_per = len(cur)

    for trace in all_traces:
        multi.add_trace(trace)

    if not overlay:
        for i, res in enumerate(analysis_results):
            vis = [False]*len(all_traces)
            for j in range(i*traces_per, i*traces_per + traces_per):
                vis[j] = True
            r2_parts = []
            if res.get("params_burgers", {}).get("R2 Score") is not None:
                r2_parts.append(f"Burgers R²={res['params_burgers']['R2 Score']:.3f}")
            if enable_maxwell and res.get("params_maxwell", {}).get("R2 Score") is not None:
                r2_parts.append(f"Maxwell R²={res['params_maxwell']['R2 Score']:.3f}")
            if enable_kelvin and res.get("params_kelvin", {}).get("R2 Score") is not None:
                r2_parts.append(f"KV R²={res['params_kelvin']['R2 Score']:.3f}")
            if enable_zener and res.get("params_zener", {}).get("R2 Score") is not None:
                r2_parts.append(f"Zener R²={res['params_zener']['R2 Score']:.3f}")
            r2_str = (" | " + " | ".join(r2_parts)) if r2_parts else ""
            buttons.append(dict(label=res["Sample"], method="update",
                                args=[{"visible": vis},
                                      {"title": f"<b>{res['Sample']}</b>{r2_str}"}]))

    title0 = ""
    if analysis_results:
        if overlay:
            title0 = "<b>All Samples — Overlay</b>"
        else:
            res0 = analysis_results[0]
            r2_parts0 = []
            if res0.get("params_burgers", {}).get("R2 Score") is not None:
                r2_parts0.append(f"Burgers R²={res0['params_burgers']['R2 Score']:.3f}")
            if enable_maxwell and res0.get("params_maxwell", {}).get("R2 Score") is not None:
                r2_parts0.append(f"Maxwell R²={res0['params_maxwell']['R2 Score']:.3f}")
            if enable_kelvin and res0.get("params_kelvin", {}).get("R2 Score") is not None:
                r2_parts0.append(f"KV R²={res0['params_kelvin']['R2 Score']:.3f}")
            if enable_zener and res0.get("params_zener", {}).get("R2 Score") is not None:
                r2_parts0.append(f"Zener R²={res0['params_zener']['R2 Score']:.3f}")
            title0 = f"<b>{res0['Sample']}</b>" + \
                     ((" | " + " | ".join(r2_parts0)) if r2_parts0 else "")

    if buttons:
        multi.update_layout(
            updatemenus=[dict(active=0, buttons=buttons, direction="down",
                              pad={"r":10,"t":10}, showactive=True,
                              x=0.1, xanchor="left", y=1.15, yanchor="top")])
    multi.update_layout(
        title=title0, title_x=0.5,
        xaxis_title=f"Time ({time_unit})",
        yaxis_title=f"Shear Stress ({stress_unit})",
        legend_title_text="Legend"
    )

    # Parameters table
    params_rows = []
    for res in analysis_results:
        for model_key in ["burgers", "maxwell", "kelvin", "zener"]:
            pk = f"params_{model_key}"
            if pk in res and "Error" not in res[pk]:
                row = {"Sample": res["Sample"], "Model": model_key.capitalize()}
                row.update(res[pk])
                params_rows.append(row)

    df = pd.DataFrame(params_rows) if params_rows else pd.DataFrame()

    if not df.empty:
        # Maxwell / KV single-element aliases → canonical columns
        if "G (Pa)" in df.columns:
            if "G1 (Pa)" not in df.columns:
                df["G1 (Pa)"] = np.nan
            df["G1 (Pa)"] = df["G1 (Pa)"].fillna(df["G (Pa)"])
        if "η (Pa·s)" in df.columns:
            if "η1 (Pa·s)" not in df.columns:
                df["η1 (Pa·s)"] = np.nan
            df["η1 (Pa·s)"] = df["η1 (Pa·s)"].fillna(df["η (Pa·s)"])
        if "tau (s)" in df.columns:
            if "tau1 (s)" not in df.columns:
                df["tau1 (s)"] = np.nan
            df["tau1 (s)"] = df["tau1 (s)"].fillna(df["tau (s)"])

        cols = ['Sample', 'Model', 'R2 Score',
                'G1 (Pa)', 'η1 (Pa·s)', 'tau1 (s)',
                'G2 (Pa)', 'η2 (Pa·s)', 'tau2 (s)',
                'G_perm (Pa)', 'G_trans (Pa)', 'η_trans (Pa·s)', 'tauZ (s)']
        df = df.reindex(columns=cols)

        table_vals = []
        for col in df.columns:
            if col in ('Sample', 'Model'):
                table_vals.append(df[col].tolist())
            elif col == 'R2 Score':
                table_vals.append([f'{v:.3f}' if pd.notna(v) else '-' for v in df[col]])
            elif 'tau' in col:
                table_vals.append([
                    ('∞' if v == float('inf') else f'{v:.2f}') if pd.notna(v) else '-'
                    for v in df[col]
                ])
            else:
                table_vals.append([f'{v:.2e}' if pd.notna(v) else '-' for v in df[col]])

        tbl = go.Figure(data=[go.Table(
            header=dict(values=[f'<b>{c}</b>' for c in df.columns],
                        fill_color='paleturquoise', align='left', font=dict(size=14)),
            cells=dict(values=table_vals, fill_color='lavender', align='left', font=dict(size=13))
        )])
        tbl.update_layout(title_text="<b>Stress Relaxation Results</b>",
                          margin=dict(l=20,r=20,t=50,b=20), title_x=0.5,
                          height=100+len(df)*35)
    else:
        tbl = go.Figure()

    return multi.to_dict(), tbl.to_dict()
