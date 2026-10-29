"""Specifications for A6: the A3 model, the simpler comparison specifications, the event study and the robustness suite.

Every function takes the analysis panel from :func:`oews_eda.data.load_panel` (A4 database -> A5 EDA
loader), so A6 reads exactly the rows the EDA describes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from oews_eda.data import OEWS_VINTAGE, REFERENCE_YEAR

from .estimate import FEResult, ModelError, fit

MAIN_FE = ["cell_id", "indyear"]
EVENT_YEARS = [2021, 2023, 2024, 2025]
PRACTICAL_THRESHOLD = 0.01   # 1 log point per 1 SD of exposure (A5 practical-significance bar, carried forward)
CLUSTER = "soc_code"


def model_frame(panel: pd.DataFrame) -> pd.DataFrame:
    """Add the treatment variables, fixed-effect ids and sample flags the specifications use.

    Variables (all exposure terms use ``exposure_z``: occupation exposure standardized across
    occupations, so coefficients are per 1 SD of exposure):

        exp_post          exposure_z x 1[year >= 2023]                    (A3 primary)
        exp_post_delayed  exposure_z x 1[year >= 2024]                    (A3 delayed post)
        exp_share         exposure_z x share of post-ChatGPT OEWS panels  (0, 0, 1/6, 1/2, 5/6)
        exp_y{t}          exposure_z x 1[year == t], t != 2022            (event study, 2022 = reference)
        jz_post           standardized Job Zone x post                    (preparation control)
        analyst_post, clerk_post   focal-occupation x post                (descriptive contrast)
        indyear           industry-by-year fixed-effect id
        balanced_emp/_wage  cell observed in every year for that outcome
    """
    d = panel.copy()
    share = OEWS_VINTAGE["post_panel_share"]
    d["post_panel_share"] = d["year"].map(share)
    d["exp_post"] = d["exposure_z"] * d["post"]
    d["exp_post_delayed"] = d["exposure_z"] * d["post_delayed"]
    d["exp_share"] = d["exposure_z"] * d["post_panel_share"]
    for t in EVENT_YEARS:
        d[f"exp_y{t}"] = d["exposure_z"] * (d["year"] == t)
    d["exp_placebo"] = d["exposure_z"] * (d["year"] == REFERENCE_YEAR)
    occ_jz = d.drop_duplicates(CLUSTER).set_index(CLUSTER)["job_zone_mean"]
    jz_z = (d[CLUSTER].map(occ_jz) - occ_jz.mean()) / occ_jz.std()
    d["jz_post"] = jz_z * d["post"]
    d["analyst_post"] = (d["focal_role"] == "analyst").astype(float) * d["post"]
    d["clerk_post"] = (d["focal_role"] == "clerk_contrast").astype(float) * d["post"]
    d["indyear"] = d["naics_code"] + "|" + d["year"].astype(str)
    d["year_fe"] = d["year"].astype(str)
    n_years = d["year"].nunique()
    for out, tag in (("log_emp", "emp"), ("log_wage", "wage")):
        d[f"balanced_{tag}"] = d.groupby("cell_id")[out].transform("count") == n_years
    d.attrs.update(panel.attrs)
    return d


@dataclass(frozen=True)
class Spec:
    """One row of the specification table: what is estimated, on which rows, with which fixed effects."""
    key: str
    label: str
    role: str                     # 'comparison' | 'main' | 'robustness' | 'placebo' | 'descriptive'
    x: tuple[str, ...]
    fe: tuple[str, ...] = tuple(MAIN_FE)
    sample: str = "all"           # 'all' | 'balanced' | 'drop2021' | 'drop2023' | 'pre_only'
    note: str = ""


def specifications(outcome: str = "log_emp") -> list[Spec]:
    """The specification suite, in the order reported."""
    tag = "emp" if outcome == "log_emp" else "wage"
    return [
        Spec("pooled_ols", "Pooled OLS, no fixed effects", "comparison",
             ("exp_post", "exposure_z", "post"), (), note="Simplest DiD: exposure, post and their product"),
        Spec("twfe_year", "Cell + year fixed effects", "comparison", ("exp_post",), ("cell_id", "year_fe"),
             note="Classic two-way DiD; no industry-specific shocks"),
        Spec("main", "A3 model: cell + industry-by-year FE", "main", ("exp_post",),
             note="Primary estimate"),
        Spec("delayed_post", "Delayed post (2024+; 2023 coded pre)", "robustness", ("exp_post_delayed",)),
        Spec("delayed_drop2023", "Delayed post, 2023 excluded", "robustness", ("exp_post_delayed",),
             sample="drop2023"),
        Spec("panel_share", "Dose: share of post-ChatGPT OEWS panels", "robustness", ("exp_share",),
             note="Coefficient = gap once every panel is post-ChatGPT"),
        Spec("balanced", "Balanced cells only", "robustness", ("exp_post",), sample=f"balanced_{tag}"),
        Spec("drop2021", "Excluding May 2021 (2017 NAICS)", "robustness", ("exp_post",), sample="drop2021"),
        Spec("jobzone", "Adding Job Zone x post", "robustness", ("exp_post", "jz_post"),
             note="Exposure net of preparation level"),
        Spec("placebo", "Placebo: fake post in 2022 (2021-22 only)", "placebo", ("exp_placebo",),
             sample="pre_only", note="Should be ~0"),
    ]


def _subset(d: pd.DataFrame, sample: str) -> pd.DataFrame:
    if sample == "all":
        return d
    if sample.startswith("balanced"):
        return d[d[sample]]
    if sample == "drop2021":
        return d[d["year"] != 2021]
    if sample == "drop2023":
        return d[d["year"] != 2023]
    if sample == "pre_only":
        return d[d["year"] <= REFERENCE_YEAR]
    raise ModelError(f"unknown sample '{sample}'")


def run_spec(d: pd.DataFrame, spec: Spec, outcome: str = "log_emp") -> FEResult:
    """Estimate one specification on the model frame."""
    res = fit(_subset(d, spec.sample), outcome, list(spec.x), list(spec.fe), CLUSTER, label=spec.key)
    res.notes.update({"label": spec.label, "role": spec.role, "sample": spec.sample,
                      "fixed_effects": " + ".join(spec.fe) or "none", "note": spec.note})
    return res


def event_study(d: pd.DataFrame, outcome: str = "log_emp") -> FEResult:
    """Exposure-by-year coefficients relative to 2022, with the A3 fixed effects."""
    res = fit(d, outcome, [f"exp_y{t}" for t in EVENT_YEARS], MAIN_FE, CLUSTER, label="event_study")
    res.notes.update({"label": "Event study (2022 = 0)", "role": "event_study", "sample": "all",
                      "fixed_effects": " + ".join(MAIN_FE), "note": ""})
    return res


def leave_one_out(d: pd.DataFrame, by: str, outcome: str = "log_emp") -> pd.DataFrame:
    """Main coefficient re-estimated dropping one ``by`` group (industry or occupation) at a time."""
    rows = []
    # only groups that contribute to the estimate (an occupation without an exposure score drops out anyway)
    for g in sorted(d.dropna(subset=["exposure_z", outcome])[by].unique()):
        try:
            r = fit(d[d[by] != g], outcome, ["exp_post"], MAIN_FE, CLUSTER, label=f"drop {g}")
        except ModelError as exc:            # e.g. dropping the occupation leaves < MIN_CLUSTERS
            rows.append({"dropped_by": by, "dropped": g, "coef": np.nan, "se_cr1": np.nan, "error": str(exc)})
            continue
        rows.append({"dropped_by": by, "dropped": g, "coef": r.coef(), "se_cr1": float(r.table.iloc[0]["se"]),
                     "n_obs": r.n_obs, "n_clusters": r.n_clusters, "error": ""})
    return pd.DataFrame(rows)


def finance_contrast(d: pd.DataFrame, outcome: str = "log_emp") -> pd.DataFrame:
    """Descriptive analyst / clerk post-period deviations from the exposure-predicted path.

    Each focal role is a single occupation, i.e. a single cluster, so no cluster-robust standard error
    exists for its coefficient. Point estimates only; read as context (A3 feedback: keep descriptive).
    """
    res = fit(d, outcome, ["exp_post", "analyst_post", "clerk_post"], MAIN_FE, CLUSTER, label="finance_contrast")
    t = res.table
    return pd.DataFrame([
        {"term": "analyst_post", "role": "Financial & investment analysts (13-2051)",
         "coef": t.loc["analyst_post", "coef"], "pct_effect": (np.exp(t.loc["analyst_post", "coef"]) - 1) * 100},
        {"term": "clerk_post", "role": "Bookkeeping, accounting & auditing clerks (43-3031)",
         "coef": t.loc["clerk_post", "coef"], "pct_effect": (np.exp(t.loc["clerk_post", "coef"]) - 1) * 100},
        {"term": "exp_post", "role": "Exposure x post, holding the two roles' own deviations out",
         "coef": t.loc["exp_post", "coef"], "pct_effect": (np.exp(t.loc["exp_post", "coef"]) - 1) * 100},
    ]).assign(outcome=outcome, inference="descriptive: one occupation per role, no cluster SE")


def practical_verdict(lo: float, hi: float, threshold: float = PRACTICAL_THRESHOLD) -> str:
    """Classify an interval against the practical bar (log points per SD of exposure)."""
    if hi < -threshold or lo > threshold:
        return "practically meaningful"
    if lo > -threshold and hi < threshold:
        return "negligible (inside the bar)"
    if lo > 0 or hi < 0:
        return "nonzero but may be below the bar"
    return "inconclusive"


def exposure_scale(d: pd.DataFrame) -> dict[str, float]:
    """Exposure units, so per-SD coefficients can be restated for an interquartile move."""
    occ = d.drop_duplicates(CLUSTER).dropna(subset=["exposure_z"])
    q25, q75 = occ["exposure_z"].quantile([.25, .75])
    return {"sd_exposure_share": float(occ["exposure_main"].std()), "iqr_z": float(q75 - q25),
            "n_occupations": int(len(occ))}
