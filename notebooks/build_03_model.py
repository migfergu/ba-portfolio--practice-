"""Builds notebooks/03_model.ipynb (kept as a script so the notebook's structure is reviewable in diffs).

Run:  uv run python notebooks/build_03_model.py   then open and "Run All" in Jupyter (about 3 minutes).
"""
from __future__ import annotations

import json
from pathlib import Path

MD, CODE = "markdown", "code"
CELLS: list[tuple[str, str]] = [
(MD, """# Assignment 6 - Analytics Engine & Modeling
## Generative AI Exposure and Financial Analyst Employment and Wages

**BUS 751 · Miguel L. Ferguson II · Pathway 2 (research-oriented)**

**Research question (A3).** Did U.S. occupations with higher predicted generative-AI task exposure see different employment and wage changes after ChatGPT's late-2022 release, relative to less-exposed occupations in the same industry? **H1:** employment β < 0 (one-sided). **Wages:** two-sided.

**Workflow.** This notebook *imports* `oews_model` (`src/oews_model/`), which reads the A4 database through the A5 loader (`oews_eda.data.load_panel`). It defines no estimation code of its own:
1. Estimand, unit, specification, uncertainty.
2. The A3 model.
3. Comparison with simpler specifications.
4. Event study and pre-period diagnostic.
5. Robustness and sensitivity.
6. Wages and the descriptive finance contrast.
7. Validation: known-answer recovery (A5 feedback 1 and 3) and Monte Carlo calibration of the inference.
8. Interpretation and limits. 9. Regenerate every artifact.

Method: `docs/A6_METHOD.md` · Evaluation: `docs/A6_EVALUATION_REPORT.md` · Interpretation: `docs/A6_INTERPRETATION.md`.

> **Data status: SYNTHETIC SAMPLE.** The committed database is built from `data/sample/` (seed 751). The generator plants an exposure-linked employment slowdown that grows each post year and **no** wage effect, and it does not simulate OEWS panel pooling. Estimates below therefore test the method against a known answer; they are not evidence about real occupations. `uv run oews-pipeline run --source raw` followed by `uv run oews-model` produces the real-data version (`docs/DATA_ACCESS.md`)."""),
(CODE, """# Setup: import the packages (installed by `uv sync`; the path fallback covers a bare Jupyter kernel)
import sys
from pathlib import Path

try:
    import oews_model
except ModuleNotFoundError:
    sys.path.insert(0, str(Path.cwd().resolve().parent / "src"))
    import oews_model

import pandas as pd
from IPython.display import display
from oews_eda import data, known_answer
from oews_model import analysis, inference, plots, report, validation

pd.set_option("display.float_format", "{:,.4f}".format)
pd.set_option("display.width", 170)
pd.set_option("display.max_colwidth", 70)
B, N_PERM = 1999, 999          # notebook draws; `uv run oews-model` uses 9999 / 4999
MODEL = data.REPO_ROOT / "reports" / "model"
print("oews_model", oews_model.__version__, "| database:", data.DEFAULT_DB.relative_to(data.REPO_ROOT))"""),
(MD, """## 1. Estimand, unit, specification, uncertainty

* **Unit:** detailed 2018-SOC occupation *o* × 4-digit NAICS industry *i* × May reference year *t* (2021-2025), one OEWS estimate per row.
* **Specification (A3):** log *Y*<sub>oit</sub> = α<sub>oi</sub> + δ<sub>it</sub> + β (Exposure<sub>o</sub> × Post<sub>t</sub>) + ε<sub>oit</sub>. α<sub>oi</sub> absorbs every fixed difference between occupation-industry cells; δ<sub>it</sub> absorbs every shock common to an industry in a year (rate cycles, sector hiring). Exposure is standardized across occupations, so β is per 1 SD of exposure.
* **Estimand:** β = the post-2022 change in log employment (or log mean wage) of an occupation with 1 SD higher GenAI exposure, relative to less-exposed occupations in the same industry and year. It is a *differential association*: exposure measures technical potential, not adoption.
* **Uncertainty:** exposure varies only across occupations, so errors are clustered by occupation (G ≈ 19). With so few clusters, CR1 t(G − 1) intervals are paired with a wild cluster restricted bootstrap (Webb weights) and randomization inference that reassigns exposure across occupations."""),
(CODE, """panel = data.load_panel()
qc = data.validate_panel(panel)
print("Quality gate passed:", qc.passed)
d = analysis.model_frame(panel)
scale = analysis.exposure_scale(d)
print(f"{len(d)} rows, {d['cell_id'].nunique()} cells, {scale['n_occupations']} occupations with exposure; "
      f"1 SD exposure = {scale['sd_exposure_share']:.3f} task share; IQR = {scale['iqr_z']:.2f} SD")
display(d.groupby("year")[["post", "post_delayed", "post_panel_share"]].first())"""),
(MD, """## 2. The A3 model

Why this method: the question is a pre/post difference between more- and less-exposed occupations, the data are a short panel of cells, and the outcome is a level observed every May. Two-way fixed effects with exposure × post is the difference-in-differences estimator for a continuous, time-invariant treatment intensity; industry-by-year effects make the comparison *within* industry and year, which is the A4/A5 comparison group carried into a model. Fixed effects are absorbed by alternating projections, which gives the same β as dummy-variable OLS (tested)."""),
(CODE, """main_spec = next(s for s in analysis.specifications() if s.key == "main")
main = analysis.run_spec(d, main_spec)
display(main.table)
wcr = inference.wild_cluster_bootstrap(main, B=B)
ri = inference.randomization_inference(main.data.frame, main, lambda x: (x["exposure_z"] * x["post"]).to_numpy(), n_perm=N_PERM)
print(f"n = {main.n_obs}, cells = {main.n_cells}, clusters = {main.n_clusters}, within R2 = {main.r2_within:.3f}")
print(f"WCR: p = {wcr['p_wcr']:.4f} (one-sided {wcr['p_wcr_lower']:.4f}), 95% CI [{wcr['ci_low_wcr']:+.4f}, {wcr['ci_high_wcr']:+.4f}]")
print(f"Randomization inference: p = {ri['p_ri']:.4f} ({ri['n_perm']} reassignments)")
print("Practical verdict (WCR CI vs +/-1 log point):", analysis.practical_verdict(wcr["ci_low_wcr"], wcr["ci_high_wcr"]))"""),
(MD, """## 3. Comparison with simpler specifications

The rubric requires a simpler comparison. Two are reported, in the same units:
* **Pooled OLS** (exposure, post, exposure × post; no fixed effects): what a cross-sectional reading of the panel gives.
* **Cell + year fixed effects**: the textbook two-way DiD, without industry-specific year shocks.

The A5 descriptive baseline (High − Low within-industry gap, `reports/eda/hypothesis_tests.csv`) is the binary-group version of the same contrast."""),
(CODE, """spec_emp = report.specification_table(d, "log_emp", B=B, n_perm=N_PERM)
cols = ["label", "role", "coef", "se_cr1", "ci_low_cr1", "ci_high_cr1", "p_wcr", "ci_low_wcr", "ci_high_wcr", "p_ri", "n_obs", "practical_verdict"]
display(spec_emp.query("role in ['comparison', 'main']")[cols])"""),
(MD, """**Reading.** Fixed effects change the *precision* far more than the point estimate: pooled OLS carries the large level differences between cells in its residual, so its interval spans zero. Adding industry-by-year effects to cell + year effects moves β little, so industry-wide shocks are not what drives the contrast on this sample."""),
(MD, """## 4. Event study and the pre-period diagnostic

Exposure × year coefficients with 2022 as the reference. The 2021 coefficient is the only pre-period check available in the consistent-method window (A3), so it has low power; it is a diagnostic, not a proof of parallel trends."""),
(CODE, """es = report.event_study_table(d, "log_emp", B=B)
display(es[["year", "coef", "ci_low_cr1", "ci_high_cr1", "ci_low_wcr", "ci_high_wcr", "p_wcr"]])
cf = validation.closed_form(d)
planted = pd.DataFrame({"year": [2021, 2022, 2023, 2024, 2025],
                        "coef": [cf["exp_y2021"], 0, cf["exp_y2023"], cf["exp_y2024"], cf["exp_y2025"]]})
fig = plots.plot_event_study(es, planted if panel.attrs.get("source_mode") == "sample" else None,
                             source_mode=panel.attrs.get("source_mode"))"""),
(MD, """## 5. Robustness and sensitivity

Timing (delayed post, with and without 2023; post-ChatGPT panel share as the dose), sample (balanced cells; excluding the 2017-NAICS year), an omitted-correlate check (Job Zone × post), and a placebo with a fake 2022 post on 2021-22 only. Then leave-one-industry-out and leave-one-occupation-out."""),
(CODE, """display(spec_emp.query("role in ['robustness', 'placebo']")[cols])
fig = plots.plot_spec_forest(spec_emp, analysis.PRACTICAL_THRESHOLD, source_mode=panel.attrs.get("source_mode"))"""),
(CODE, """loo = pd.concat([analysis.leave_one_out(d, "naics_code"), analysis.leave_one_out(d, "soc_code")], ignore_index=True)
display(loo.groupby("dropped_by")["coef"].describe()[["count", "min", "max"]])
fig = plots.plot_leave_one_out(loo, main.coef(), source_mode=panel.attrs.get("source_mode"))"""),
(MD, """## 6. Wages (two-sided) and the descriptive finance contrast"""),
(CODE, """spec_wage = report.specification_table(d, "log_wage", B=B, n_perm=N_PERM)
display(spec_wage[cols])
display(pd.concat([analysis.finance_contrast(d, o) for o in ("log_emp", "log_wage")], ignore_index=True))"""),
(MD, """The analyst and clerk terms are each a single occupation, i.e. one cluster, so no cluster-robust standard error exists for them. They are point estimates of how far each role sits from the exposure-predicted path, kept descriptive as the A3 feedback asked."""),
(MD, """## 7. Validation against the known answer

**A5 feedback 1 and 3.** The generator plants `1 - 0.06 (exposure - 0.6)(year - 2022)` from 2023. Two separate questions:

* *Is the code right?* With `emp_noise_sd = 0` nothing random is left in employment, so every estimate must equal the **oracle** (the same estimator applied to the planted log effect on the same cells) to within headcount rounding. The tolerances are tight enough that a one-year shift fails them (mutation tests in `tests/`).
* *Is the committed seed plausible?* 200 further seeds give the sampling spread; the seed-751 estimate must sit within 3 SDs of the noise-free value."""),
(CODE, """display(validation.recovery())
ka = known_answer.evaluate(seeds=range(752, 792))      # 40 seeds here; the committed report uses 200
display(ka["checks"][["statistic", "year", "closed_form", "noise_free", "oracle", "code_error", "code_pass",
                      "seed751", "seed_mean", "seed_sd", "seed751_z", "seed751_pctile", "sampling_pass"]])"""),
(MD, """**What happened to 2023.** On noise-free data the 2023 gap is −1.79 points against an oracle of −1.79, so the generator, the pipeline, the 2022 reference, the change definition and the median split all carry the 2023 effect correctly. The seed-751 value (+0.07) is a sampling outcome: across 200 seeds the 2023 gap averages −1.9 points with SD 0.77, and only 1 seed in 200 is as high. Part of the miss is shared with every year (the 2022 reference draw also lifts 2021 and 2024); the rest is the 2023 draw itself. It is not a code defect."""),
(MD, """### Monte Carlo calibration of the inference

`uv run oews-model simulate` re-runs the full pipeline and the main model on 200 seeds with the planted effect and 200 with **no** effect, recording bias, CR1 coverage, and the rejection rate of each test. Under no effect a 5% test should reject about 5% of the time."""),
(CODE, """mc = MODEL / "monte_carlo_summary.csv"
display(pd.read_csv(mc) if mc.exists() else "Run `uv run oews-model simulate` to create the calibration table.")"""),
(MD, """## 8. Interpretation and limits

The written interpretation (estimand, magnitude, inferential boundary, limitations) is in `docs/A6_INTERPRETATION.md`. On the sample it can only say that the method recovers what was planted; the substantive answer to the A3 question comes from the authorized real-data run, through the same command."""),
(MD, """## 9. Regenerate every artifact and the run log

`uv run oews-model` writes the tables in `reports/model/`, figures 12-14 and `model_run_log.json` (input and output SHA-256s). `uv run oews-model --verify-against reports/model/model_run_log.json` checks a rebuilt database against the log."""),
(CODE, """summary = report.run_all()          # about 3 minutes (9,999 bootstrap draws, 200 known-answer seeds)
print({k: summary[k] for k in ("source_mode", "panel", "validation")})"""),
]


def build(path: Path) -> None:
    """Write the notebook JSON (no outputs) to ``path``."""
    nb = {"cells": [], "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                    "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": kind, "id": f"cell-{i:02d}", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == CODE:
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    out = Path(__file__).with_name("03_model.ipynb")
    build(out)
    print(f"wrote {out}")
