"""
Amplitude Sweep analysis — LVER detection and G'/G'' plotting.
Ported from interface.py (Gabriel David, 2025).
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def analyze_lver(
    dataframes_list: list[tuple[str, pd.DataFrame]],
    plateau_points: int = 5,
    deviation: float = 0.05,
) -> list[dict]:
    """
    Detect Linear Viscoelastic Region (LVER) end point for each sample.

    Parameters
    ----------
    dataframes_list : list of (sample_name, DataFrame)
        Must contain 'Shear Strain', 'Storage Modulus', 'Loss Modulus'.
    plateau_points : int
        Number of initial points used to estimate the plateau modulus.
    deviation : float
        Fractional deviation threshold (default 5 %).

    Returns
    -------
    list of dicts with LVER strain, storage modulus, and loss modulus.
    """
    results = []
    for sample_name, df in dataframes_list:
        required = {'Shear Strain', 'Storage Modulus', 'Loss Modulus'}
        if not required.issubset(df.columns):
            continue

        x  = pd.to_numeric(df['Shear Strain'], errors='coerce').to_numpy()
        gp = pd.to_numeric(df['Storage Modulus'], errors='coerce').to_numpy()
        gl = pd.to_numeric(df['Loss Modulus'], errors='coerce').to_numpy()

        plateau = np.nanmean(gp[:plateau_points])
        lower   = plateau * (1 - deviation)

        idx_break = np.where(gp < lower)[0]

        if idx_break.size and idx_break[0] > 0:
            i = idx_break[0]
            x1, y1_gp, y1_gl = x[i-1], gp[i-1], gl[i-1]
            x2, y2_gp, y2_gl = x[i],   gp[i],   gl[i]
            lver_strain  = x1 + (lower - y1_gp) * (x2 - x1) / (y2_gp - y1_gp)
            lver_storage = lower
            lver_loss    = y1_gl + (lver_strain - x1) * (y2_gl - y1_gl) / (x2 - x1)
        else:
            lver_strain  = x[-1]
            lver_storage = gp[-1]
            lver_loss    = gl[-1]

        results.append({
            "Sample":               sample_name,
            "Shear Strain (1)":     float(lver_strain),
            "Storage Modulus (Pa)": float(lver_storage),
            "Loss Modulus (Pa)":    float(lver_loss),
        })
    return results


def build_amplitude_figures(
    dataframes_list: list[tuple[str, pd.DataFrame]],
    units: dict,
    lver_results: list[dict] | None = None,
) -> tuple[dict, dict]:
    """
    Build Plotly figures for amplitude sweep.

    Returns
    -------
    (sweep_plot_json, lver_table_json)
    """
    colors  = px.colors.qualitative.Vivid
    symbols = ["cross","triangle-up","circle","square","diamond","x","triangle-down","star"]

    fig = go.Figure()

    for i, (name, df) in enumerate(dataframes_list):
        color = colors[i % len(colors)]
        x = pd.to_numeric(df.get('Shear Strain'), errors='coerce')
        for j, col in enumerate(['Storage Modulus', 'Loss Modulus']):
            if col in df.columns:
                y = pd.to_numeric(df[col], errors='coerce')
                fig.add_scatter(x=x, y=y, mode='markers+lines',
                                name=f"{name} — {col}",
                                marker=dict(color=color, symbol=symbols[j % len(symbols)]),
                                line=dict(color=color, dash='dash' if j else 'solid'))

    strain_unit = units.get("Shear Strain", "1")
    modulus_unit = units.get("Storage Modulus", "Pa")

    # LVER markers
    if lver_results:
        lver_df = pd.DataFrame(lver_results)
        mean_v = lver_df[["Shear Strain (1)","Storage Modulus (Pa)","Loss Modulus (Pa)"]].mean()
        std_v  = lver_df[["Shear Strain (1)","Storage Modulus (Pa)","Loss Modulus (Pa)"]].std(ddof=0).fillna(0)

        ms, ss = mean_v["Shear Strain (1)"], std_v["Shear Strain (1)"]
        mG, sG = mean_v["Storage Modulus (Pa)"], std_v["Storage Modulus (Pa)"]
        mL, sL = mean_v["Loss Modulus (Pa)"], std_v["Loss Modulus (Pa)"]

        fig.add_trace(go.Scatter(x=[ms], y=[mG], mode='markers', name='LVER G\'',
                                 marker=dict(color='red', symbol='cross', size=12),
                                 error_x=dict(type='data', array=[ss], visible=True),
                                 error_y=dict(type='data', array=[sG], visible=True)))
        fig.add_trace(go.Scatter(x=[ms], y=[mL], mode='markers', name='LVER G\'\'',
                                 marker=dict(color='darkred', symbol='cross', size=12),
                                 error_x=dict(type='data', array=[ss], visible=True),
                                 error_y=dict(type='data', array=[sL], visible=True)))

    fig.update_layout(
        title="<b>Amplitude Sweep</b>", title_x=0.5,
        xaxis_title=f"Shear Strain ({strain_unit})",
        yaxis_title=f"Modulus ({modulus_unit})",
        xaxis_type="log", yaxis_type="log",
        legend_title="Samples"
    )

    # LVER table
    if lver_results:
        df_lver = pd.DataFrame(lver_results)
        numeric_cols = df_lver.select_dtypes(include='number').columns
        means = df_lver[numeric_cols].mean()
        stds  = df_lver[numeric_cols].std(ddof=0).fillna(0)

        table_vals = []
        for col in df_lver.columns:
            if col == 'Sample':
                table_vals.append(df_lver[col].tolist() + ['<b>Mean</b>','<b>Std Dev</b>'])
            else:
                cells = [f"{v:.4f}" for v in df_lver[col]]
                cells += [f"<b>{means[col]:.4f}</b>", f"<b>{stds[col]:.4f}</b>"]
                table_vals.append(cells)

        height = 200 + len(lver_results)*40
        tbl = go.Figure(data=[go.Table(
            header=dict(values=[f'<b>{c}</b>' for c in df_lver.columns],
                        fill_color='paleturquoise', align='left', font=dict(size=14)),
            cells=dict(values=table_vals, fill_color='lavender', align='left', font=dict(size=13))
        )])
        tbl.update_layout(title="<b>LVER Results</b>", margin=dict(l=20,r=20,t=50,b=20),
                          title_x=0.5, height=height)
    else:
        tbl = go.Figure()

    return fig.to_dict(), tbl.to_dict()
