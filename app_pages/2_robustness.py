"""Page 2 - Is it robust? Specification suite, placebo, leave-one-out and known-answer validation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from oews_dashboard import data_access as da
from oews_dashboard import ui
from oews_model.analysis import PRACTICAL_THRESHOLD
from oews_model.plots import plot_leave_one_out, plot_spec_forest

outcome, inference = ui.choices()
results = ui.require_results()
noun = da.OUTCOME_NOUN[outcome]

st.title("Is the result robust?")
st.markdown(f"Does the **{noun}** estimate survive different timing, samples, controls and a placebo, and is it "
            "driven by any single industry or occupation? Change the outcome or uncertainty method in the sidebar.")
ui.provenance_banner(results)

summ = da.robustness_summary(results, outcome, inference)
main = da.headline(results, outcome, inference)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Main estimate per 1 SD", ui.fmt_pct(main["pct"]), border=True)
k1.caption(f"95% CI {ui.fmt_pct(main['pct_low'])} to {ui.fmt_pct(main['pct_high'])}")
k2.metric("Alternatives with the same sign", f"{summ['same_sign']} of {summ['n_alt']}", border=True,
          help="Comparison and robustness specifications (placebo excluded).")
k2.caption(f"Range {ui.fmt_pct(summ['range_pct'][0])} to {ui.fmt_pct(summ['range_pct'][1])}")
k3.metric("Clear the 1-point practical bar", f"{summ['meaningful']} of {summ['n_alt']}", border=True,
          help=f"Whole 95% interval beyond +/-{PRACTICAL_THRESHOLD * 100:.0f} log point per 1 SD.")
k3.caption("Pooled OLS without fixed effects is the usual exception: it is the noisy baseline.")
k4.metric("Placebo (fake post in 2022)", ui.fmt_pct(summ["placebo_pct"]), border=True,
          help="Pretends ChatGPT arrived a year early using only 2021-2022. Should be about zero.")
k4.caption(f"{ui.fmt_p(summ['placebo_p'])} - " + ("near zero, as it should be" if summ["placebo_p"] > 0.10
                                                     else "**not near zero - investigate**"))

# ---------------------------------------------------------------- specification suite
st.subheader(f"The exposure x post coefficient across specifications ({noun})")
left, right = st.columns([1, 1])
with left:
    fig = plot_spec_forest(results.specs[outcome], PRACTICAL_THRESHOLD, source_mode=results.source_mode)
    fig.axes[0].set_title(f"Exposure x post coefficient across specifications (log {noun})", pad=12)
    ui.show_figure(fig)
with right:
    tab = da.robustness_table(results, outcome, inference)
    pct_fmt = st.column_config.NumberColumn(format="%+.2f%%")
    st.dataframe(tab, hide_index=True, column_config={
        "Effect per 1 SD (%)": pct_fmt, "95% CI low (%)": pct_fmt, "95% CI high (%)": pct_fmt,
        "p-value": st.column_config.NumberColumn(format="%.4f"),
        "Rows": st.column_config.NumberColumn(format="%d")})
    st.caption(f"Table intervals and p-values: {ui.inference_name(inference)} (two-sided). Figure shows both "
               "methods: solid = CR1, dashed = wild bootstrap. Percent = exp(coefficient) - 1.")

# ---------------------------------------------------------------- leave one out
st.subheader("Is one industry or occupation driving it? (employment)")
if outcome != "emp":
    st.caption("Leave-one-out was run for the primary employment outcome only; showing employment here.")
panel = ui.get_panel()
labels = da.code_labels(panel)
dims = {"Drop one industry": "naics_code", "Drop one occupation": "soc_code"}
c1, c2 = st.columns([1, 2])
with c1:
    dim_label = st.radio("Remove", list(dims), horizontal=True)
    by = dims[dim_label]
    view = da.leave_one_out_view(results, by, labels[by])
    if view.empty:
        st.warning("No leave-one-out results are saved for this dimension. Re-run "
                   f"`{da.BUILD_MODEL_CMD}` to regenerate them.")
        st.stop()
    choice = st.selectbox("Which one", view["Dropped"].tolist(), index=0,
                          help="Sorted from the most negative estimate to the least negative.")
    row = view.loc[view["Dropped"] == choice]
    if row.empty:          # stale selection after switching dimension
        row = view.iloc[[0]]
    row = row.iloc[0]
    full = da.headline(results, "emp", "cr1")
    st.metric(f"Estimate without {row['Dropped'][:40]}", ui.fmt_pct(row["Effect per 1 SD (%)"]),
              delta=f"{row['Effect per 1 SD (%)'] - full['pct']:+.2f} pts vs full sample", delta_color="off",
              border=True)
    st.caption(f"95% CI {ui.fmt_pct(row['95% CI low (%)'])} to {ui.fmt_pct(row['95% CI high (%)'])} (CR1) - "
               f"{int(row['Rows'])} rows")
    lo, hi = view["Effect per 1 SD (%)"].min(), view["Effect per 1 SD (%)"].max()
    all_below = bool((view["95% CI high (%)"] < 0).all())
    st.markdown(f"Across all {len(view)} removals the estimate stays between **{ui.fmt_pct(lo)}** and "
                f"**{ui.fmt_pct(hi)}** (full sample {ui.fmt_pct(full['pct'])}). "
                + ("Every interval stays below zero: no single "
                   f"{'industry' if by == 'naics_code' else 'occupation'} drives the result."
                   if all_below else "At least one interval reaches zero: inspect that case."))
with c2:
    fig = plot_leave_one_out(results.loo, results.specs["emp"].set_index("spec").loc["main", "coef"],
                             source_mode=results.source_mode)
    ui.show_figure(fig)

# ---------------------------------------------------------------- method validation
st.subheader("Does the method recover a known answer?")
val = results.summary.get("validation", {})
checks = {"Model recovers the planted effect (noise-free, pinned tolerance)": val.get("model_recovery_pass"),
          "EDA code recovers the planted effect": val.get("eda_code_pass"),
          "Sampling bands over many synthetic seeds": val.get("eda_sampling_pass")}
st.dataframe(
    {"Check (Assignment 6 known-answer validation)": list(checks),
     "Result": ["Pass" if v else ("Fail" if v is False else "Not run") for v in checks.values()]},
    hide_index=True)
st.caption("The synthetic generator plants a known employment effect and no wage effect. Recovering both is "
           "evidence the code is correct; it says nothing about the real labor market. Details: "
           "docs/A6_EVALUATION_REPORT.md.")
ui.limitations_note()
