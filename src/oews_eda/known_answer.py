"""Known-answer checks: what the EDA *should* recover from the synthetic generator, and how far off it may be.

The synthetic sample (``oews_pipeline.sample_data``) plants an employment effect of

    emp multiplier = 1 - EFFECT_SLOPE * (exposure - EFFECT_CENTER) * (year - 2022)   for year >= 2023

and no wage effect. This module turns that into numbers the EDA must hit, separating two questions
the A5 feedback asked to keep apart:

1. **Is the code right?**  Run the generator with ``emp_noise_sd=0``. Nothing random is left in the
   employment outcome, so the EDA estimate must equal the *oracle* (the same estimator applied to
   the planted log effect on the same cells) up to integer rounding of headcounts. A tight
   tolerance (``CODE_TOL_*``) turns any defect in the generator -> pipeline -> EDA chain (a shifted
   year, a wrong reference year, a flipped sign, a broken median split) into a test failure.
2. **Is a given seed's estimate plausible?**  Re-run the noisy generator over many seeds. The spread
   of the estimates is the sampling noise of a 19-occupation, ~130-cell panel. A seed's estimate
   is consistent with correct code when it lies within ``SAMPLING_Z`` standard deviations of the
   noise-free value.

Only test 1 can tell a bug from noise; test 2 says how big noise is. See
``docs/A6_EVALUATION_REPORT.md`` section 1 for the derivation and results.
"""
from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from . import data, describe

# Tolerances (documented in docs/A6_EVALUATION_REPORT.md §1)
CODE_TOL_SLOPE = 0.10      # pts per +0.1 exposure: noise-free EDA slope vs oracle
CODE_TOL_GAP = 0.25        # pts: noise-free event-time gap vs oracle, every year
SAMPLING_Z = 3.0           # a seed's estimate may sit at most 3 sampling SDs from the noise-free value


def closed_form_slope() -> float:
    """First-order slope the fig04 regression should recover, in points per +0.1 exposure.

    fig04 regresses d_log_emp = mean(post log emp) - mean(pre log emp) on exposure. With
    ln(1 - a x k) ~= -a x k, a = EFFECT_SLOPE and k = year - 2022 averaging (1 + 2 + 3) / 3 = 2 over
    2023-2025, the slope is -2a per unit of exposure, i.e. -2a * 100 / 10 points per +0.1.
    """
    from oews_pipeline.sample_data import EFFECT_SLOPE, YEARS
    k_bar = np.mean([y - 2022 for y in YEARS if y >= 2023])
    return float(-EFFECT_SLOPE * k_bar * 100 / 10)


def build_sample_db(out_dir: Path, seed: int = 751, emp_noise_sd: float | None = None) -> Path:
    """Generate a synthetic sample into ``out_dir`` and run the A4 pipeline on it; return the DB path.

    Writes nothing outside ``out_dir`` (no docs/QUALITY_REPORT.md, no reports/ JSON).
    """
    from oews_pipeline.pipeline import run_pipeline
    from oews_pipeline.sample_data import EMP_NOISE_SD, generate
    out_dir = Path(out_dir)
    generate(out_dir, seed=seed, emp_noise_sd=EMP_NOISE_SD if emp_noise_sd is None else emp_noise_sd)
    db = out_dir / "oews_known_answer.db"
    if db.exists():
        db.unlink()
    level = logging.getLogger("oews_pipeline").level
    logging.getLogger("oews_pipeline").setLevel(logging.WARNING)
    try:
        run_pipeline("sample", db_path=db, data_dir=out_dir, report_md=None, report_json_dir=out_dir)
    finally:
        logging.getLogger("oews_pipeline").setLevel(level)
    return db


def _planted_log_effect(panel: pd.DataFrame, slope: float | None = None) -> pd.Series:
    """ln(planted multiplier) per panel row, using the generator's own exposure values."""
    from oews_pipeline.sample_data import OCCUPATIONS, planted_effect
    gen_exp = {s: e for s, _, _, e, _ in OCCUPATIONS}
    eff = [np.log(planted_effect(gen_exp[s], y, slope)) if s in gen_exp else np.nan
           for s, y in zip(panel["soc_code"], panel["year"])]
    return pd.Series(eff, index=panel.index)


def oracle_panel(panel: pd.DataFrame, slope: float | None = None) -> pd.DataFrame:
    """Copy of ``panel`` whose log employment is replaced by the planted log effect on the same cells.

    Keeping the observed cells (suppression, merge attrition) means the oracle answers "what would the
    estimator report on exactly these cells if the code were right and there were no noise".
    """
    out = panel.copy()
    out["log_emp"] = _planted_log_effect(panel, slope).where(panel["log_emp"].notna())
    return out


def eda_slope(panel: pd.DataFrame) -> float:
    """fig04 statistic: OLS slope of cell d_log_emp on exposure, in points per +0.1 exposure."""
    c = describe.cell_changes(panel).dropna(subset=["d_log_emp", "exposure_main"])
    return float(stats.linregress(c["exposure_main"], c["d_log_emp"] * 100).slope / 10)


def eda_gaps(panel: pd.DataFrame) -> pd.Series:
    """fig11 statistic without the bootstrap: High - Low within-industry change since 2022, points, by year."""
    ch = describe.cell_year_changes(panel).dropna(subset=["exposure_group"])
    g = ch.groupby(["year", "exposure_group"])["change"].mean().unstack()
    return (g["High"] - g["Low"]) * 100


@dataclass
class KnownAnswer:
    """Estimates on one database next to their oracle values."""
    slope: float
    slope_oracle: float
    gaps: pd.Series
    gaps_oracle: pd.Series

    def table(self, label: str) -> pd.DataFrame:
        rows = [{"run": label, "statistic": "fig04 slope (pts per +0.1 exposure)", "year": None,
                 "estimate": self.slope, "oracle": self.slope_oracle}]
        rows += [{"run": label, "statistic": "fig11 High-Low gap (pts)", "year": int(y),
                  "estimate": float(self.gaps[y]), "oracle": float(self.gaps_oracle[y])} for y in self.gaps.index]
        out = pd.DataFrame(rows)
        out["error"] = out["estimate"] - out["oracle"]
        return out


def known_answer(db_path: Path | str) -> KnownAnswer:
    """EDA statistics and their oracle values on one pipeline database."""
    panel = data.load_panel(db_path)
    orc = oracle_panel(panel)
    return KnownAnswer(eda_slope(panel), eda_slope(orc), eda_gaps(panel), eda_gaps(orc))


def seed_distribution(seeds: range | list[int], work_dir: Path | None = None) -> pd.DataFrame:
    """EDA slope and event-time gaps for each generator seed (noisy), one row per seed."""
    rows = []
    with tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        for seed in seeds:
            db = build_sample_db(Path(tmp) / str(seed), seed=seed)
            panel = data.load_panel(db)
            gaps = eda_gaps(panel)
            rows.append({"seed": seed, "slope": eda_slope(panel),
                         **{f"gap_{int(y)}": float(v) for y, v in gaps.items()}})
    return pd.DataFrame(rows)


def evaluate(committed_db: Path | str = data.DEFAULT_DB, seeds: range | list[int] = range(752, 792),
             work_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Full known-answer report: noise-free check, committed-seed check, and sampling distribution.

    Returns:
        ``{"checks": ..., "seeds": ...}``. ``checks`` has one row per statistic with the noise-free
        estimate, oracle, code tolerance, committed-seed estimate, sampling SD across ``seeds``, the
        committed seed's z-score against the noise-free value, and pass flags.
    """
    with tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        clean = known_answer(build_sample_db(Path(tmp), seed=751, emp_noise_sd=0.0))
    committed = known_answer(committed_db)
    dist = seed_distribution(seeds, work_dir)

    rows = [("slope", None, clean.slope, clean.slope_oracle, CODE_TOL_SLOPE, committed.slope, dist["slope"])]
    for y in clean.gaps.index:
        col = f"gap_{int(y)}"
        if col in dist and dist[col].std() > 0:
            rows.append(("gap", int(y), float(clean.gaps[y]), float(clean.gaps_oracle[y]), CODE_TOL_GAP,
                         float(committed.gaps[y]), dist[col]))
    out = []
    for stat, year, est, orc, tol, seed_est, d in rows:
        sd = float(d.std(ddof=1))
        z = (seed_est - est) / sd
        out.append({"statistic": stat, "year": year, "closed_form": closed_form_slope() if stat == "slope" else None,
                    "noise_free": est, "oracle": orc, "code_error": est - orc, "code_tol": tol,
                    "code_pass": abs(est - orc) <= tol, "seed751": seed_est, "seed_mean": float(d.mean()),
                    "seed_sd": sd, "seed751_z": z, "seed751_pctile": float((d <= seed_est).mean() * 100),
                    "sampling_pass": abs(z) <= SAMPLING_Z})
    return {"checks": pd.DataFrame(out), "seeds": dist}
