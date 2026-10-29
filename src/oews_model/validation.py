"""Validation of the A6 estimator against the synthetic generator's known answer.

Two layers, mirroring ``oews_eda.known_answer``:

* **Recovery (code correctness).** On a noise-free sample the estimator must reproduce the oracle (the
  same specification fitted to the planted log effect on the same cells) almost exactly, and the
  oracle must match the closed-form value implied by the generator.
* **Monte Carlo (inference calibration).** Over many seeds, with the planted effect and with no effect,
  record the estimate, its CR1 standard error, CR1 interval coverage of the oracle, and the rejection
  rates of CR1, wild-cluster-bootstrap and randomization tests. Under no effect a 5% test should reject
  about 5% of the time; that is the check on whether the inference can be trusted with ~19 clusters.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from oews_eda import data
from oews_eda.known_answer import build_sample_db, oracle_panel

from . import analysis as A
from .inference import randomization_inference, wild_cluster_bootstrap

RECOVERY_TOL_MAIN = 0.001     # log points per SD: noise-free estimate vs oracle (headcount rounding only)
RECOVERY_TOL_EVENT = 0.002
CLOSED_FORM_TOL = 0.10        # relative: oracle vs first-order closed form (log approximation, exposure measure)


def closed_form(d: pd.DataFrame) -> dict[str, float]:
    """First-order coefficients implied by the generator, per 1 SD of exposure.

    The generator multiplies employment by 1 - a (e - 0.6) k with k = year - 2022 in post years, so
    log employment moves by about -a k per unit of exposure, i.e. -a k sd(e) per SD. The post-period
    dummy averages k over 2023-2025 (k_bar = 2); event-time coefficients are -a k sd(e) for each year.
    """
    from oews_pipeline.sample_data import EFFECT_SLOPE, YEARS
    sd = A.exposure_scale(d)["sd_exposure_share"]
    post = [y - 2022 for y in YEARS if y >= 2023]
    out = {"main": -EFFECT_SLOPE * np.mean(post) * sd}
    for t in A.EVENT_YEARS:
        out[f"exp_y{t}"] = -EFFECT_SLOPE * max(t - 2022, 0) * sd
    return out


def recovery(work_dir: Path | None = None) -> pd.DataFrame:
    """Noise-free recovery table for the main coefficient and the event-study path."""
    with tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        d = A.model_frame(data.load_panel(build_sample_db(Path(tmp), seed=751, emp_noise_sd=0.0)))
    orc = A.model_frame(oracle_panel(d))
    cf = closed_form(d)
    main_spec = next(s for s in A.specifications() if s.key == "main")
    rows = [("main", A.run_spec(d, main_spec).coef(), A.run_spec(orc, main_spec).coef(), cf["main"],
             RECOVERY_TOL_MAIN)]
    est, ore = A.event_study(d), A.event_study(orc)
    for t in A.EVENT_YEARS:
        name = f"exp_y{t}"
        rows.append((name, est.coef(name), ore.coef(name), cf[name], RECOVERY_TOL_EVENT))
    out = pd.DataFrame(rows, columns=["term", "noise_free", "oracle", "closed_form", "tol"])
    out["recovery_error"] = out["noise_free"] - out["oracle"]
    out["recovery_pass"] = out["recovery_error"].abs() <= out["tol"]
    rel = (out["oracle"] - out["closed_form"]).abs() / out["closed_form"].abs().where(out["closed_form"] != 0)
    out["closed_form_rel_gap"] = rel
    out["closed_form_pass"] = rel.isna() | (rel <= CLOSED_FORM_TOL) | (out["oracle"].abs() < 1e-3)
    return out


def monte_carlo(seeds: range | list[int], effect_slope: float | None = None, B: int = 999, n_perm: int = 499,
                work_dir: Path | None = None) -> pd.DataFrame:
    """One row per seed: main estimate, oracle, CR1 SE/CI, and CR1 / WCR / RI p-values (two-sided, 5%)."""
    from oews_pipeline.sample_data import EFFECT_SLOPE, generate
    from oews_pipeline.pipeline import run_pipeline
    a = EFFECT_SLOPE if effect_slope is None else effect_slope
    main_spec = next(s for s in A.specifications() if s.key == "main")
    rows = []
    with tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        for seed in seeds:
            out = Path(tmp) / str(seed)
            generate(out, seed=seed, effect_slope=a)
            db = out / "mc.db"
            run_pipeline("sample", db_path=db, data_dir=out, report_md=None, report_json_dir=out)
            d = A.model_frame(data.load_panel(db))
            r = A.run_spec(d, main_spec)
            truth = A.run_spec(A.model_frame(oracle_panel(d, slope=a)), main_spec).coef() if a else 0.0
            t = r.table.iloc[0]
            w = wild_cluster_bootstrap(r, B=B, seed=seed, ci=False)
            ri = randomization_inference(r.data.frame, r, lambda x: (x["exposure_z"] * x["post"]).to_numpy(),
                                         n_perm=n_perm, seed=seed)
            rows.append({"seed": seed, "effect_slope": a, "coef": t["coef"], "truth": truth, "se_cr1": t["se"],
                         "covers_cr1": t["ci_low"] <= truth <= t["ci_high"], "p_cr1": t["p"],
                         "p_wcr": w["p_wcr"], "p_ri": ri["p_ri"]})
    return pd.DataFrame(rows)


def summarize_monte_carlo(mc: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """Bias, SE calibration, coverage and rejection rates by planted effect size."""
    out = []
    for a, g in mc.groupby("effect_slope"):
        out.append({"effect_slope": a, "n_seeds": len(g), "mean_truth": g["truth"].mean(),
                    "mean_coef": g["coef"].mean(), "bias": (g["coef"] - g["truth"]).mean(),
                    "sd_coef": g["coef"].std(ddof=1), "mean_se_cr1": g["se_cr1"].mean(),
                    "se_ratio": g["se_cr1"].mean() / g["coef"].std(ddof=1),
                    "coverage_cr1": g["covers_cr1"].mean(),
                    "reject_cr1": (g["p_cr1"] < alpha).mean(), "reject_wcr": (g["p_wcr"] < alpha).mean(),
                    "reject_ri": (g["p_ri"] < alpha).mean()})
    return pd.DataFrame(out)
