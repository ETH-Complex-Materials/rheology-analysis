"""
Temperature Sweep analysis — G', G'' vs temperature, gel-point detection, tan(δ).
New module (not in original interface.py).
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def analyze_temperature_sweep(
    dataframes_list: list[tuple[str, pd.DataFrame]],
) -> list[dict]:
    """
    Extract temperature-sweep data and detect gel point (G'=G'' crossover).

    Parameters
    ----------
    dataframes_list : list of (sample_name, DataFrame)
        Must contain 'Temperature' and at least 'Storage Modulus'.

    Returns
    -------
    list of result dicts per sample.
    """
    results = []
    temp_col_candidates = ["Temperature", "temperature", "Temp"]

    for sample_name, df in dataframes_list:
        temp_col = next((c for c in temp_col_candidates if c in df.columns), None)
        if temp_col is None:
            continue
        if "Storage Modulus" not in df.columns:
            continue

        T  = pd.to_numeric(df[temp_col], errors='coerce').to_numpy()
        gp = pd.to_numeric(df['Storage Modulus'], errors='coerce').to_numpy()
        gl = pd.to_numeric(df.get('Loss Modulus', pd.Series(dtype=float)), errors='coerce').to_numpy() \
             if 'Loss Modulus' in df.columns else np.full_like(T, np.nan)

        mask = np.isfinite(T) & np.isfinite(gp)
        T, gp, gl = T[mask], gp[mask], gl[mask]

        res = {
            "Sample": sample_name,
            "temp_col": temp_col,
            "data": {
                "T":  T.tolist(),
                "gp": gp.tolist(),
                "gl": gl.tolist(),
            }
        }

        # Gel point: crossover where G' = G''
        gl_valid = np.isfinite(gl)
        if gl_valid.any():
            diff = gp - gl
            sign_changes = np.where(np.diff(np.sign(diff[np.isfinite(diff)])))[0]
            gl_f = gl[np.isfinite(diff)]
            gp_f = gp[np.isfinite(diff)]
            T_f  = T[np.isfinite(diff)]
            diff_f = diff[np.isfinite(diff)]
            if len(sign_changes):
                idx = sign_changes[0]
                t0, t1 = T_f[idx], T_f[idx+1]
                d0, d1 = diff_f[idx], diff_f[idx+1]
                if d1 != d0:
                    T_cross = t0 - d0*(t1-t0)/(d1-d0)
                    G_cross = float(np.interp(T_cross, T_f, gp_f))
                    res["gel_point"] = {"T": float(T_cross), "G": G_cross}

        results.append(res)
    return results


def build_temperature_figures(
    analysis_results: list[dict],
    units: dict,
    show_tan_delta: bool = True,
) -> list[dict]:
    """
    Build Plotly figures for temperature sweep.

    Returns
    -------
    list of Plotly figure JSON dicts:
      [0] G', G'' vs temperature
      [1] tan(δ) vs temperature (if show_tan_delta)
    """
    colors  = px.colors.qualitative.Vivid
    figures = []

    temp_label = units.get("Temperature", "°C")
    mod_label  = units.get("Storage Modulus", "Pa")

    # --- G'/G'' vs Temperature ---
    fig_main = go.Figure()

    for i, res in enumerate(analysis_results):
        col = colors[i % len(colors)]
        d   = res["data"]
        T   = d["T"]
        gp  = d["gp"]
        gl  = d["gl"]
        name = res["Sample"]

        fig_main.add_trace(go.Scatter(x=T, y=gp, mode='markers+lines', name=f"{name} G'",
                                      marker=dict(color=col, symbol='circle'),
                                      line=dict(color=col)))

        if any(np.isfinite(gl)):
            fig_main.add_trace(go.Scatter(x=T, y=gl, mode='markers+lines', name=f"{name} G''",
                                          marker=dict(color=col, symbol='square'),
                                          line=dict(color=col, dash='dash')))

        # Gel-point marker
        if "gel_point" in res:
            gpt = res["gel_point"]
            fig_main.add_trace(go.Scatter(
                x=[gpt["T"]], y=[gpt["G"]],
                mode='markers',
                name=f"{name} gel point (T={gpt['T']:.1f} {temp_label})",
                marker=dict(color=col, symbol='star', size=14,
                            line=dict(width=2, color='black'))
            ))

    fig_main.update_layout(
        title="<b>Temperature Sweep — G′ and G″</b>", title_x=0.5,
        xaxis_title=f"Temperature ({temp_label})",
        yaxis_title=f"Modulus ({mod_label})",
        legend_title="Samples"
    )
    figures.append(fig_main.to_dict())

    # --- tan(δ) vs temperature ---
    if show_tan_delta:
        fig_tan = go.Figure()
        for i, res in enumerate(analysis_results):
            col = colors[i % len(colors)]
            d = res["data"]
            gp_arr = np.array(d["gp"])
            gl_arr = np.array(d["gl"])
            with np.errstate(divide='ignore', invalid='ignore'):
                tan_d = np.where(gp_arr > 0, gl_arr / gp_arr, np.nan)
            fig_tan.add_trace(go.Scatter(x=d["T"], y=tan_d.tolist(),
                                         mode='markers+lines', name=res["Sample"],
                                         marker=dict(color=col), line=dict(color=col)))
            # Mark gel point on tan(δ) plot
            if "gel_point" in res:
                gpt = res["gel_point"]
                fig_tan.add_trace(go.Scatter(
                    x=[gpt["T"]], y=[1.0],
                    mode='markers',
                    name=f"{res['Sample']} gel point",
                    marker=dict(color=col, symbol='star', size=14,
                                line=dict(width=2, color='black')),
                    showlegend=False
                ))

        fig_tan.add_hline(y=1.0, line_dash="dash", line_color="gray",
                          annotation_text="tan(δ)=1 (gel point)")
        fig_tan.update_layout(
            title="<b>Temperature Sweep — tan(δ)</b>", title_x=0.5,
            xaxis_title=f"Temperature ({temp_label})",
            yaxis_title="tan(δ) = G''/G'"
        )
        figures.append(fig_tan.to_dict())

    return figures
