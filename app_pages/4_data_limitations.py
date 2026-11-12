"""Page 4 - Data & limitations: what the evidence cannot show, provenance, sample construction, recovery."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import streamlit as st

from oews_dashboard import data_access as da
from oews_dashboard import ui
from oews_eda.data import oews_vintage, panel_definition

results = ui.require_results()
st.title("Data, provenance and limitations")
prov = ui.provenance_banner(results)

# ---------------------------------------------------------------- limitations first
st.subheader("Limitations: read these before using the numbers")
st.markdown(f"""
1. **{'Synthetic sample.' if prov.is_sample else 'Real-data run.'}** {'The committed results come from a synthetic sample with a planted employment effect and no wage effect. They validate the method; they are not labor-market findings. Real BLS OEWS, Eloundou et al. and O*NET files are licensed or large and are never committed (see docs/DATA_ACCESS.md).' if prov.is_sample else 'Results come from the authorized raw files listed below.'}
2. **Association, not causation.** Industry-by-year fixed effects remove shocks common to an industry, but any post-2022 shock that hit high-exposure occupations differently (tech-sector layoffs, interest-rate effects on analyst roles) is not separated from GenAI.
3. **Exposure is potential, not adoption.** Eloundou et al. (2024) score which tasks GenAI *could* speed up; they do not measure whether employers adopted it. Exposure is fixed at its pre-2023 value.
4. **OEWS pools three years of surveys.** Each May estimate averages six semiannual panels, so May 2023 contains one post-ChatGPT panel and May 2025 five. Early effects are diluted; the dose specification on the robustness page addresses this.
5. **Few clusters.** Exposure varies by occupation only, so there are {results.summary.get('panel', {}).get('n_occupations', 'n/a')} independent clusters. Wild cluster bootstrap and randomization inference are used because the conventional cluster-robust t can be too optimistic with this few.
6. **Suppression and coverage.** OEWS suppresses small or unreliable cells; suppressed values are left missing, never imputed. The balanced-cells check shows results do not depend on which cells drop out.
7. **What the outcomes measure.** Employment is a stock (not hires or separations); the wage is the mean for incumbents, so composition changes can move it.
8. **Analyst vs. clerk is descriptive.** One occupation per role means no valid standard error; it illustrates, it does not test.
""")

# ---------------------------------------------------------------- provenance
st.subheader("Provenance: can these numbers be reproduced?")
c1, c2, c3 = st.columns(3)
c1.metric("Model results", ui.fmt_time(prov.model_generated_at), border=True)
c1.caption(f"`{da.BUILD_MODEL_CMD}` at commit {prov.code_commit}, {prov.source_mode} mode")
c2.metric("Your database", ui.fmt_time(prov.etl_finished_at) if prov.etl_finished_at else "Not built",
          border=True)
c2.caption(f"`{da.BUILD_DB_CMD}`" + (f", {prov.db_source_mode} mode" if prov.db_source_mode else ""))
status = ("Verified" if prov.verified else "Not verified (no database)" if prov.inputs_match is None
          else "Mismatch")
c3.metric("Checksum verification", status, border=True)
c3.caption("Database input files vs. model run log, and result files vs. their recorded SHA-256.")

panel = ui.get_panel()
if panel is None:
    st.warning(f"The database is not built, so sample construction and input checksums cannot be shown. "
               f"Run `{da.BUILD_DB_CMD}`, or use the button below.")
    ui.build_sample_button()
else:
    inputs = pd.DataFrame(results.run_log.get("inputs", []))
    if not inputs.empty:
        found = da.input_manifest().set_index("source_name")["sha256"]
        inputs["Matches your database"] = [found.get(s) == h for s, h in zip(inputs["source_name"], inputs["sha256"])]
        inputs["sha256"] = inputs["sha256"].str[:12] + "..."
        st.dataframe(inputs[["source_name", "file_name", "version", "rows_read", "sha256", "Matches your database"]]
                     .rename(columns={"source_name": "Source", "file_name": "File", "version": "Version",
                                      "rows_read": "Rows read", "sha256": "SHA-256"}), hide_index=True)

    # ------------------------------------------------------------ sample construction
    st.subheader("Sample construction: from source rows to the analysis sample")
    left, right = st.columns([1, 1])
    with left:
        att = da.attrition(panel)
        st.dataframe(att.rename(columns={"stage": "Stage", "n": "Count", "unit": "Unit"}), hide_index=True)
        st.caption("Rows that fail validation are quarantined in the database (`rejected_record`), not dropped "
                   "silently. Source: A5 `oews_eda.data.attrition_table`.")
    with right:
        q = da.quality_gate(panel)
        st.markdown(f"**A5 data-quality gate: {'PASSED' if q['passed'] else 'FAILED'}**")
        st.dataframe(pd.DataFrame({"Check": list(q["checks"]),
                                   "Result": ["Pass" if v else "Fail" for v in q["checks"].values()]}),
                     hide_index=True)
        cov = q["coverage"].rename(columns={"year": "Year", "rows": "Rows", "emp_model_ready": "Employment usable",
                                            "wage_model_ready": "Wage usable", "emp_suppressed": "Emp. suppressed",
                                            "wage_suppressed": "Wage suppressed", "wage_topcoded": "Wage top-coded",
                                            "employment_covered": "Employment covered"})
        cov["Year"] = cov["Year"].astype(str)
        st.dataframe(cov, hide_index=True)

st.subheader("What one row is, and where each field comes from")
st.dataframe(panel_definition().rename(columns=str.capitalize), hide_index=True)
st.markdown("**OEWS release facts by May reference year**")
v = oews_vintage().reset_index()
v["post_panel_share"] = (v["post_panel_share"] * 100).round(0).astype(int).astype(str) + "%"
v["year"] = v["year"].astype(str)
st.dataframe(v.rename(columns={"year": "Year", "panels_pooled": "Panels pooled",
                               "post_chatgpt_panels": "Post-ChatGPT panels", "estimation": "Method",
                               "soc": "SOC", "naics": "NAICS", "post_panel_share": "Post share"}),
             hide_index=True)

with st.expander("If something looks wrong (recovery steps)"):
    st.markdown(f"""
| Symptom | Fix |
|---|---|
| "Database not built" | `{da.BUILD_DB_CMD}` (sample) or `uv run oews-pipeline run --source raw` (licensed files) |
| "Model results not found" or "Result files changed" | `{da.BUILD_MODEL_CMD}` (about 3-4 minutes) |
| "Results and database disagree" | You rebuilt the database from different inputs; re-run `{da.BUILD_MODEL_CMD}` |
| Stale numbers after a rebuild | Press **R** in the app or use the menu: Clear cache, then Rerun |
| Port 8501 busy | `uv run streamlit run streamlit_app.py --server.port 8502` |

Full guide: docs/APP_GUIDE.md. Real-data path without committing licensed files: docs/DATA_ACCESS.md.
""")
