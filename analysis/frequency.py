"""
Frequency Sweep analysis — G', G'', tan(δ), |η*|, power-law fitting, Cole-Cole.
New module (not in original interface.py).
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy.optimize import curve_fit


def _r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred)**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    return 1.0 if ss_tot == 0 else 1 - ss_res / ss_tot


def _power_law(omega, a, n):
    return a * omega**n


def analyze_frequency_sweep(
    dataframes_list: list[tuple[str, pd.DataFrame]],
) -> list[dict]:
    """
    Extract frequency-sweep data and fit power-law G' = a·ω^n.

    Parameters
    ----------
    dataframes_list : list of (sample_name, DataFrame)
        Must contain a frequency column ('Angular Frequency' or 'Frequency')
        and at least one of 'Storage Modulus', 'Loss Modulus'.

    Returns
    -------
    list of result dicts per sample.
    """
    results = []
    freq_col_candidates = ["Angular Frequency", "Frequency", "Angular frequency", "frequency"]

    for sample_name, df in dataframes_list:
        # Identify frequency column
        freq_col = next((c for c in freq_col_candidates if c in df.columns), None)
        if freq_col is None:
            continue
        if "Storage Modulus" not in df.columns:
            continue

        omega = pd.to_numeric(df[freq_col], errors='coerce').to_numpy()
        gp    = pd.to_numeric(df.get('Storage Modulus', pd.Series()), errors='coerce').to_numpy()
        gl    = pd.to_numeric(df.get('Loss Modulus', pd.Series(dtype=float)), errors='coerce').to_numpy() \
                if 'Loss Modulus' in df.columns else np.full_like(omega, np.nan)
        eta_star = pd.to_numeric(df.get('Complex Viscosity', pd.Series(dtype=float)), errors='coerce').to_numpy() \
                   if 'Complex Viscosity' in df.columns else None

        mask = np.isfinite(omega) & np.isfinite(gp)
        omega_c, gp_c, gl_c = omega[mask], gp[mask], gl[mask]

        res = {
            "Sample": sample_name,
            "freq_col": freq_col,
            "data": {
                "omega": omega_c.tolist(),
                "gp":    gp_c.tolist(),
                "gl":    gl_c.tolist(),
            }
        }

        if eta_star is not None:
            res["data"]["eta_star"] = eta_star[mask].tolist()

        # Power-law fit to G'
        if len(omega_c) >= 3:
            try:
                # Fit in log-space for robustness: only positive values
                pos = gp_c > 0
                if pos.sum() >= 3:
                    p, _ = curve_fit(_power_law, omega_c[pos], gp_c[pos],
                                     p0=[np.mean(gp_c), 0.5],
                                     bounds=([0, -3], [1e12, 3]), maxfev=5000)
                    fit = _power_law(omega_c, *p)
                    res["params_powerlaw"] = {
                        "a (Pa·s^n)": float(p[0]),
                        "n (exponent)": float(p[1]),
                        "R2 Score": _r2(gp_c, fit),
                    }
                    res["fitted_gp"] = fit.tolist()
            except (RuntimeError, ValueError):
                res["params_powerlaw"] = {"Error": "Fit failed"}

        # Gel point: crossover G' = G''
        if np.any(np.isfinite(gl_c)) and len(gl_c) > 1:
            diff = gp_c - gl_c
            sign_changes = np.where(np.diff(np.sign(diff)))[0]
            if len(sign_changes):
                idx = sign_changes[0]
                # Linear interpolation
                x0, x1 = omega_c[idx], omega_c[idx+1]
                d0, d1 = diff[idx], diff[idx+1]
                if d1 != d0:
                    omega_cross = x0 - d0*(x1-x0)/(d1-d0)
                    g_cross = float(np.interp(omega_cross, omega_c, gp_c))
                    res["gel_point"] = {"omega": float(omega_cross), "G": g_cross}

        results.append(res)
    return results


def build_frequency_figures(
    analysis_results: list[dict],
    units: dict,
    show_tan_delta: bool = True,
    show_eta_star: bool = False,
    show_cole_cole: bool = False,
) -> list[dict]:
    """
    Build Plotly figures for frequency sweep.

    Returns
    -------
    list of Plotly figure JSON dicts:
      [0] G', G'' vs frequency (main)
      [1] tan(δ) vs frequency  (if show_tan_delta)
      [2] |η*| vs frequency    (if show_eta_star)
      [3] Cole-Cole (G'' vs G') (if show_cole_cole)
    """
    colors  = px.colors.qualitative.Vivid
    figures = []

    freq_label = units.get("Angular Frequency", units.get("Frequency", "rad/s"))
    mod_label  = units.get("Storage Modulus", "Pa")

    # --- Main G'/G'' plot ---
    fig_main = go.Figure()
    for i, res in enumerate(analysis_results):
        col = colors[i % len(colors)]
        d = res["data"]
        omega = d["omega"]
        gp    = d["gp"]
        gl    = d["gl"]
        name  = res["Sample"]

        fig_main.add_trace(go.Scatter(x=omega, y=gp, mode='markers+lines', name=f"{name} G'",
                                      marker=dict(color=col, symbol='circle'),
                                      line=dict(color=col)))
        if any(np.isfinite(gl)):
            fig_main.add_trace(go.Scatter(x=omega, y=gl, mode='markers+lines', name=f"{name} G''",
                                          marker=dict(color=col, symbol='square'),
                                          line=dict(color=col, dash='dash')))

        # Power-law fit overlay
        if "fitted_gp" in res:
            n  = res.get("params_powerlaw", {}).get("n (exponent)", None)
            r2 = res.get("params_powerlaw", {}).get("R2 Score", None)
            lbl = f"{name} G' fit"
            if n is not None:
                lbl += f" (n={n:.2f}, R²={r2:.3f})" if r2 else f" (n={n:.2f})"
            fig_main.add_trace(go.Scatter(x=omega, y=res["fitted_gp"],
                                          mode='lines', name=lbl,
                                          line=dict(color=col, dash='dot', width=2)))

        # Gel-point marker
        if "gel_point" in res:
            gp_cross = res["gel_point"]
            fig_main.add_trace(go.Scatter(
                x=[gp_cross["omega"]], y=[gp_cross["G"]],
                mode='markers', name=f"{name} gel point",
                marker=dict(color=col, symbol='star', size=14,
                            line=dict(width=2, color='black'))
            ))

    fig_main.update_layout(
        title="<b>Frequency Sweep — G′ and G″</b>", title_x=0.5,
        xaxis_title=f"Angular Frequency ({freq_label})",
        yaxis_title=f"Modulus ({mod_label})",
        xaxis_type="log", yaxis_type="log",
        legend_title="Samples"
    )
    figures.append(fig_main.to_dict())

    # --- tan(δ) ---
    if show_tan_delta:
        fig_tan = go.Figure()
        for i, res in enumerate(analysis_results):
            col = colors[i % len(colors)]
            d = res["data"]
            gp_arr = np.array(d["gp"])
            gl_arr = np.array(d["gl"])
            with np.errstate(divide='ignore', invalid='ignore'):
                tan_d = np.where(gp_arr > 0, gl_arr / gp_arr, np.nan)
            fig_tan.add_trace(go.Scatter(x=d["omega"], y=tan_d.tolist(),
                                         mode='markers+lines', name=res["Sample"],
                                         marker=dict(color=col), line=dict(color=col)))
        fig_tan.update_layout(
            title="<b>Frequency Sweep — tan(δ)</b>", title_x=0.5,
            xaxis_title=f"Angular Frequency ({freq_label})",
            yaxis_title="tan(δ) = G''/G'",
            xaxis_type="log"
        )
        figures.append(fig_tan.to_dict())

    # --- |η*| ---
    if show_eta_star:
        fig_eta = go.Figure()
        for i, res in enumerate(analysis_results):
            col = colors[i % len(colors)]
            d = res["data"]
            if "eta_star" in d:
                fig_eta.add_trace(go.Scatter(x=d["omega"], y=d["eta_star"],
                                             mode='markers+lines', name=res["Sample"],
                                             marker=dict(color=col), line=dict(color=col)))
        fig_eta.update_layout(
            title="<b>Frequency Sweep — Complex Viscosity |η*|</b>", title_x=0.5,
            xaxis_title=f"Angular Frequency ({freq_label})",
            yaxis_title="Complex Viscosity |η*| (Pa·s)",
            xaxis_type="log", yaxis_type="log"
        )
        figures.append(fig_eta.to_dict())

    # --- Cole-Cole (G'' vs G') ---
    if show_cole_cole:
        fig_cc = go.Figure()
        for i, res in enumerate(analysis_results):
            col = colors[i % len(colors)]
            d = res["data"]
            fig_cc.add_trace(go.Scatter(x=d["gp"], y=d["gl"],
                                        mode='markers+lines', name=res["Sample"],
                                        marker=dict(color=col), line=dict(color=col)))
        fig_cc.update_layout(
            title="<b>Cole-Cole Plot</b>", title_x=0.5,
            xaxis_title=f"G' ({mod_label})",
            yaxis_title=f"G'' ({mod_label})"
        )
        figures.append(fig_cc.to_dict())

    return figures
