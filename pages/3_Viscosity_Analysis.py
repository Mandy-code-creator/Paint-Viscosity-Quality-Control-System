"""
Page 4 – Viscosity Reduction Analysis (Per Resin)
Professional redesign: clean light theme, polished charts
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data_processing import load_and_process, RESIN_COLORS, PROFESSIONAL_COLORS, hex_to_rgba

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Viscosity Per Resin · PaintIQ",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design tokens ─────────────────────────────────────────────────────────────
ACCENT   = "#1A73E8"
RED      = "#E53935"
GREEN    = "#2E7D32"
AMBER    = "#F57C00"
PURPLE   = "#6C3FD6"
TEAL     = "#00796B"

BG_PAGE  = "#F0F2F6"
BG_CARD  = "#FFFFFF"
BORDER   = "#DDE1E9"
GRID     = "#EEF0F4"
FONT     = "#1A1D23"
MUTED    = "#5F6878"
SHADOW   = "0 2px 8px rgba(0,0,0,0.08), 0 0 0 1px rgba(0,0,0,0.04)"

# Rich qualitative palette – high contrast on white
QUAL_PALETTE = [
    "#1A73E8","#E53935","#2E7D32","#F57C00","#7B1FA2",
    "#00796B","#C2185B","#1565C0","#BF360C","#37474F",
    "#558B2F","#6A1B9A",
]

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {{
    background: {BG_PAGE} !important;
    color: {FONT} !important;
    font-family: 'Inter', sans-serif !important;
}}
[data-testid="stAppViewContainer"] > .main {{ background: {BG_PAGE} !important; }}
.block-container {{ padding-top: .4rem !important; background: {BG_PAGE} !important; }}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: {BG_CARD} !important;
    border-right: 1.5px solid {BORDER} !important;
}}
[data-testid="stSidebar"] * {{ color: {FONT} !important; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background: #F7F9FC !important;
    border: 1.5px solid {BORDER} !important;
    border-radius: 8px !important;
}}
[data-testid="stSidebar"] [data-baseweb="tag"] {{
    background: #E8F0FE !important; color: {ACCENT} !important;
    border-radius: 4px !important; font-size: .7rem !important;
}}

/* Page header */
.page-header {{
    background: linear-gradient(120deg, {ACCENT} 0%, {PURPLE} 100%);
    border-radius: 14px; padding: 1.3rem 1.8rem;
    margin-bottom: 1.2rem;
    box-shadow: 0 6px 24px rgba(26,115,232,.22);
}}
.page-header h1 {{
    font-family: 'Space Mono', monospace !important;
    font-size: 1.4rem; font-weight: 700; color: #fff !important;
    margin: 0; letter-spacing: -.3px;
    -webkit-text-fill-color: #fff !important;
}}
.page-header .sub {{
    font-size: .72rem; color: rgba(255,255,255,.78);
    letter-spacing: 2px; text-transform: uppercase; margin-top: 4px;
}}

/* Summary KPI cards */
.kpi-row {{ display: flex; gap: .8rem; margin-bottom: 1.2rem; flex-wrap: wrap; }}
.kpi-card {{
    flex: 1; min-width: 130px;
    background: {BG_CARD};
    border: 1.5px solid {BORDER};
    border-radius: 12px; padding: .9rem 1.1rem;
    box-shadow: {SHADOW}; position: relative; overflow: hidden;
}}
.kpi-card::after {{
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
}}
.kpi-card.blue::after  {{ background: {ACCENT}; }}
.kpi-card.red::after   {{ background: {RED}; }}
.kpi-card.green::after {{ background: {GREEN}; }}
.kpi-card.amber::after {{ background: {AMBER}; }}
.kpi-card.purple::after{{ background: {PURPLE}; }}
.kpi-label {{ font-size: .62rem; font-weight: 700; color: {MUTED}; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: .35rem; }}
.kpi-value {{ font-family: 'Space Mono', monospace; font-size: 1.6rem; font-weight: 700; color: {FONT}; line-height: 1; }}
.kpi-sub   {{ font-size: .68rem; color: {MUTED}; margin-top: .2rem; }}

/* Section label */
.sec-label {{
    font-size: .63rem; font-weight: 700; letter-spacing: 2.5px;
    text-transform: uppercase; color: {MUTED};
    border-left: 3px solid {ACCENT}; padding-left: .55rem; margin-bottom: .75rem;
}}

/* Resin section card */
.resin-card {{
    background: {BG_CARD};
    border: 1.5px solid {BORDER};
    border-radius: 14px; padding: 1.1rem 1.4rem 1.2rem;
    box-shadow: {SHADOW}; margin-bottom: 1.4rem;
}}
.resin-title {{
    font-family: 'Space Mono', monospace;
    font-size: 1rem; font-weight: 700; color: {FONT};
    display: flex; align-items: center; gap: .5rem;
    margin-bottom: .2rem;
}}
.resin-meta {{ font-size: .72rem; color: {MUTED}; margin-bottom: .9rem; }}
.resin-badge {{
    display: inline-block;
    padding: .18rem .6rem; border-radius: 20px;
    font-size: .62rem; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
}}

/* Insight pill */
.insight-pill {{
    display: inline-flex; align-items: center; gap: .35rem;
    background: #F0F7FF; border: 1px solid #BBDEFB;
    border-radius: 20px; padding: .2rem .7rem;
    font-size: .7rem; color: {ACCENT}; font-weight: 500;
    margin-right: .4rem; margin-bottom: .3rem;
}}

/* Divider */
.divider {{ border: none; border-top: 1.5px solid {BORDER}; margin: 1rem 0; }}

::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-track {{ background: {BG_PAGE}; }}
::-webkit-scrollbar-thumb {{ background: #C5CCD8; border-radius: 4px; }}
</style>
""", unsafe_allow_html=True)

# ── Plotly base layout ────────────────────────────────────────────────────────
def base_layout(**kwargs):
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=BG_CARD,
        font=dict(family="Inter, sans-serif", color=FONT, size=12),
        xaxis=dict(gridcolor=GRID, linecolor=BORDER, tickcolor=MUTED,
                   showgrid=False, zeroline=False),
        yaxis=dict(gridcolor=GRID, linecolor=BORDER, tickcolor=MUTED,
                   showgrid=True, zeroline=True, zerolinecolor=BORDER, zerolinewidth=1.5),
        legend=dict(bgcolor="rgba(255,255,255,.9)", bordercolor=BORDER, borderwidth=1,
                    font=dict(size=11, color=FONT)),
        margin=dict(l=50, r=20, t=50, b=50),
        hoverlabel=dict(bgcolor=BG_CARD, bordercolor=BORDER,
                        font=dict(color=FONT, size=12)),
    )
    layout.update(kwargs)
    return layout

# ── Load data ─────────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = load_and_process(None)
    st.session_state.is_demo = True

df_base = st.session_state.get("df_filtered", st.session_state.df)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:.8rem 0 .5rem; text-align:center;'>
        <div style='font-family:Space Mono,monospace; font-size:1.1rem;
                    background:linear-gradient(135deg,#1A73E8,#6C3FD6);
                    -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-weight:700;'>
            🎨 PaintIQ
        </div>
        <div style='font-size:.58rem; color:#5F6878; letter-spacing:2px; text-transform:uppercase; margin-top:2px;'>
            Quality Intelligence
        </div>
    </div>""", unsafe_allow_html=True)
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload Excel / CSV", type=["xlsx","xls","csv"], label_visibility="collapsed")
    if uploaded:
        try:
            st.session_state.df = load_and_process(uploaded)
            st.session_state.is_demo = False
        except Exception as e:
            st.error(str(e))

    df_all = st.session_state.df
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:.63rem; font-weight:700; color:#5F6878; text-transform:uppercase; letter-spacing:2px; margin-bottom:.5rem;'>🔍 Filters</div>", unsafe_allow_html=True)

    all_vendors  = sorted(df_all["Supplier"].dropna().unique().tolist())
    sel_vendors  = st.multiselect("Supplier / Vendor", all_vendors, placeholder="All suppliers")

    all_resins   = sorted(df_all["Resin_Type"].dropna().unique().tolist())
    sel_resins   = st.multiselect("Resin Type", all_resins, placeholder="All resin types")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:.63rem; font-weight:700; color:#5F6878; text-transform:uppercase; letter-spacing:2px; margin-bottom:.5rem;'>⚙️ Chart Options</div>", unsafe_allow_html=True)
    chart_type  = st.radio("Chart style", ["Bar + Error", "Dot Plot", "Grouped Bar"], label_visibility="collapsed")
    sort_order  = st.radio("Sort bars by", ["Sensitivity ↓", "Sensitivity ↑", "Alphabetical"], label_visibility="collapsed")
    show_table  = st.checkbox("Show data table", value=False)
    min_samples = st.slider("Min samples per group", 1, 20, 3)

    # Apply filters
    df = df_all.copy()
    if sel_vendors: df = df[df["Supplier"].isin(sel_vendors)]
    if sel_resins:  df = df[df["Resin_Type"].isin(sel_resins)]

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:.68rem; color:#5F6878;'>Showing <b style='color:{ACCENT}'>{len(df):,}</b> / {len(df_all):,} rows</div>", unsafe_allow_html=True)

# ── Page header ───────────────────────────────────────────────────────────────
demo_tag = " · <span style='background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.4);color:#fff;font-size:.58rem;letter-spacing:2px;text-transform:uppercase;padding:.1rem .5rem;border-radius:20px;margin-left:.4rem;'>DEMO</span>" if st.session_state.is_demo else ""
st.markdown(f"""
<div class='page-header'>
    <h1>🔬 Viscosity Reduction per Resin{demo_tag}</h1>
    <div class='sub'>Sensitivity = Δ viscosity / 1% solvent added · grouped by Resin Type</div>
</div>
""", unsafe_allow_html=True)

if len(df) == 0:
    st.warning("No data matches the current filters.")
    st.stop()

# ── Derive Viscosity_Sensitivity & Solvent_Type if needed ─────────────────────
df = df.copy()
if "Viscosity_Sensitivity" not in df.columns:
    # sec drop per kg solvent (proxy for sensitivity)
    df["Viscosity_Sensitivity"] = df["Reduction"] / df["Solvent_Weight"].replace(0, np.nan)

if "Solvent_Type" not in df.columns:
    # Use Supplier as a proxy for solvent type if not present
    df["Solvent_Type"] = df["Supplier"]

# ── Aggregate ─────────────────────────────────────────────────────────────────
summary = (
    df.groupby(["Resin_Type", "Solvent_Type"])["Viscosity_Sensitivity"]
      .agg(mean="mean", std="std", count="count", median="median")
      .reset_index()
      .dropna(subset=["mean"])
)
summary = summary[summary["count"] >= min_samples]
summary["std"] = summary["std"].fillna(0)

resins = sorted(summary["Resin_Type"].unique())

if len(resins) == 0:
    st.warning("Not enough data after filtering. Try lowering the minimum samples threshold.")
    st.stop()

# ── Global KPI summary row ────────────────────────────────────────────────────
overall_mean = summary["mean"].mean()
best_resin   = summary.loc[summary["mean"].idxmax(), "Resin_Type"] if len(summary) > 0 else "-"
best_solvent = summary.loc[summary["mean"].idxmax(), "Solvent_Type"] if len(summary) > 0 else "-"
most_stable  = summary.loc[summary["std"].idxmin(), "Resin_Type"] if len(summary) > 0 else "-"
total_combos = len(summary)

st.markdown(f"""
<div class='kpi-row'>
    <div class='kpi-card blue'>
        <div class='kpi-label'>Resin Types</div>
        <div class='kpi-value'>{len(resins)}</div>
        <div class='kpi-sub'>in current view</div>
    </div>
    <div class='kpi-card amber'>
        <div class='kpi-label'>Solvent × Resin Combos</div>
        <div class='kpi-value'>{total_combos}</div>
        <div class='kpi-sub'>with ≥ {min_samples} samples</div>
    </div>
    <div class='kpi-card red'>
        <div class='kpi-label'>Avg Sensitivity</div>
        <div class='kpi-value'>{overall_mean:.1f}</div>
        <div class='kpi-sub'>sec / kg solvent</div>
    </div>
    <div class='kpi-card green'>
        <div class='kpi-label'>Most Sensitive Resin</div>
        <div class='kpi-value' style='font-size:1.1rem; padding-top:.15rem;'>{best_resin}</div>
        <div class='kpi-sub'>highest avg drop</div>
    </div>
    <div class='kpi-card purple'>
        <div class='kpi-label'>Most Stable Resin</div>
        <div class='kpi-value' style='font-size:1.1rem; padding-top:.15rem;'>{most_stable}</div>
        <div class='kpi-sub'>lowest variability</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Overview: All-Resin heatmap ───────────────────────────────────────────────
st.markdown("<div class='sec-label'>Overview — Sensitivity Heatmap (Resin × Solvent)</div>", unsafe_allow_html=True)

pivot = summary.pivot(index="Resin_Type", columns="Solvent_Type", values="mean").round(2)
if not pivot.empty:
    fig_heat = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=[
            [0.0,  "#EAF4FB"],
            [0.25, "#90CAF9"],
            [0.5,  "#1A73E8"],
            [0.75, "#C62828"],
            [1.0,  "#7B0000"],
        ],
        text=[[f"{v:.1f}" if not np.isnan(v) else "" for v in row] for row in pivot.values],
        texttemplate="%{text}",
        textfont=dict(size=11, color="#ffffff"),
        hoverongaps=False,
        colorbar=dict(
            title=dict(text="sec/kg", font=dict(size=11, color=MUTED), side="right"),
            tickfont=dict(size=10, color=MUTED),
            len=0.8, thickness=12,
            outlinewidth=0,
        ),
        xgap=2, ygap=2,
    ))
    fig_heat.update_layout(
        **base_layout(height=max(220, len(pivot) * 42 + 80),
                      margin=dict(l=90, r=20, t=30, b=60)),
        xaxis=dict(side="bottom", tickangle=-30, tickfont=dict(size=11),
                   showgrid=False, linecolor=BORDER),
        yaxis=dict(tickfont=dict(size=11), showgrid=False, linecolor=BORDER),
    )
    st.plotly_chart(fig_heat, use_container_width=True, config={"displayModeBar": False})

st.markdown("<hr class='divider'>", unsafe_allow_html=True)

# ── Per-resin detail charts ───────────────────────────────────────────────────
st.markdown("<div class='sec-label'>Detailed View — One Chart per Resin Type</div>", unsafe_allow_html=True)

# Layout: 2 columns for resin cards when many resins
use_cols = len(resins) > 3
if use_cols:
    col_pairs = st.columns(2)

def sort_df(sub):
    if sort_order == "Sensitivity ↓":
        return sub.sort_values("mean", ascending=False)
    elif sort_order == "Sensitivity ↑":
        return sub.sort_values("mean", ascending=True)
    return sub.sort_values("Solvent_Type")

for i, resin in enumerate(resins):
    sub = sort_df(summary[summary["Resin_Type"] == resin].copy())
    if sub.empty:
        continue

    resin_color = RESIN_COLORS.get(resin, QUAL_PALETTE[i % len(QUAL_PALETTE)])
    n_solvents  = len(sub)
    top_solvent = sub.iloc[0]["Solvent_Type"]
    top_mean    = sub.iloc[0]["mean"]
    avg_std     = sub["std"].mean()
    stability   = "High" if avg_std < 2 else "Medium" if avg_std < 5 else "Low"
    stab_color  = GREEN if stability == "High" else AMBER if stability == "Medium" else RED

    # ── Build chart ──
    solvents = sub["Solvent_Type"].tolist()
    means    = sub["mean"].tolist()
    stds     = sub["std"].tolist()
    counts   = sub["count"].tolist()

    # Assign a distinct color to each solvent bar
    bar_colors = [QUAL_PALETTE[j % len(QUAL_PALETTE)] for j in range(len(solvents))]

    if chart_type == "Bar + Error":
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=solvents, y=means,
            error_y=dict(type="data", array=stds, visible=True,
                         color="#888", thickness=1.8, width=5),
            marker=dict(
                color=bar_colors,
                line=dict(color="white", width=1.5),
            ),
            text=[f"{m:.1f}" for m in means],
            textposition="outside",
            textfont=dict(size=10, color=FONT, family="Space Mono, monospace"),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Mean: <b>%{y:.2f}</b> sec/kg<br>"
                "Std: %{error_y.array:.2f}<br>"
                "<extra></extra>"
            ),
            showlegend=False,
        ))
        # Add a subtle mean reference line
        grand_mean = np.mean(means)
        fig.add_hline(
            y=grand_mean,
            line_dash="dot", line_color="#AAAAAA", line_width=1.5,
            annotation_text=f"avg {grand_mean:.1f}",
            annotation_font=dict(size=9, color=MUTED),
            annotation_position="top right",
        )
        fig.update_layout(
            **base_layout(height=340),
            title=dict(text="", font=dict(size=12, color=MUTED)),
            yaxis_title="Avg Sensitivity (sec / kg solvent)",
            xaxis_title="",
            bargap=0.35,
        )

    elif chart_type == "Dot Plot":
        fig = go.Figure()
        # Error bar lines (connect to dot)
        for j, (s, m, sd, c) in enumerate(zip(solvents, means, stds, bar_colors)):
            fig.add_shape(type="line",
                x0=j, x1=j, y0=m - sd, y1=m + sd,
                line=dict(color=c, width=2.5))
        # Dots
        fig.add_trace(go.Scatter(
            x=solvents, y=means,
            mode="markers+text",
            marker=dict(size=16, color=bar_colors,
                        line=dict(color="white", width=2.5),
                        symbol="circle"),
            text=[f"{m:.1f}" for m in means],
            textposition="top center",
            textfont=dict(size=10, color=FONT, family="Space Mono, monospace"),
            hovertemplate="<b>%{x}</b><br>Mean: <b>%{y:.2f}</b><extra></extra>",
            showlegend=False,
        ))
        fig.add_hline(y=np.mean(means), line_dash="dot", line_color="#BBBBBB",
                      line_width=1.5)
        fig.update_layout(
            **base_layout(height=340),
            yaxis_title="Avg Sensitivity (sec / kg solvent)",
            xaxis_title="",
        )

    else:  # Grouped Bar (mean vs median)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Mean", x=solvents, y=means,
            marker=dict(color=ACCENT, opacity=.85, line=dict(color="white", width=1.5)),
            error_y=dict(type="data", array=stds, visible=True,
                         color="#888", thickness=1.5, width=4),
            text=[f"{m:.1f}" for m in means], textposition="outside",
            textfont=dict(size=10, color=FONT),
        ))
        fig.add_trace(go.Bar(
            name="Median", x=solvents, y=sub["median"].tolist(),
            marker=dict(color=AMBER, opacity=.75, line=dict(color="white", width=1.5)),
            text=[f"{m:.1f}" for m in sub["median"].tolist()],
            textposition="outside", textfont=dict(size=10, color=FONT),
        ))
        fig.update_layout(
            **base_layout(height=340),
            barmode="group", bargap=0.25, bargroupgap=0.08,
            yaxis_title="Sensitivity (sec / kg solvent)", xaxis_title="",
        )

    # ── Card wrapper via columns ──
    target_col = col_pairs[i % 2] if use_cols else st

    with target_col:
        badge_bg = hex_to_rgba(resin_color, 0.12)
        st.markdown(f"""
        <div class='resin-card'>
            <div class='resin-title'>
                <span style='width:10px; height:10px; border-radius:50%;
                             background:{resin_color}; display:inline-block; flex-shrink:0;'></span>
                {resin}
                <span class='resin-badge' style='background:{badge_bg}; color:{resin_color};
                             border:1px solid {resin_color}40;'>{n_solvents} solvents</span>
            </div>
            <div class='resin-meta'>
                Top performer: <b style='color:{ACCENT}'>{top_solvent}</b>
                &nbsp;·&nbsp; Mean {top_mean:.1f} sec/kg
                &nbsp;·&nbsp; Stability:
                <b style='color:{stab_color}'>{stability}</b>
                &nbsp;·&nbsp; Avg Std: {avg_std:.2f}
            </div>
        """, unsafe_allow_html=True)

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Insight pills
        if len(sub) >= 2:
            best  = sub.iloc[0]
            worst = sub.iloc[-1]
            diff  = best["mean"] - worst["mean"]
            st.markdown(f"""
            <div style='margin-top:-.3rem; margin-bottom:.2rem;'>
                <span class='insight-pill'>⬆ Best: <b>{best["Solvent_Type"]}</b> ({best["mean"]:.1f})</span>
                <span class='insight-pill' style='background:#FFF8E1; border-color:#FFE082; color:{AMBER};'>
                    ⬇ Lowest: <b>{worst["Solvent_Type"]}</b> ({worst["mean"]:.1f})</span>
                <span class='insight-pill' style='background:#F3E5F5; border-color:#CE93D8; color:{PURPLE};'>
                    Δ spread: {diff:.1f} sec/kg</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Optional table
        if show_table:
            disp = sub[["Solvent_Type","mean","std","median","count"]].copy()
            disp.columns = ["Solvent Type","Mean (sec/kg)","Std Dev","Median","n"]
            disp = disp.round(2)
            st.dataframe(disp, use_container_width=True, hide_index=True,
                         column_config={
                             "Mean (sec/kg)": st.column_config.ProgressColumn(
                                 "Mean (sec/kg)", min_value=0,
                                 max_value=float(disp["Mean (sec/kg)"].max()) * 1.1,
                                 format="%.2f"),
                         })

# ── Cross-resin ranking bar ───────────────────────────────────────────────────
st.markdown("<hr class='divider'>", unsafe_allow_html=True)
st.markdown("<div class='sec-label'>Cross-Resin Ranking — Best Solvent per Resin</div>", unsafe_allow_html=True)

best_per_resin = (summary.sort_values("mean", ascending=False)
                         .groupby("Resin_Type").first().reset_index()
                         .sort_values("mean", ascending=True))

if not best_per_resin.empty:
    colors_bar = [RESIN_COLORS.get(r, QUAL_PALETTE[j % len(QUAL_PALETTE)])
                  for j, r in enumerate(best_per_resin["Resin_Type"])]
    fig_rank = go.Figure()
    fig_rank.add_trace(go.Bar(
        y=best_per_resin["Resin_Type"],
        x=best_per_resin["mean"],
        orientation="h",
        marker=dict(color=colors_bar, line=dict(color="white", width=1.5)),
        error_x=dict(type="data", array=best_per_resin["std"].tolist(),
                     visible=True, color="#AAAAAA", thickness=1.5, width=4),
        text=[f"{v:.1f}  ({s})" for v, s in
              zip(best_per_resin["mean"], best_per_resin["Solvent_Type"])],
        textposition="outside",
        textfont=dict(size=10, color=FONT),
        hovertemplate="<b>%{y}</b><br>Best solvent: %{text}<extra></extra>",
        showlegend=False,
    ))
    fig_rank.update_layout(
        **base_layout(height=max(280, len(best_per_resin) * 38 + 80),
                      margin=dict(l=70, r=160, t=35, b=40)),
        xaxis_title="Best Sensitivity (sec / kg solvent)",
        xaxis=dict(showgrid=True, gridcolor=GRID, zeroline=True,
                   zerolinecolor=BORDER, linecolor=BORDER),
        yaxis=dict(showgrid=False, linecolor=BORDER, tickfont=dict(size=11)),
        title=dict(text="Top sensitivity score & winning solvent per resin",
                   font=dict(size=12, color=MUTED)),
    )
    st.plotly_chart(fig_rank, use_container_width=True, config={"displayModeBar": False})

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<hr class='divider'>
<div style='text-align:center; color:#A0A8B5; font-size:.62rem;
            padding:.4rem 0 1rem; font-family:Space Mono,monospace; letter-spacing:1.5px;'>
    PAINT QUALITY INTELLIGENCE v1.0 &nbsp;·&nbsp; PAGE 4
</div>
""", unsafe_allow_html=True)
