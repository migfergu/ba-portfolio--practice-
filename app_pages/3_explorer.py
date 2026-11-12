"""Page 3 - Occupation explorer: filterable descriptive evidence from the A4 database via A5 functions."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from oews_dashboard import data_access as da
from oews_dashboard import ui
from oews_eda.plots import plot_focal_contrast, plot_trend_index

outcome, inference = ui.choices()
results = ui.require_results()
noun = da.OUTCOME_NOUN[outcome]

st.title("Occupation explorer")
st.markdown(f"Which occupations and industries sit behind the result? Filter the **{noun}** evidence by industry and "
            "exposure level. These views are descriptive (raw trends and within-industry changes); the model "
            "estimate on **The answer** page adds industry-by-year controls and formal uncertainty.")
ui.provenance_banner(results)
panel = ui.require_panel()

# ---------------------------------------------------------------- page filters (sidebar)
options = da.industry_options(panel)
terciles = ["High", "Middle", "Low"]
with st.sidebar:
    st.header("Explorer filters")
    picked = st.multiselect("Industries (4-digit NAICS)", list(options), default=list(options),
                            help="Default: all industries in the panel.")
    picked_t = st.multiselect("Exposure tercile", terciles, default=terciles,
                              help="Occupations split into thirds by GenAI exposure.")
    balanced = st.checkbox("Balanced cells only (trend chart)", value=True,
                           help="Keep only occupation-industry cells observed in all five years, so "
                                "suppression churn cannot masquerade as a trend.")

if not picked or not picked_t:
    st.warning("No industries or exposure groups are selected. Choose at least one of each in the sidebar "
               "(**Explorer filters**).")
    st.stop()
sel = da.filter_panel(panel, [options[p] for p in picked if p in options], picked_t)
if sel.empty:
    st.warning("No rows match the current filters. Add industries or exposure groups in the sidebar.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Occupations", f"{sel['soc_code'].nunique()}", border=True)
k2.metric("Industries", f"{sel['naics_code'].nunique()}", border=True)
k3.metric("Occupation-industry cells", f"{sel['cell_id'].nunique()}", border=True)
k4.metric(f"Rows with {noun} reported", f"{sel[da.OUTCOME_COLUMN[outcome]].notna().sum():,}", border=True)

# ---------------------------------------------------------------- trend
st.subheader(f"{noun.capitalize()} trend by exposure tercile (index, May 2022 = 100)")
trend_l = da.trend_long(sel, outcome, balanced=balanced)
if trend_l.empty:
    st.info("Too few cells in this selection to index against 2022. "
            + ("Try unticking **Balanced cells only** or " if balanced else "Try ") + "adding industries.")
else:
    tab_fig, tab_live, tab_data = st.tabs(["Chart", "Interactive (hover for values)", "Data"])
    with tab_fig:
        fig = plot_trend_index(trend_l, outcome_label=noun.capitalize(), source_mode=results.source_mode)
        fig.axes[0].set_title(f"{noun.capitalize()} index by GenAI exposure tercile (May 2022 = 100)", pad=12)
        ui.show_figure(fig)
    wide = da.trend_by_exposure(sel, outcome, balanced=balanced)
    with tab_live:
        st.line_chart(wide, x_label="May reference year", y_label=f"{noun.capitalize()} index (2022 = 100)",
                      height=360)
    with tab_data:
        st.dataframe(wide.reset_index(), hide_index=True)
    st.caption("Geometric-mean index over " + ", ".join(f"{k.split()[0].lower()}: {v} cells"
                                                         for k, v in wide.attrs.get("n_cells", {}).items())
               + ". Groups differ by color, marker and line style, so the chart also reads in grayscale. A "
               "high-exposure line falling behind the low-exposure line after 2022 is the descriptive pattern "
               "the model tests.")

# ---------------------------------------------------------------- occupations
st.subheader(f"Exposure vs. pre-to-post change in {noun}, by occupation")
occ = da.occupation_view(sel, outcome)
if occ.empty:
    st.info("No occupation in this selection has both a pre- and post-2022 observation.")
else:
    y = "Change vs same-industry peers (%)"
    left, right = st.columns([1, 1])
    with left:
        st.scatter_chart(occ, x="GenAI exposure (share of tasks)", y=y, color="Exposure tercile", height=380,
                         x_label="GenAI exposure (share of tasks, 0-1)",
                         y_label=f"{noun.capitalize()} change vs same-industry peers (%)")
        st.caption("Each point is one occupation: mean post-2022 minus mean pre-2023 log outcome, net of the "
                   "industry average change, weighted by pre-period employment. n = occupations, not cells. "
                   "Terciles are also ordered along the x-axis, so the chart reads without color.")
    with right:
        st.dataframe(occ.drop(columns=["SOC"]), hide_index=True, height=380, column_config={
            "GenAI exposure (share of tasks)": st.column_config.ProgressColumn(
                format="%.2f", min_value=0.0, max_value=1.0),
            y: st.column_config.NumberColumn(format="%+.1f%%"),
        })

    st.markdown("**Spot-check one occupation**")
    names = dict(zip(occ["Occupation"], occ["SOC"]))
    default = next((i for i, s in enumerate(occ["SOC"]) if s == "13-2051"), 0)
    pick = st.selectbox("Occupation", list(names), index=default)
    detail = da.occupation_detail(sel, names.get(pick, ""))
    if detail.empty:
        st.info("No rows for this occupation under the current filters.")
    else:
        st.dataframe(detail, hide_index=True, column_config={
            "Employment": st.column_config.NumberColumn(format="%.0f"),
            "Mean annual wage (USD)": st.column_config.NumberColumn(format="$%.0f")})
        st.caption("Blank values are suppressed in OEWS (kept as missing, never imputed).")

# ---------------------------------------------------------------- analyst vs clerk
st.subheader("Financial analysts vs. bookkeeping clerks: employment and wage index (May 2022 = 100)")
focal = da.focal_long(sel)
if focal.empty:
    st.info("Neither focal occupation appears in the selected industries.")
else:
    ui.show_figure(plot_focal_contrast(focal, source_mode=results.source_mode))
    fin = da.finance_view(results, outcome)
    st.dataframe(fin, hide_index=True,
                 column_config={"Post-2022 deviation (%)": st.column_config.NumberColumn(format="%+.2f%%")})
    st.caption("Descriptive only (one occupation per role, so no cluster standard error). Both are highly "
               "exposed; the contrast shows how two finance roles moved, not a causal comparison. Index uses "
               "industry cells observed in every year.")
ui.limitations_note()
