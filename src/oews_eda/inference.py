"""Hypothesis tests, assumption checks, effect sizes and cluster-robust regression.

Design note. GenAI exposure varies only across *occupations*, while the panel has many
occupation x industry cells per occupation. Cells of the same occupation are therefore not
independent, and a naive cell-level test overstates the evidence. Every test here is paired
with an occupation-level or occupation-clustered check, mirroring the A3 plan to cluster
standard errors by occupation.

Implemented with NumPy/SciPy only (no extra dependency): OLS with CR1 cluster-robust
standard errors and G-1 degrees of freedom, matching the small-cluster correction used by
Stata and ``statsmodels`` (``cov_type='cluster'``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------- assumptions & effect size
def check_assumptions(a: np.ndarray, b: np.ndarray, alpha: float = 0.05) -> dict[str, object]:
    """Check the assumptions of a two-sample mean comparison.

    * Normality: Shapiro-Wilk per group (with n > 30 the CLT makes the t-test robust anyway).
    * Equal variances: Levene (median-centred, Brown-Forsythe variant).

    Returns:
        Dict of statistics, p-values, booleans, and the recommended test
        ('student_t', 'welch_t', or 'mann_whitney').
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    sw_a, sw_b = stats.shapiro(a), stats.shapiro(b)
    lev = stats.levene(a, b, center="median")
    normal = (sw_a.pvalue > alpha and sw_b.pvalue > alpha) or min(a.size, b.size) > 30
    equal_var = lev.pvalue > alpha
    recommended = ("student_t" if equal_var else "welch_t") if normal else "mann_whitney"
    return {"n_a": int(a.size), "n_b": int(b.size),
            "shapiro_a_W": float(sw_a.statistic), "shapiro_a_p": float(sw_a.pvalue),
            "shapiro_b_W": float(sw_b.statistic), "shapiro_b_p": float(sw_b.pvalue),
            "levene_W": float(lev.statistic), "levene_p": float(lev.pvalue),
            "normal_or_large_n": bool(normal), "equal_variances": bool(equal_var),
            "recommended_test": recommended}


def hedges_g(a: np.ndarray, b: np.ndarray) -> float:
    """Bias-corrected standardized mean difference (a - b) / pooled sd (Hedges' g)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = a.size, b.size
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    j = 1 - 3 / (4 * (na + nb) - 9)
    return float(j * (a.mean() - b.mean()) / sp)


def cluster_bootstrap_diff(df: pd.DataFrame, value: str, group: str, high: str, low: str,
                           cluster: str = "soc_code", n_boot: int = 2000, seed: int = 751) -> tuple[float, float]:
    """95% percentile CI for mean(high) - mean(low), resampling whole clusters (occupations).

    Resampling occupations rather than cells keeps within-occupation correlation intact.
    """
    rng = np.random.default_rng(seed)
    d = df.dropna(subset=[value, group])
    by = {g: [grp[value].to_numpy() for _, grp in sub.groupby(cluster)] for g, sub in d.groupby(group)}
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        draw = {}
        for g in (high, low):
            parts = by[g]
            idx = rng.integers(0, len(parts), len(parts))
            draw[g] = np.concatenate([parts[j] for j in idx]).mean()
        diffs[i] = draw[high] - draw[low]
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


# ---------------------------------------------------------------- main hypothesis test
@dataclass
class GroupTestResult:
    """Everything needed to report a two-group hypothesis test properly."""
    outcome: str
    h0: str
    h1: str
    alternative: str
    n_high: int
    n_low: int
    mean_high: float
    mean_low: float
    diff: float
    diff_pct_points: float
    test_used: str
    statistic: float
    p_value: float
    hedges_g: float
    cluster_ci_low: float
    cluster_ci_high: float
    mann_whitney_p: float
    assumptions: dict = field(default_factory=dict)
    decision: str = ""
    interpretation: str = ""

    def to_dict(self) -> dict:
        """Plain-dict form for JSON export."""
        return asdict(self)


def exposure_group_test(cells: pd.DataFrame, value: str = "d_log_emp", alternative: str = "less",
                        group: str = "exposure_group", alpha: float = 0.05) -> GroupTestResult:
    """Test whether high-exposure cells changed differently from low-exposure cells pre -> post.

    Hypotheses (A3 H1 for employment is directional; wages are two-sided):
        H0: mu_High - mu_Low >= 0 (alternative='less') or = 0 (alternative='two-sided')
        H1: mu_High - mu_Low <  0                        or != 0

    The test is chosen from :func:`check_assumptions` (Welch's t when variances differ, Student's t
    when they do not, Mann-Whitney U when normality fails in small samples). Mann-Whitney is
    always reported as a distribution-free robustness check, and an occupation-cluster bootstrap
    CI shows whether the conclusion survives within-occupation dependence.
    """
    d = cells.dropna(subset=[value, group])
    hi = d.loc[d[group] == "High", value].to_numpy()
    lo = d.loc[d[group] == "Low", value].to_numpy()
    a = check_assumptions(hi, lo, alpha)
    if a["recommended_test"] == "mann_whitney":
        res = stats.mannwhitneyu(hi, lo, alternative=alternative)
        name = "Mann-Whitney U"
    else:
        res = stats.ttest_ind(hi, lo, equal_var=a["equal_variances"], alternative=alternative)
        name = "Student's t" if a["equal_variances"] else "Welch's t"
    mw = stats.mannwhitneyu(hi, lo, alternative=alternative)
    ci = cluster_bootstrap_diff(d, value, group, "High", "Low")
    diff = float(hi.mean() - lo.mean())
    h0 = "mean(High) - mean(Low) >= 0" if alternative == "less" else "mean(High) - mean(Low) = 0"
    h1 = "mean(High) - mean(Low) < 0" if alternative == "less" else "mean(High) - mean(Low) != 0"
    reject = res.pvalue < alpha
    ci_excludes_zero = ci[1] < 0 or ci[0] > 0
    label = "employment" if "emp" in value else "mean wages"
    pct = (np.exp(diff) - 1) * 100
    if abs(pct) < 0.5:
        interp = (f"High- and low-exposure cells' {label} changed by virtually the same amount between the pre "
                  f"and post periods (gap {pct:+.2f}%, Hedges' g = {hedges_g(hi, lo):.2f}). ")
    else:
        interp = (f"High-exposure cells' {label} grew about {abs(pct):.1f}% "
                  f"{'less' if diff < 0 else 'more'} than low-exposure cells' between the pre and post periods "
                  f"(Hedges' g = {hedges_g(hi, lo):.2f}). ")
    if reject and ci_excludes_zero:
        interp += ("The gap is statistically distinguishable from zero at the 5% level, and the "
                   "occupation-cluster bootstrap CI also excludes zero, so the result does not rest on "
                   "treating cells of the same occupation as independent.")
    elif reject:
        interp += ("The cell-level test rejects H0 at the 5% level, but the occupation-cluster bootstrap CI "
                   "includes zero, so the evidence weakens once within-occupation dependence is respected.")
    else:
        interp += ("The gap is not statistically distinguishable from zero at the 5% level"
                   + (" (the occupation-cluster bootstrap CI also includes zero)." if not ci_excludes_zero
                      else ", although the cluster bootstrap CI excludes zero; treat as inconclusive."))
    return GroupTestResult(
        outcome=value, h0=h0, h1=h1, alternative=alternative, n_high=int(hi.size), n_low=int(lo.size),
        mean_high=float(hi.mean()), mean_low=float(lo.mean()), diff=diff, diff_pct_points=float(pct),
        test_used=name, statistic=float(res.statistic), p_value=float(res.pvalue),
        hedges_g=hedges_g(hi, lo), cluster_ci_low=ci[0], cluster_ci_high=ci[1],
        mann_whitney_p=float(mw.pvalue), assumptions=a,
        decision="Reject H0" if reject else "Fail to reject H0", interpretation=interp)


def occupation_permutation_test(occ: pd.DataFrame, x: str = "exposure_main", y: str = "d_log_emp",
                                n_perm: int = 10000, alternative: str = "less", seed: int = 751) -> dict:
    """Permutation test of the Spearman correlation between exposure and change, n = occupations.

    Shuffles the exposure score across occupations, which needs no distributional assumption and
    respects that exposure is assigned at the occupation level.
    """
    d = occ[[x, y]].dropna()
    obs = stats.spearmanr(d[x], d[y]).statistic
    rng = np.random.default_rng(seed)
    xs = d[x].to_numpy()
    yr = stats.rankdata(d[y])
    perm = np.array([stats.spearmanr(rng.permutation(xs), yr).statistic for _ in range(n_perm)])
    if alternative == "less":
        p = (np.sum(perm <= obs) + 1) / (n_perm + 1)
    elif alternative == "greater":
        p = (np.sum(perm >= obs) + 1) / (n_perm + 1)
    else:
        p = (np.sum(np.abs(perm) >= abs(obs)) + 1) / (n_perm + 1)
    return {"n_occupations": int(len(d)), "spearman_rho": float(obs), "p_value": float(p),
            "alternative": alternative, "n_permutations": n_perm}


# ---------------------------------------------------------------- multivariate regression
@dataclass
class OLSResult:
    """Coefficient table and fit statistics from :func:`ols_cluster`."""
    table: pd.DataFrame
    n_obs: int
    n_clusters: int
    r2: float
    formula: str


def ols_cluster(df: pd.DataFrame, y: str, x: list[str], fixed_effects: list[str] | None = None,
                cluster: str = "soc_code") -> OLSResult:
    """OLS with optional categorical fixed effects and CR1 cluster-robust standard errors.

    Args:
        df: Data with the outcome, regressors, fixed-effect columns and cluster id.
        y: Outcome column.
        x: Regressors whose coefficients are reported.
        fixed_effects: Categorical columns absorbed as dummies (coefficients not reported).
        cluster: Cluster id; inference uses t with G - 1 degrees of freedom.

    Returns:
        :class:`OLSResult` with coef, se, t, p and 95% CI for each regressor in ``x``.
    """
    fixed_effects = fixed_effects or []
    d = df.dropna(subset=[y, *x, *fixed_effects, cluster]).copy()
    X = d[x].astype(float)
    for fe in fixed_effects:
        X = X.join(pd.get_dummies(d[fe], prefix=fe, drop_first=True, dtype=float))
    X.insert(0, "const", 1.0)
    Xm, yv = X.to_numpy(), d[y].to_numpy(float)
    xtx_inv = np.linalg.pinv(Xm.T @ Xm)
    beta = xtx_inv @ Xm.T @ yv
    resid = yv - Xm @ beta
    n, k = Xm.shape
    groups = d[cluster].to_numpy()
    uniq = np.unique(groups)
    G = len(uniq)
    meat = np.zeros((k, k))
    for g in uniq:
        s = Xm[groups == g].T @ resid[groups == g]
        meat += np.outer(s, s)
    corr = (G / (G - 1)) * ((n - 1) / (n - k))
    V = corr * xtx_inv @ meat @ xtx_inv
    se = np.sqrt(np.diag(V))
    tval = beta / se
    dof = G - 1
    p = 2 * stats.t.sf(np.abs(tval), dof)
    crit = stats.t.ppf(0.975, dof)
    tab = pd.DataFrame({"coef": beta, "se_cluster": se, "t": tval, "p_value": p,
                        "ci_low": beta - crit * se, "ci_high": beta + crit * se}, index=X.columns)
    r2 = 1 - resid.var() / yv.var()
    formula = f"{y} ~ {' + '.join(x)}" + (f" | FE: {', '.join(fixed_effects)}" if fixed_effects else "")
    return OLSResult(table=tab.loc[["const", *x]], n_obs=n, n_clusters=G, r2=float(r2), formula=formula)


def vif(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Variance inflation factors (multicollinearity check for the multivariate model)."""
    d = df[columns].dropna().astype(float)
    out = {}
    for c in columns:
        others = d.drop(columns=c)
        A = np.column_stack([np.ones(len(d)), others.to_numpy()])
        coef, *_ = np.linalg.lstsq(A, d[c].to_numpy(), rcond=None)
        r2 = 1 - np.var(d[c].to_numpy() - A @ coef) / np.var(d[c].to_numpy())
        out[c] = 1 / (1 - r2) if r2 < 1 else np.inf
    return pd.Series(out, name="VIF")
