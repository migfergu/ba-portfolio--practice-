"""Univariate, bivariate and multivariate descriptive analysis.

Every function takes a DataFrame and returns a DataFrame, so results can be printed in the
notebook, saved to ``reports/eda/`` and reused by later assignments without copy-paste.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .data import REFERENCE_YEAR


# ---------------------------------------------------------------- univariate
def univariate_summary(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Distribution summary for numeric columns.

    Args:
        df: Any frame (panel rows, cells, or occupations).
        columns: Numeric columns to describe.

    Returns:
        One row per column: n, missing share, mean, sd, min, quartiles, max, skewness and excess
        kurtosis. Skew far from 0 is the cue to model a variable in logs.
    """
    rows = {}
    for col in columns:
        s = df[col].astype(float)
        x = s.dropna()
        rows[col] = {"n": int(x.size), "missing_share": round(float(s.isna().mean()), 3),
                     "mean": x.mean(), "sd": x.std(ddof=1), "min": x.min(),
                     "p25": x.quantile(.25), "median": x.median(), "p75": x.quantile(.75),
                     "max": x.max(), "skew": stats.skew(x), "excess_kurtosis": stats.kurtosis(x)}
    return pd.DataFrame(rows).T


def occupation_table(panel: pd.DataFrame) -> pd.DataFrame:
    """One row per occupation: exposure, preparation, group labels and pre-period size/pay.

    Pre-period employment is the mean of 2021-2022 total employment summed across industries.
    """
    pre = panel[panel["post"] == 0]
    size = (pre.groupby(["soc_code", "year"])["tot_emp"].sum().groupby("soc_code").mean()
            .rename("pre_emp_total"))
    wage = pre.groupby("soc_code")["a_mean"].mean().rename("pre_mean_wage")
    base = (panel.drop_duplicates("soc_code")
            .set_index("soc_code")[["occ_title", "focal_role", "exposure_main", "exposure_z",
                                    "job_zone_mean", "exposure_group", "exposure_tercile"]])
    n_ind = panel.groupby("soc_code")["naics_code"].nunique().rename("n_industries")
    return base.join([size, wage, n_ind]).sort_values("exposure_main", ascending=False)


# ---------------------------------------------------------------- bivariate
def cell_changes(panel: pd.DataFrame, post_col: str = "post") -> pd.DataFrame:
    """Collapse the panel to one pre -> post change per occupation x industry cell.

    For each cell: ``d_log_emp`` = mean post-period log employment minus mean pre-period log
    employment (likewise ``d_log_wage``). Averaging within period uses every available year and
    tolerates a suppressed year. This is the cell-level analogue of the A3 difference-in-differences
    contrast. A cell needs at least one pre and one post observation of the outcome.

    Args:
        panel: Output of :func:`oews_eda.data.load_panel`.
        post_col: 'post' (2023+) or 'post_delayed' (2024+, A3 robustness timing).

    Returns:
        One row per cell with exposure, group labels, job zone, sector, pre-period levels and changes.
    """
    attrs = (panel.drop_duplicates("cell_id")
             .set_index("cell_id")[["soc_code", "naics_code", "occ_title", "naics_title", "naics_sector",
                                    "focal_role", "exposure_main", "exposure_z", "job_zone_mean",
                                    "exposure_group", "exposure_tercile"]])
    out = attrs.copy()
    for var in ("log_emp", "log_wage"):
        means = panel.groupby(["cell_id", post_col])[var].mean().unstack(post_col)
        out[f"pre_{var}"] = means.get(0)
        out[f"post_{var}"] = means.get(1)
        out[f"d_{var}"] = out[f"post_{var}"] - out[f"pre_{var}"]
    out = out.reset_index()
    # Within-industry change: subtract the industry's mean change, so the comparison is high- vs
    # low-exposure occupations in the SAME industry over the SAME period (the long-difference analogue
    # of the A3 industry-by-year fixed effects). This removes industry-wide shocks such as rate cycles.
    for var in ("log_emp", "log_wage"):
        col = f"d_{var}"
        out[f"{col}_wi"] = out[col] - out.groupby("naics_code")[col].transform("mean")
    out.attrs.update(panel.attrs)
    out.attrs["post_definition"] = post_col
    return out


def group_comparison(cells: pd.DataFrame, value: str, group: str = "exposure_group") -> pd.DataFrame:
    """Mean, median, sd and n of ``value`` by group, with exp(mean)-1 as an approximate % change."""
    g = cells.dropna(subset=[value, group]).groupby(group)[value]
    out = g.agg(n="size", mean="mean", median="median", sd="std")
    out["approx_pct_change"] = (np.exp(out["mean"]) - 1) * 100
    return out


def correlation_table(cells: pd.DataFrame, columns: list[str], method: str = "spearman") -> pd.DataFrame:
    """Pairwise correlation matrix (Spearman by default: robust to skew and outliers)."""
    return cells[columns].corr(method=method)


def correlation_with_pvalues(cells: pd.DataFrame, x: str, y: str) -> dict[str, float]:
    """Pearson and Spearman correlation between two columns, with p-values and n."""
    d = cells[[x, y]].dropna()
    pr, pp = stats.pearsonr(d[x], d[y])
    sr, sp = stats.spearmanr(d[x], d[y])
    return {"n": int(len(d)), "pearson_r": float(pr), "pearson_p": float(pp),
            "spearman_rho": float(sr), "spearman_p": float(sp)}


def occupation_changes(cells: pd.DataFrame, value: str = "d_log_emp") -> pd.DataFrame:
    """Aggregate cell changes to occupations, weighting cells by pre-period employment.

    Exposure varies only by occupation, so this is the honest unit for an exposure-outcome
    correlation: n equals the number of occupations, not the number of cells.
    """
    d = cells.dropna(subset=[value, "exposure_main"]).copy()
    d["w"] = np.exp(d["pre_log_emp"]).fillna(1.0)
    agg = d.groupby("soc_code").apply(
        lambda g: pd.Series({"occ_title": g["occ_title"].iat[0], "exposure_main": g["exposure_main"].iat[0],
                             "job_zone_mean": g["job_zone_mean"].iat[0], "focal_role": g["focal_role"].iat[0],
                             value: np.average(g[value], weights=g["w"]), "n_cells": len(g)}),
        include_groups=False)
    return agg.sort_values("exposure_main", ascending=False)


def cell_year_changes(panel: pd.DataFrame, outcome: str = "log_emp", base_year: int = REFERENCE_YEAR,
                      within_industry: bool = True) -> pd.DataFrame:
    """Per cell and year: outcome minus the cell's own base-year value (event time, 2022 = 0).

    With ``within_industry=True`` the industry-by-year mean change is subtracted, so each value is
    the cell's change relative to other occupations in its industry in that year.

    Returns:
        Long frame with cell_id, soc_code, naics_code, year, exposure_group, change.
    """
    d = panel.dropna(subset=[outcome]).copy()
    base = d[d["year"] == base_year].set_index("cell_id")[outcome]
    d = d[d["cell_id"].isin(base.index)]
    d["change"] = d[outcome] - d["cell_id"].map(base)
    if within_industry:
        d["change"] = d["change"] - d.groupby(["naics_code", "year"])["change"].transform("mean")
    return d[["cell_id", "soc_code", "naics_code", "year", "exposure_group", "exposure_main", "change"]]


def pre_period_change(panel: pd.DataFrame, outcome: str = "log_emp", within_industry: bool = True) -> pd.DataFrame:
    """Placebo outcome: 2021 -> 2022 change per cell (both years pre-ChatGPT; should show no exposure gap)."""
    ch = cell_year_changes(panel, outcome, base_year=2021, within_industry=within_industry)
    out = ch[ch["year"] == REFERENCE_YEAR].rename(columns={"change": f"d_pre_{outcome}"})
    return out.drop(columns="year")


# ---------------------------------------------------------------- multivariate / trends
def trend_index(panel: pd.DataFrame, by: str = "exposure_tercile", outcome: str = "log_emp",
                reference_year: int = REFERENCE_YEAR) -> pd.DataFrame:
    """Mean outcome by group and year, re-based so reference_year = 100.

    Computed as 100 * exp(mean log outcome - mean log outcome in the reference year), i.e. a
    geometric-mean index. Pass a balanced panel (``data.balanced_cells``) to avoid composition
    effects.

    Returns:
        Long frame: group, year, n_cells, index.
    """
    m = panel.dropna(subset=[outcome, by]).groupby([by, "year"])[outcome].agg(["mean", "size"]).reset_index()
    ref = m[m["year"] == reference_year].set_index(by)["mean"]
    m["index"] = 100 * np.exp(m["mean"] - m[by].map(ref))
    return m.rename(columns={"size": "n_cells", by: "group"})[["group", "year", "n_cells", "index"]]


def focal_contrast(panel: pd.DataFrame, reference_year: int = REFERENCE_YEAR) -> pd.DataFrame:
    """Descriptive analyst-vs-clerk contrast (A3; instructor: keep descriptive, not causal).

    For each focal occupation, keeps its industry cells observed (employment and wage) in every
    panel year, so the index reflects a fixed set of cells rather than suppression churn. Sums
    employment and averages wages within role-year, then indexes each to reference_year = 100.

    Returns:
        Long frame: focal_role, year, total_emp, mean_wage, n_industries, emp_index, wage_index.
    """
    n_years = panel["year"].nunique()
    f = panel[panel["focal_role"].notna()].dropna(subset=["tot_emp", "a_mean"])
    obs = f.groupby("cell_id")["year"].nunique()
    f = f[f["cell_id"].isin(obs[obs == n_years].index)]
    g = f.groupby(["focal_role", "year"]).agg(total_emp=("tot_emp", "sum"), mean_wage=("a_mean", "mean"),
                                             n_industries=("naics_code", "nunique")).reset_index()
    for col, new in (("total_emp", "emp_index"), ("mean_wage", "wage_index")):
        ref = g[g["year"] == reference_year].set_index("focal_role")[col]
        g[new] = 100 * g[col] / g["focal_role"].map(ref)
    return g
