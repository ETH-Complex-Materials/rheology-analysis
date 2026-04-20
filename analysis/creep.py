"""
Creep Recovery analysis — Burgers, Maxwell, Kelvin-Voigt model fitting.
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

def _burgers_creep(t_data, E1, eta1, E2, eta2, sigma0, t_release):
    strain = np.zeros_like(t_data, dtype=float)
    E1 = max(E1, 1e-9); eta1 = max(eta1, 1e-9)
    E2 = max(E2, 1e-9); eta2 = max(eta2, 1e-9)
    tau2 = eta2 / E2

    idx_c = t_data <= t_release
    if idx_c.any():
        t = t_data[idx_c]
        strain[idx_c] = sigma0/E1 + (sigma0/eta1)*t + (sigma0/E2)*(1 - np.exp(-t/tau2))

    idx_r = t_data > t_release
    if idx_r.any():
        t_r = t_data[idx_r] - t_release
        eps_perm = (sigma0/eta1)*t_release
        eps_kv   = (sigma0/E2)*(1 - np.exp(-t_release/tau2))
        strain[idx_r] = eps_perm + eps_kv * np.exp(-t_r/tau2)

    return strain


def _maxwell_creep(t_data, E, eta, sigma0, t_release):
    strain = np.zeros_like(t_data, dtype=float)
    E = max(E, 1e-9); eta = max(eta, 1e-9)

    idx_c = t_data <= t_release
    if idx_c.any():
        t = t_data[idx_c]
        strain[idx_c] = sigma0/E + (sigma0/eta)*t

    idx_r = t_data > t_release
    if idx_r.any():
        strain[idx_r] = (sigma0/eta)*t_release
    return strain


def _kelvin_creep(t_data, E, eta, sigma0, t_release):
    strain = np.zeros_like(t_data, dtype=float)
    E = max(E, 1e-9); eta = max(eta, 1e-9)
    tau = eta / E

    idx_c = t_data <= t_release
    if idx_c.any():
        t = t_data[idx_c]
        strain[idx_c] = (sigma0/E)*(1 - np.exp(-t/tau))

    idx_r = t_data > t_release
    if idx_r.any():
        t_r = t_data[idx_r] - t_release
        eps_rel = (sigma0/E)*(1 - np.exp(-t_release/tau))
        strain[idx_r] = eps_rel * np.exp(-t_r/tau)
    return strain


def _zener_creep(t_data, G_perm, G_trans, eta_trans, sigma0, t_release):
    """
    Zener / Standard Linear Solid — parallel representation.
    Permanent spring G_perm in parallel with a Maxwell branch (G_trans + eta_trans).
    Recovery via Boltzmann superposition: apply −σ₀ at t_release.
    """
    G_perm    = max(G_perm,    1e-9)
    G_trans   = max(G_trans,   1e-9)
    eta_trans = max(eta_trans, 1e-9)
    tau_ret = eta_trans * (G_perm + G_trans) / (G_perm * G_trans)

    def J(t):
        return 1.0 / G_perm - (1.0 / G_perm - 1.0 / (G_perm + G_trans)) * np.exp(-t / tau_ret)

    strain = sigma0 * J(t_data)

    idx_r = t_data > t_release
    if idx_r.any():
        strain[idx_r] -= sigma0 * J(t_data[idx_r] - t_release)

    return strain


def _r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else 0.0
    return 1 - ss_res / ss_tot


def _infer_sigma0_from_name(sample_name: str) -> float | None:
    """
    Extract σ₀ from explicit stress markers in a sample/file name.

    Accepts patterns such as:
    - "50Pa"
    - "50 Pa"
    - "stress_50pa"

    Intentionally ignores generic digits like "S1" to avoid false positives.
    """
    if not sample_name:
        return None

    match = re.search(
        r"(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*pa(?=$|[^A-Za-z0-9])",
        sample_name,
        re.IGNORECASE,
    )
    if not match:
        return None

    val = float(match.group(1))
    return val if val > 0 else None


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def _auto_detect_t_release(df: pd.DataFrame) -> float | None:
    """
    Detect stress release time.
    Primary strategy: time of the global Shear Strain maximum.
    Fallback: first NaN/negative creep-compliance after valid data.
    """
    if 'Time' not in df.columns:
        return None
    t_col = pd.to_numeric(df['Time'], errors='coerce')

    # Primary strategy – t_release = time of the global Shear Strain maximum for t > 5 s
    # The 5 s guard excludes instrument artefacts at the very start of the series.
    if 'Shear Strain' in df.columns:
        strain = pd.to_numeric(df['Shear Strain'], errors='coerce')
        valid = strain.notna() & t_col.notna() & (strain > 0) & (t_col > 5.0)
        if valid.sum() > 10:
            peak_idx = strain[valid].idxmax()
            return float(t_col[peak_idx])

    # Fallback – compliance goes NaN/negative at stress release
    if 'Creep Compliance' in df.columns:
        comp = pd.to_numeric(df['Creep Compliance'], errors='coerce')
        valid_mask = comp.notna() & (comp > 0)
        n_valid = valid_mask.sum()
        if n_valid > 10:
            after_valid = (~valid_mask) & (t_col > t_col[valid_mask].median())
            if after_valid.any():
                return float(t_col[after_valid.idxmax()])

    return None


def analyze_creep_recovery(
    dataframes_list: list[tuple[str, pd.DataFrame]],
    t_release_val: float | None = None,
    drop_index=None,
    enable_maxwell: bool = False,
    enable_kelvin: bool = False,
    enable_zener: bool = False,
    prune_window: float = 0.0,
    exclude_ranges: list | None = None,
    prune_start_n: int = 0,
    prune_release_n: int = 0,
) -> list[dict]:
    """
    Fit viscoelastic models to creep-recovery data.

    Parameters
    ----------
    dataframes_list : list of (sample_name, DataFrame)
        Each DataFrame must have columns 'Time' and 'Shear Strain'.
    t_release_val : float or None
        Time at which stress is released. If None, auto-detected from data.
    drop_index : array-like, optional
        DataFrame index values to drop before fitting.
    enable_maxwell / enable_kelvin : bool
        Whether to fit optional models.
    prune_window : float
        Legacy time-based pruning after t_release. Disabled by default; overridden
        when prune_release_n > 0.
    prune_start_n : int
        Number of data points to exclude from the beginning of the series (Zone 1).
    prune_release_n : int
        Number of data points to exclude right after t_release (Zone 2).
        When > 0, takes precedence over prune_window for the post-release region.

    Returns
    -------
    list of result dicts (one per sample).
    """
    results = []

    for sample_name, df in dataframes_list:
        if 'Time' not in df.columns or 'Shear Strain' not in df.columns:
            continue

        # Use the same σ₀ inference as the pre-analysis UI to keep displayed and
        # fitted values consistent. Only fall back to the sample name when the
        # data columns do not provide a reliable estimate.
        sigma0 = infer_sigma0(df)
        if sigma0 is None or sigma0 == 0:
            sigma0 = _infer_sigma0_from_name(sample_name)

        if sigma0 is None or sigma0 == 0:
            if 'Creep Compliance' in df.columns:
                strain_col = pd.to_numeric(df['Shear Strain'], errors='coerce')
                comp_col   = pd.to_numeric(df['Creep Compliance'], errors='coerce')
                valid = strain_col.notna() & comp_col.notna() & (comp_col > 0)
                if valid.any():
                    # Use a stable window of early creep points
                    idx_valid = np.where(valid)[0][:20]
                    s_vals = strain_col.values[idx_valid]
                    c_vals = comp_col.values[idx_valid]
                    # compliance = strain_decimal / sigma  →  sigma = strain_decimal / compliance
                    # If strain is in %, strain_decimal = strain_% / 100
                    ratio = np.median(s_vals / c_vals)
                    # Heuristic: if ratio > 200, strain is likely in %, divide by 100
                    sigma0 = ratio / 100.0 if ratio > 200 else ratio

        if sigma0 is None or sigma0 <= 0:
            sigma0 = 1.0

        # Auto-detect t_release if not provided
        t_rel = t_release_val if t_release_val is not None else _auto_detect_t_release(df)
        if t_rel is None:
            t_rel = 300.0  # last-resort default

        df_p = df.copy()
        if drop_index is not None and len(drop_index):
            df_p = df_p.drop(drop_index, errors='ignore')

        t = df_p["Time"].to_numpy(dtype=float)
        s = df_p["Shear Strain"].to_numpy(dtype=float)

        mask = np.isfinite(t) & np.isfinite(s)
        t, s = t[mask], s[mask]
        if len(t) == 0:
            continue

        # Shear Strain is always stored in % by the instrument; convert to absolute.
        s = s / 100.0

        # Zone 1 — exclude first prune_start_n data points (initial loading transient)
        if prune_start_n > 0 and prune_start_n < len(t):
            t, s = t[prune_start_n:], s[prune_start_n:]

        # Zone 2 — exclude first prune_release_n data points after t_release
        #           (stress-release oscillation artefact); falls back to prune_window if 0
        if prune_release_n > 0:
            after_idx = np.where(t > t_rel)[0]
            if len(after_idx) > 0:
                n_excl = min(prune_release_n, len(after_idx))
                excl = np.zeros(len(t), dtype=bool)
                excl[after_idx[:n_excl]] = True
                t, s = t[~excl], s[~excl]
        elif prune_window > 0:
            keep_post = ~((t > t_rel) & (t < t_rel + prune_window))
            t, s = t[keep_post], s[keep_post]

        # Additional user-defined exclusion ranges (kept for backward compatibility)
        if exclude_ranges:
            for t_lo, t_hi in exclude_ranges:
                excl = (t >= float(t_lo)) & (t <= float(t_hi))
                t, s = t[~excl], s[~excl]

        if len(t) == 0:
            continue

        res = {"Sample": sample_name, "sigma0": sigma0, "t_release": t_rel,
               "experimental_data": {"t": t.tolist(), "strain": s.tolist()}}

        # Burgers (always)
        def _b(t, E1, eta1, E2, eta2):
            return _burgers_creep(t, E1, eta1, E2, eta2, sigma0, t_rel)
        try:
            p, _ = curve_fit(_b, t, s, p0=[10000, 1e8, 10000, 1e6],
                             bounds=(0,np.inf), maxfev=10000)
            fit = _b(t, *p)
            res["params_burgers"] = {"G1 (Pa)": p[0], "η1 (Pa·s)": p[1],
                                     "G2 (Pa)": p[2], "η2 (Pa·s)": p[3],
                                     "R2 Score": _r2(s, fit)}
            res["fitted_data_burgers"] = {"strain": fit.tolist()}
        except RuntimeError:
            res["params_burgers"] = {"Error": "Fit failed"}
            res["fitted_data_burgers"] = {"strain": None}

        # Maxwell (optional)
        if enable_maxwell:
            def _m(t, E, eta):
                return _maxwell_creep(t, E, eta, sigma0, t_rel)
            try:
                p, _ = curve_fit(_m, t, s, p0=[10000, 1e8],
                                 bounds=(0,np.inf), maxfev=5000)
                fit = _m(t, *p)
                res["params_maxwell"] = {"G (Pa)": p[0], "η (Pa·s)": p[1],
                                        "R2 Score": _r2(s, fit)}
                res["fitted_data_maxwell"] = {"strain": fit.tolist()}
            except RuntimeError:
                res["params_maxwell"] = {"Error": "Fit failed"}
                res["fitted_data_maxwell"] = {"strain": None}

        # Kelvin-Voigt (optional)
        if enable_kelvin:
            def _k(t, E, eta):
                return _kelvin_creep(t, E, eta, sigma0, t_rel)
            try:
                p, _ = curve_fit(_k, t, s, p0=[10000, 1e6],
                                 bounds=(0,np.inf), maxfev=5000)
                fit = _k(t, *p)
                res["params_kelvin"] = {"G (Pa)": p[0], "η (Pa·s)": p[1],
                                       "R2 Score": _r2(s, fit)}
                res["fitted_data_kelvin"] = {"strain": fit.tolist()}
            except RuntimeError:
                res["params_kelvin"] = {"Error": "Fit failed"}
                res["fitted_data_kelvin"] = {"strain": None}

        # Zener / SLS (optional)
        if enable_zener:
            def _z(t, G_perm, G_trans, eta_trans):
                return _zener_creep(t, G_perm, G_trans, eta_trans, sigma0, t_rel)
            try:
                p, _ = curve_fit(_z, t, s, p0=[10000, 10000, 1e6],
                                 bounds=(0, np.inf), maxfev=10000)
                fit = _z(t, *p)
                G_p, G_t, eta_t = p
                tauZ = eta_t * (G_p + G_t) / (G_p * G_t)
                res["params_zener"] = {
                    "G_perm (Pa)":    G_p,
                    "G_trans (Pa)":   G_t,
                    "η_trans (Pa·s)": eta_t,
                    "tauZ (s)":       tauZ,
                    "R2 Score":       _r2(s, fit),
                }
                res["fitted_data_zener"] = {"strain": fit.tolist()}
            except (RuntimeError, ValueError):
                res["params_zener"] = {"Error": "Fit failed"}
                res["fitted_data_zener"] = {"strain": None}

        results.append(res)
    return results


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

_OVERLAY_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]


def build_creep_figures(
    analysis_results: list[dict],
    units: dict,
    enable_maxwell: bool = False,
    enable_kelvin: bool = False,
    enable_zener: bool = False,
    overlay: bool = False,
) -> tuple[dict, dict]:
    """
    Build Plotly figures for creep recovery.

    Returns
    -------
    (multi_plot_json, table_json) — both as Plotly JSON dicts.
    """
    time_unit   = units.get("Time", "s")
    strain_unit = units.get("Shear Strain", "%")

    # --- multi-sample plot with dropdown ---
    multi = go.Figure()
    all_traces = []
    buttons = []
    traces_per = 0

    for i, res in enumerate(analysis_results):
        t  = res["experimental_data"]["t"]
        sn = res["experimental_data"]["strain"]
        visible = True if overlay else (i == 0)
        color   = _OVERLAY_COLORS[i % len(_OVERLAY_COLORS)] if overlay else '#1f77b4'
        cur = []

        exp_name = res["Sample"] if overlay else 'Experimental'
        cur.append(go.Scatter(x=t, y=sn, mode='markers', name=exp_name,
                              legendgroup=res["Sample"], visible=visible,
                              marker=dict(color=color, symbol='circle-open')))

        if res.get("fitted_data_burgers", {}).get("strain") is not None:
            fit_name = f"{res['Sample']} fit" if overlay else 'Burgers'
            fit_color = color if overlay else '#ff7f0e'
            cur.append(go.Scatter(x=t, y=res["fitted_data_burgers"]["strain"],
                                  mode='lines', name=fit_name, legendgroup=res["Sample"],
                                  visible=visible, line=dict(color=fit_color, width=2)))

        if enable_maxwell and res.get("fitted_data_maxwell", {}).get("strain") is not None:
            cur.append(go.Scatter(x=t, y=res["fitted_data_maxwell"]["strain"],
                                  mode='lines', name='Maxwell', legendgroup=res["Sample"],
                                  visible=visible, line=dict(color=color if overlay else '#2ca02c',
                                                             dash='dash')))

        if enable_kelvin and res.get("fitted_data_kelvin", {}).get("strain") is not None:
            cur.append(go.Scatter(x=t, y=res["fitted_data_kelvin"]["strain"],
                                  mode='lines', name='Kelvin-Voigt', legendgroup=res["Sample"],
                                  visible=visible, line=dict(color=color if overlay else '#d62728',
                                                             dash='dot')))

        if enable_zener and res.get("fitted_data_zener", {}).get("strain") is not None:
            cur.append(go.Scatter(x=t, y=res["fitted_data_zener"]["strain"],
                                  mode='lines', name='Zener', legendgroup=res["Sample"],
                                  visible=visible, line=dict(color=color if overlay else '#9467bd',
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
            if "params_burgers" in res and "R2 Score" in res["params_burgers"]:
                r2_parts.append(f"Burgers R²={res['params_burgers']['R2 Score']:.3f}")
            if enable_maxwell and "params_maxwell" in res and "R2 Score" in res["params_maxwell"]:
                r2_parts.append(f"Maxwell R²={res['params_maxwell']['R2 Score']:.3f}")
            if enable_kelvin and "params_kelvin" in res and "R2 Score" in res["params_kelvin"]:
                r2_parts.append(f"KV R²={res['params_kelvin']['R2 Score']:.3f}")
            if enable_zener and "params_zener" in res and "R2 Score" in res["params_zener"]:
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
            title0 = f"<b>{res0['Sample']}</b>" + ((" | " + " | ".join(r2_parts0)) if r2_parts0 else "")

    if buttons:
        multi.update_layout(
            updatemenus=[dict(active=0, buttons=buttons, direction="down",
                              pad={"r":10,"t":10}, showactive=True,
                              x=0.1, xanchor="left", y=1.15, yanchor="top")])

    multi.update_layout(
        title=title0, title_x=0.5,
        xaxis_title=f"Time ({time_unit})",
        yaxis_title="Shear Strain",
        legend_title_text="Legend"
    )

    # --- parameters table ---
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
        # Maxwell / KV use single-element "G (Pa)" / "η (Pa·s)" → merge into G1 / η1
        if "G (Pa)" in df.columns:
            if "G1 (Pa)" not in df.columns:
                df["G1 (Pa)"] = np.nan
            df["G1 (Pa)"] = df["G1 (Pa)"].fillna(df["G (Pa)"])
        if "η (Pa·s)" in df.columns:
            if "η1 (Pa·s)" not in df.columns:
                df["η1 (Pa·s)"] = np.nan
            df["η1 (Pa·s)"] = df["η1 (Pa·s)"].fillna(df["η (Pa·s)"])

        cols = ['Sample', 'Model', 'R2 Score',
                'G1 (Pa)', 'η1 (Pa·s)', 'G2 (Pa)', 'η2 (Pa·s)',
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

        table_fig = go.Figure(data=[go.Table(
            header=dict(values=[f'<b>{c}</b>' for c in df.columns],
                        fill_color='paleturquoise', align='left',
                        font=dict(size=14, color='black')),
            cells=dict(values=table_vals, fill_color='lavender', align='left',
                       font=dict(size=13, color='black'))
        )])
        table_fig.update_layout(title_text="<b>Model Regression Results</b>",
                                 margin=dict(l=20,r=20,t=50,b=20), title_x=0.5,
                                 height=100 + len(df)*35)
    else:
        table_fig = go.Figure()

    return multi.to_dict(), table_fig.to_dict()


# ---------------------------------------------------------------------------
# Recovery component analysis
# ---------------------------------------------------------------------------

def evaluate_recovery_components(analysis_results: list[dict], t_release: float = None) -> list[dict]:
    """Decompose creep into elastic, viscoelastic and plastic fractions."""
    components = []
    for res in analysis_results:
        p = res.get("params_burgers", {})
        # Skip if fit failed or if all four Burgers parameters are absent
        if not p or "Error" in p or "G1 (Pa)" not in p:
            continue
        sample_name = str(res["Sample"])
        # Clamp to avoid division by zero at parameter boundaries
        E1   = max(float(p["G1 (Pa)"]),   1e-9)
        eta1 = max(float(p["η1 (Pa·s)"]), 1e-9)
        E2   = max(float(p["G2 (Pa)"]),   1e-9)
        eta2 = max(float(p["η2 (Pa·s)"]), 1e-9)

        # sigma0 cancels in the fractions, so any positive value works
        sigma0 = 1.0

        # Use per-sample t_release (ignore the passed global value unless set)
        if t_release and float(t_release) > 0:
            t_rel = float(t_release)
        else:
            t_rel = float(res.get("t_release", 0)) or 0.0
            if t_rel <= 0:
                continue  # can't compute without t_release

        # Skip if there are no data points after t_release (no recovery phase in this sample)
        t_data = np.array(res.get("experimental_data", {}).get("t", []))
        if len(t_data) == 0 or not np.any(t_data > t_rel):
            continue

        tau2 = eta2 / E2
        eps_el = sigma0 / E1
        eps_pl = (sigma0 / eta1) * t_rel
        eps_vi = (sigma0 / E2) * (1 - np.exp(-t_rel / tau2))
        total  = eps_el + eps_pl + eps_vi
        if not np.isfinite(total) or total <= 0:
            total = max(eps_el, 1e-30) + max(eps_pl, 1e-30) + max(eps_vi, 1e-30)

        frac_el = 100 * eps_el / total
        frac_vi = 100 * eps_vi / total
        frac_pl = 100 * eps_pl / total

        # Sanity check — skip if any fraction is non-finite
        if not (np.isfinite(frac_el) and np.isfinite(frac_vi) and np.isfinite(frac_pl)):
            continue

        components.append({
            "Sample":       sample_name,
            "eps_elastic":  eps_el,
            "eps_visco":    eps_vi,
            "eps_plastic":  eps_pl,
            "frac_elastic": frac_el,
            "frac_visco":   frac_vi,
            "frac_plastic": frac_pl,
        })
    return components


def build_recovery_component_figures(components: list[dict]) -> dict:
    """Combined bar chart + summary table for recovery components (single figure)."""
    from plotly.subplots import make_subplots

    if not components:
        empty = go.Figure()
        empty.add_annotation(
            text="No recovery data found.<br>Select both segments (creep + recovery) in the<br>Sheet Selection panel to enable this analysis.",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=14), align="center")
        return empty.to_dict()

    df = pd.DataFrame(components)
    means = df[['frac_elastic','frac_visco','frac_plastic']].mean()
    stds  = df[['frac_elastic','frac_visco','frac_plastic']].std(ddof=0).fillna(0)

    avg_row = pd.DataFrame([{'Sample': 'Mean', **means}])
    df_plot = pd.concat([df, avg_row], ignore_index=True)

    n_rows = len(components)
    tbl_height = max(0.28, min(0.40, 0.12 + n_rows * 0.06))
    bar_height = 1.0 - tbl_height

    fig = make_subplots(
        rows=2, cols=1,
        specs=[[{"type": "bar"}], [{"type": "table"}]],
        row_heights=[bar_height, tbl_height],
        vertical_spacing=0.14,
    )

    fig.add_trace(go.Bar(x=df_plot['Sample'], y=df_plot['frac_elastic'],
                         name='Elastic', marker_color='#2196F3',
                         text=[f"{v:.1f}%" for v in df_plot['frac_elastic']],
                         textposition='inside', insidetextanchor='middle'), row=1, col=1)
    fig.add_trace(go.Bar(x=df_plot['Sample'], y=df_plot['frac_visco'],
                         name='Viscoelastic', marker_color='#FF9800',
                         text=[f"{v:.1f}%" for v in df_plot['frac_visco']],
                         textposition='inside', insidetextanchor='middle'), row=1, col=1)
    fig.add_trace(go.Bar(x=df_plot['Sample'], y=df_plot['frac_plastic'],
                         name='Plastic', marker_color='#4CAF50',
                         text=[f"{v:.1f}%" for v in df_plot['frac_plastic']],
                         textposition='inside', insidetextanchor='middle'), row=1, col=1)

    headers = ['Sample', 'Elastic (%)', 'Viscoelastic (%)', 'Plastic (%)']
    cols_d  = ['Sample', 'frac_elastic', 'frac_visco', 'frac_plastic']
    table_vals = []
    for col in cols_d:
        if col == 'Sample':
            table_vals.append(df[col].tolist() + ['<b>Mean</b>', '<b>Std Dev</b>'])
        else:
            cells  = [f"{v:.2f}" for v in df[col]]
            cells += [f"<b>{means[col]:.2f}</b>", f"<b>{stds[col]:.2f}</b>"]
            table_vals.append(cells)

    fig.add_trace(go.Table(
        header=dict(values=[f'<b>{h}</b>' for h in headers],
                    fill_color='paleturquoise', align='left', font=dict(size=13)),
        cells=dict(values=table_vals, fill_color='lavender',  align='left', font=dict(size=12)),
    ), row=2, col=1)

    fig.update_layout(
        barmode='stack',
        title_text='<b>Recovery Component Analysis</b>',
        title_x=0.5,
        xaxis=dict(title='Sample', type='category'),
        yaxis=dict(title='Fraction (%)', range=[0, 108], autorange=False),
        plot_bgcolor='white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        height=560 + n_rows * 20,
        margin=dict(l=60, r=20, t=60, b=40),
    )

    return fig.to_dict()


# ---------------------------------------------------------------------------
# Pre-analysis inference helpers (used by the parser/API to display values
# before the user launches a fit)
# ---------------------------------------------------------------------------

def infer_sigma0(df: pd.DataFrame) -> float | None:
    """
    Infer σ₀ from a DataFrame without a sample name.
    Strategy 1: median of the first 10 positive Shear Stress values.
    Strategy 2: strain/compliance ratio from early creep points.
    Returns None when no reliable estimate can be made.
    """
    if 'Shear Stress' in df.columns:
        ss = pd.to_numeric(df['Shear Stress'], errors='coerce').dropna()
        ss = ss[ss > 0]
        if len(ss):
            val = float(ss.iloc[:10].median())
            if val > 0:
                return val

    if 'Creep Compliance' in df.columns and 'Shear Strain' in df.columns:
        strain_col = pd.to_numeric(df['Shear Strain'], errors='coerce')
        comp_col   = pd.to_numeric(df['Creep Compliance'], errors='coerce')
        valid = strain_col.notna() & comp_col.notna() & (comp_col > 0)
        if valid.any():
            idx_valid = np.where(valid)[0][:20]
            s_vals = strain_col.values[idx_valid]
            c_vals = comp_col.values[idx_valid]
            ratio = np.median(s_vals / c_vals)
            val = ratio / 100.0 if ratio > 200 else ratio
            if val > 0:
                return val

    return None


def infer_t_release(df: pd.DataFrame) -> float | None:
    """Public wrapper around _auto_detect_t_release for pre-analysis display."""
    return _auto_detect_t_release(df)
