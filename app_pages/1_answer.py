"""Page 1 - The answer: research question, headline KPIs, bottom line and timing of the gap."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from oews_dashboard import data_access as da
from oews_dashboard import ui
from oews_eda.data import OEWS_VINTAGE
from oews_model.plots import plot_event_study

outcome, inference = ui.choices()
results = ui.require_results()

st.title("Did jobs more exposed to generative AI grow more slowly after ChatGPT?")
st.markdown(
    "**Question.** After ChatGPT's release in late 2022, did U.S. occupations whose tasks are more exposed to "
    "generative AI see different employment and wage changes than less-exposed occupations **in the same "
    "industry**? Focus: financial analysts and neighboring finance occupations.")
prov = ui.provenance_banner(results)

emp = da.headline(results, "emp", inference)
wage = da.headline(results, "wage", inference)
pre = da.pretrend(results, "emp")
panel_info = results.summary.get("panel", {})

# ---------------------------------------------------------------- KPIs (above the fold)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Employment gap per 1 SD more exposure", ui.fmt_pct(emp["pct"]), border=True,
          help="Primary estimate (A3 model: cell + industry-by-year fixed effects). Percent difference in "
               "post-2022 employment per 1 standard deviation of GenAI exposure.")
k1.caption(f"95% CI {ui.fmt_pct(emp['pct_low'])} to {ui.fmt_pct(emp['pct_high'])} - "
           f"one-sided {ui.fmt_p(emp['p_one_sided'])} - **{emp['verdict']}**")
k2.metric("Wage gap per 1 SD more exposure", ui.fmt_pct(wage["pct"]), border=True,
          help="Same model for log mean annual wage. Two-sided test (no direction predicted).")
k2.caption(f"95% CI {ui.fmt_pct(wage['pct_low'])} to {ui.fmt_pct(wage['pct_high'])} - "
           f"{ui.fmt_p(wage['p'])} - **{wage['verdict']}**")
k3.metric("Pre-trend check (2021 vs 2022)", ui.fmt_pct(pre["pct"]), border=True,
          help="Event-study coefficient one year before ChatGPT. Near zero means high- and low-exposure "
               "occupations were moving together before the release, which the comparison relies on.")
k3.caption(f"95% CI {ui.fmt_pct(pre.get('pct_low'))} to {ui.fmt_pct(pre.get('pct_high'))} - "
           + ("**passes: CI includes 0**" if pre["pass"] else "**fails: CI excludes 0**"))
k4.metric("Sample", f"{emp['n_clusters']} occupations", border=True,
          help="Unit = detailed occupation x 4-digit industry x May reference year (OEWS).")
k4.caption(f"{emp['n_cells']} occupation-industry cells - {emp['n_obs']} cell-years - May 2021-2025")

# ---------------------------------------------------------------- bottom line
h = emp if outcome == "emp" else wage
st.subheader("Bottom line")
supports = emp["verdict"] == "practically meaningful" and emp["ci_high"] < 0
st.info(
    f"**Employment:** {da.interpret(emp, results)}\n\n"
    f"**Wages:** {da.interpret(wage, results)}\n\n"
    f"**Hypothesis H1 (employment, beta < 0):** "
    + ("supported in this sample." if supports else "not supported in this sample.")
    + " **H2 (wages, two-sided):** "
    + ("no detectable change." if wage["verdict"].startswith(("negligible", "inconclusive")) else
       "a detectable change.")
    + f" Uncertainty: {ui.inference_name(inference)}, {emp['n_clusters']} occupation clusters.",
    icon=":material/lightbulb:")

iqr = da.iqr_effect(results, h)
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown(
        f"**What it means for planning.** Moving from a typical low-exposure occupation (25th percentile) to a "
        f"typical high-exposure one (75th percentile) corresponds to about **{ui.fmt_pct(iqr)}** in "
        f"{da.OUTCOME_NOUN[h['outcome']]} relative to same-industry peers. Treat exposure as an early-warning "
        "signal for workforce planning in finance roles, not as a forecast for any single job.")
with c2:
    st.markdown(
        "**What it does not show.** That GenAI *caused* the gap; observed AI adoption (exposure is technical "
        "potential); hiring or layoffs (OEWS measures employment stocks); effects for any individual worker.")

# ---------------------------------------------------------------- timing
st.subheader(f"When did the {da.OUTCOME_NOUN[outcome]} gap open? Exposure gap by year, 2022 = 0")
es = results.event[outcome]
fig = plot_event_study(es, source_mode=results.source_mode,
                       outcome_label="employment" if outcome == "emp" else "mean annual wage")
left, right = st.columns([3, 2])
with left:
    ui.show_figure(fig)
with right:
    tab = da.event_table(results, outcome, inference)
    share = OEWS_VINTAGE["post_panel_share"]
    tab["Post-ChatGPT share of OEWS survey panels"] = [f"{share.get(int(y), float('nan')):.0%}"
                                                      for y in tab["May reference year"]]
    st.dataframe(tab, hide_index=True, column_config={
        "Gap per 1 SD vs 2022 (%)": st.column_config.NumberColumn(format="%+.2f%%"),
        "95% CI low (%)": st.column_config.NumberColumn(format="%+.2f%%"),
        "95% CI high (%)": st.column_config.NumberColumn(format="%+.2f%%"),
    })
    st.caption(
        f"Intervals in the table: {ui.inference_name(inference)}. Each May OEWS estimate pools six semiannual "
        "survey panels collected over three years, so May 2023 reflects only one post-ChatGPT panel. A gap that "
        "grows through 2024-2025 is what gradual pooling would produce; a 2021 coefficient near zero supports "
        "parallel pre-trends.")

with st.expander("How the estimate is built (method in one paragraph)"):
    st.markdown(
        "log(Y) for each occupation x industry x year is regressed on occupation exposure x post-2022, with "
        "**occupation-by-industry fixed effects** (each cell is compared with itself) and **industry-by-year "
        "fixed effects** (industry-wide shocks such as interest-rate cycles are removed). Exposure is the "
        "Eloundou et al. (2024) share of an occupation's tasks that GenAI could speed up, standardized to "
        f"1 SD (about {panel_info.get('sd_exposure_share', float('nan')) * 100:.0f} percentage points of tasks). "
        "Standard errors are clustered by occupation; because there are only "
        f"{emp['n_clusters']} clusters, the wild cluster restricted bootstrap (B = "
        f"{results.summary.get('inference_draws', {}).get('wild_bootstrap_B', 'n/a')}) and randomization "
        f"inference (randomization {ui.fmt_p(emp['p_ri'])}) back up the conventional t-test. "
        "Source: Assignment 6 artifacts in reports/model/ - nothing is re-estimated in this app.")
ui.limitations_note()
