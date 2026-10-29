"""One-call A6 runner: estimates, inference, robustness, validation, figures and a run log.

``uv run oews-model`` (or :func:`run_all`) reads the A4 database through the A5 loader and writes:

    reports/model/specifications_emp.csv    comparison, main, robustness and placebo rows (CR1, WCR, RI)
    reports/model/specifications_wage.csv   same suite for log mean wage (two-sided outcome)
    reports/model/event_study_{emp,wage}.csv exposure-by-year coefficients, 2022 = 0
    reports/model/leave_one_out.csv         main coefficient dropping each industry / occupation
    reports/model/finance_contrast.csv      descriptive analyst / clerk deviations
    reports/model/known_answer_eda.csv      A5 fig04 / fig11 statistics vs the generator (sample only)
    reports/model/model_recovery.csv        A6 estimator vs the generator, noise-free (sample only)
    reports/model/model_summary.json        headline numbers cited in docs/A6_*.md
    reports/model/model_run_log.json        input SHA-256s, versions, commit, output SHA-256s
    reports/figures/fig12-fig14_*.png

``uv run oews-model simulate`` adds the Monte Carlo calibration tables (slow; committed outputs).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from oews_eda import data
from oews_eda import report as eda_report

from . import __version__
from . import analysis as A
from . import plots
from .inference import randomization_inference, wild_cluster_bootstrap

log = logging.getLogger("oews_model")
FIG_DIR = data.REPO_ROOT / "reports" / "figures"
TABLE_DIR = data.REPO_ROOT / "reports" / "model"
OUTCOMES = {"log_emp": "emp", "log_wage": "wage"}


def _x_builder(term: str):
    """Rebuild a tested regressor from (permuted) exposure, for randomization inference."""
    by = {"exp_post": "post", "exp_post_delayed": "post_delayed", "exp_share": "post_panel_share",
          "exp_placebo": None}

    def build(d: pd.DataFrame) -> np.ndarray:
        if term == "exp_placebo":
            return (d["exposure_z"] * (d["year"] == 2022)).to_numpy(float)
        return (d["exposure_z"] * d[by[term]]).to_numpy(float)
    return build


def specification_table(d: pd.DataFrame, outcome: str = "log_emp", B: int = 9999, n_perm: int = 4999,
                        seed: int = 751) -> pd.DataFrame:
    """Every specification with CR1, wild-cluster-bootstrap and randomization inference on its first term."""
    rows = []
    for spec in A.specifications(outcome):
        res = A.run_spec(d, spec, outcome)
        term = spec.x[0]
        row = res.row(term)
        row.update(wild_cluster_bootstrap(res, term, B=B, seed=seed))
        if spec.role != "comparison" or spec.key == "twfe_year":
            row.update(randomization_inference(res.data.frame, res, _x_builder(term), n_perm=n_perm, seed=seed))
        row["practical_verdict"] = A.practical_verdict(row["ci_low_wcr"], row["ci_high_wcr"])
        rows.append(row)
    return pd.DataFrame(rows)


def event_study_table(d: pd.DataFrame, outcome: str = "log_emp", B: int = 9999, seed: int = 751) -> pd.DataFrame:
    """Event-study coefficients with CR1 and WCR intervals, plus the 2022 reference row."""
    res = A.event_study(d, outcome)
    rows = [{"year": 2022, "term": "reference", "coef": 0.0, "se_cr1": 0.0, "ci_low_cr1": 0.0, "ci_high_cr1": 0.0,
             "p_cr1": np.nan, "ci_low_wcr": 0.0, "ci_high_wcr": 0.0, "p_wcr": np.nan}]
    for t in A.EVENT_YEARS:
        name = f"exp_y{t}"
        r = res.table.loc[name]
        w = wild_cluster_bootstrap(res, name, B=B, seed=seed)
        rows.append({"year": t, "term": name, "coef": r["coef"], "se_cr1": r["se"], "ci_low_cr1": r["ci_low"],
                     "ci_high_cr1": r["ci_high"], "p_cr1": r["p"], "ci_low_wcr": w["ci_low_wcr"],
                     "ci_high_wcr": w["ci_high_wcr"], "p_wcr": w["p_wcr"]})
    out = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    out["outcome"] = outcome
    out["n_obs"], out["n_clusters"] = res.n_obs, res.n_clusters
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_all(db_path: Path | str = data.DEFAULT_DB, fig_dir: Path = FIG_DIR, table_dir: Path = TABLE_DIR,
            B: int = 9999, n_perm: int = 4999, validate: bool = True) -> dict:
    """Run the full A6 analysis and write every artifact.

    Args:
        db_path: A4 pipeline database (sample or authorized raw build).
        B, n_perm: Wild-bootstrap draws and randomization permutations (lower them only for tests).
        validate: On the synthetic sample, also run the known-answer and recovery checks.

    Raises:
        FileNotFoundError: database missing. ValueError: the A5 data-quality gate fails.
        oews_model.estimate.ModelError: a specification cannot be estimated (e.g. too few clusters).
    """
    db_path, fig_dir, table_dir = Path(db_path), Path(fig_dir), Path(table_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}. Run `uv run oews-pipeline run` first.")
    panel = data.load_panel(db_path)
    qc = data.validate_panel(panel)
    if not qc.passed:
        failed = [k for k, v in qc.checks.items() if not v]
        raise ValueError(f"data-quality gate failed ({failed}); no estimates produced")
    mode = panel.attrs.get("source_mode", "unknown")
    d = A.model_frame(panel)
    table_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def save(df: pd.DataFrame, name: str) -> None:
        p = table_dir / name
        df.to_csv(p, index=False)
        written.append(p)

    specs, events = {}, {}
    for outcome, tag in OUTCOMES.items():
        specs[tag] = specification_table(d, outcome, B=B, n_perm=n_perm)
        events[tag] = event_study_table(d, outcome, B=B)
        save(specs[tag], f"specifications_{tag}.csv")
        save(events[tag], f"event_study_{tag}.csv")
    loo = pd.concat([A.leave_one_out(d, "naics_code"), A.leave_one_out(d, "soc_code")], ignore_index=True)
    save(loo, "leave_one_out.csv")
    fc = pd.concat([A.finance_contrast(d, o) for o in OUTCOMES], ignore_index=True)
    save(fc, "finance_contrast.csv")

    planted = None
    validation: dict = {}
    if validate and mode == "sample":
        from oews_eda.known_answer import evaluate
        from .validation import closed_form, recovery
        ka = evaluate(db_path, seeds=range(752, 952))
        save(ka["checks"], "known_answer_eda.csv")
        save(ka["seeds"], "known_answer_seeds.csv")
        rec = recovery()
        save(rec, "model_recovery.csv")
        cf = closed_form(d)
        planted = pd.DataFrame({"year": [2021, 2022, 2023, 2024, 2025],
                                "coef": [cf["exp_y2021"], 0.0, cf["exp_y2023"], cf["exp_y2024"], cf["exp_y2025"]]})
        validation = {"eda_code_pass": bool(ka["checks"]["code_pass"].all()),
                      "eda_sampling_pass": bool(ka["checks"]["sampling_pass"].all()),
                      "model_recovery_pass": bool(rec["recovery_pass"].all() and rec["closed_form_pass"].all()),
                      "gap_2023_seed751_pctile": float(ka["checks"].query("year == 2023")["seed751_pctile"].iat[0])}

    fig_dir.mkdir(parents=True, exist_ok=True)
    figs = [
        (plots.plot_event_study(events["emp"], planted, fig_dir / "fig12_event_study_emp.png", mode), "fig12_event_study_emp.png"),
        (plots.plot_spec_forest(specs["emp"], A.PRACTICAL_THRESHOLD, fig_dir / "fig13_specification_forest_emp.png", mode),
         "fig13_specification_forest_emp.png"),
        (plots.plot_leave_one_out(loo, specs["emp"].query("spec == 'main'")["coef"].iat[0],
                                  fig_dir / "fig14_leave_one_out_emp.png", mode), "fig14_leave_one_out_emp.png"),
    ]
    for fig, name in figs:
        plt.close(fig)
        written.append(fig_dir / name)

    main = {tag: specs[tag].query("spec == 'main'").iloc[0].to_dict() for tag in OUTCOMES.values()}
    scale = A.exposure_scale(d)
    summary = {
        "source_mode": mode,
        "estimand": "beta: differential change in log outcome after 2022 per 1 SD of occupation GenAI exposure, "
                    "within occupation-by-industry cells and net of industry-by-year shocks",
        "panel": {"rows": int(main["emp"]["n_obs"]), "cells": int(main["emp"]["n_cells"]),
                  "occupation_clusters": int(main["emp"]["n_clusters"]), **scale},
        "main": {tag: {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                       for k, v in m.items() if k in ("coef", "se_cr1", "ci_low_cr1", "ci_high_cr1", "p_cr1",
                                                    "p_wcr", "p_wcr_lower", "ci_low_wcr", "ci_high_wcr", "p_ri",
                                                    "p_ri_lower", "pct_effect", "practical_verdict")}
                 for tag, m in main.items()},
        "iqr_move_pct_emp": float((np.exp(main["emp"]["coef"] * scale["iqr_z"]) - 1) * 100),
        "pretrend_2021_emp": events["emp"].query("year == 2021")[["coef", "ci_low_wcr", "ci_high_wcr", "p_wcr"]]
        .iloc[0].astype(float).to_dict(),
        "robustness_range_emp": [float(specs["emp"].query("role == 'robustness'")["coef"].min()),
                                 float(specs["emp"].query("role == 'robustness'")["coef"].max())],
        "leave_one_out_range_emp": [float(loo["coef"].min()), float(loo["coef"].max())],
        "validation": validation,
        "inference_draws": {"wild_bootstrap_B": B, "permutations": n_perm},
    }
    sp = table_dir / "model_summary.json"
    sp.write_text(json.dumps(summary, indent=2, default=str))
    written.append(sp)

    run = eda_report.run_log(db_path)
    run["versions"]["oews_model"] = __version__
    run["command"] = "uv run oews-model"
    run["outputs"] = [{"file": str(p.relative_to(data.REPO_ROOT)) if p.is_relative_to(data.REPO_ROOT) else p.name,
                       "sha256": _sha(p)} for p in written if p.suffix in (".csv", ".json")]
    (table_dir / "model_run_log.json").write_text(json.dumps(run, indent=2))
    log.info("A6 outputs written to %s and %s", table_dir, fig_dir)
    return summary


def simulate(seeds: int = 200, table_dir: Path = TABLE_DIR, B: int = 999, n_perm: int = 499) -> pd.DataFrame:
    """Monte Carlo calibration (planted effect and no effect); writes monte_carlo*.csv. Takes minutes."""
    from .validation import monte_carlo, summarize_monte_carlo
    table_dir = Path(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)
    mc = pd.concat([monte_carlo(range(1000, 1000 + seeds), B=B, n_perm=n_perm),
                    monte_carlo(range(2000, 2000 + seeds), effect_slope=0.0, B=B, n_perm=n_perm)],
                   ignore_index=True)
    mc.to_csv(table_dir / "monte_carlo_draws.csv", index=False)
    summ = summarize_monte_carlo(mc)
    summ.to_csv(table_dir / "monte_carlo_summary.csv", index=False)
    return summ
