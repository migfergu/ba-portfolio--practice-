"""Two-way fixed-effects estimator for the A3 specification.

    log(Y_oit) = alpha_oi + delta_it + beta * (Exposure_o x Post_t) + e_oit

alpha_oi are occupation-by-industry (cell) effects, delta_it industry-by-year effects; Exposure_o is the
occupation's standardized GenAI exposure (``exposure_z``, 1 SD = 1). Both sets of effects are absorbed by
alternating projections (the method behind Stata's reghdfe / R's fixest), so the regressors of interest
are estimated by OLS on the doubly demeaned data (Frisch-Waugh-Lovell). Standard errors are CR1
cluster-robust by occupation with t(G - 1) reference distribution; ``inference.py`` adds a wild cluster
bootstrap and randomization inference for the small number of clusters.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


class ModelError(ValueError):
    """Raised when a specification cannot be estimated on the data supplied (empty, singular, too few clusters)."""


MIN_CLUSTERS = 10   # below this, refuse: no cluster-robust method is reliable


def absorb(values: np.ndarray, groups: list[np.ndarray], tol: float = 1e-12, max_iter: int = 10_000) -> np.ndarray:
    """Remove several sets of fixed effects from each column of ``values`` by alternating projections.

    Args:
        values: (n, m) array; each column is demeaned.
        groups: integer-coded group ids, one array of length n per fixed-effect dimension.

    Returns:
        Residuals of each column on all fixed effects jointly (the FWL "within" transform).
    """
    v = np.asarray(values, float).copy()
    if v.ndim == 1:
        v = v[:, None]
    counts = [np.bincount(g) for g in groups]
    for _ in range(max_iter):
        prev = v.copy()
        for g, c in zip(groups, counts):
            sums = np.zeros((c.size, v.shape[1]))
            np.add.at(sums, g, v)
            v -= (sums / np.maximum(c, 1)[:, None])[g]
        if np.max(np.abs(v - prev)) < tol:
            return v
    raise ModelError("fixed-effect absorption did not converge")


@dataclass
class FEData:
    """Doubly demeaned outcome and regressors, ready for OLS and for the bootstraps."""
    y: np.ndarray
    X: np.ndarray
    names: list[str]
    clusters: np.ndarray          # integer cluster codes (occupation)
    cluster_labels: np.ndarray
    n_absorbed_unnested: int      # FE levels not nested in clusters (count toward the small-sample k)
    frame: pd.DataFrame           # rows used, for diagnostics

    @property
    def n(self) -> int:
        return len(self.y)

    @property
    def G(self) -> int:
        return len(self.cluster_labels)


def prepare(df: pd.DataFrame, y: str, x: list[str], fixed_effects: list[str],
            cluster: str = "soc_code") -> FEData:
    """Drop incomplete rows and singletons, absorb fixed effects, and code clusters.

    Singleton groups (a cell observed once) are dropped iteratively: they are fit perfectly by their
    own effect, carry no information about beta, and would overstate the degrees of freedom.

    Raises:
        ModelError: if fewer than ``MIN_CLUSTERS`` clusters remain, no rows remain, or a regressor
            has no within variation after the fixed effects are removed.
    """
    d = df.dropna(subset=[y, *x, *fixed_effects, cluster]).copy()
    while fixed_effects:
        keep = np.ones(len(d), bool)
        for fe in fixed_effects:
            keep &= d.groupby(fe)[fe].transform("size").to_numpy() > 1
        if keep.all():
            break
        d = d[keep]
    if d.empty:
        raise ModelError(f"no complete rows for {y} ~ {x}")
    labels, codes = np.unique(d[cluster].to_numpy(), return_inverse=True)
    if len(labels) < MIN_CLUSTERS:
        raise ModelError(f"only {len(labels)} clusters ({cluster}); need at least {MIN_CLUSTERS}")
    groups = [pd.factorize(d[fe])[0] for fe in fixed_effects]
    yv = d[y].to_numpy(float)
    Xv = d[x].to_numpy(float)
    if groups:
        Z = absorb(np.column_stack([yv, Xv]), groups)
        yv, Xv = Z[:, 0], Z[:, 1:]
    else:
        yv = yv - yv.mean()
        Xv = Xv - Xv.mean(axis=0)
    if np.any(np.abs(Xv).max(axis=0) < 1e-10):
        bad = [n for n, s in zip(x, np.abs(Xv).max(axis=0)) if s < 1e-10]
        raise ModelError(f"no variation left in {bad} after fixed effects")
    # Fixed effects nested in the cluster (cells sit inside occupations) do not count toward k (Stata rule).
    unnested = 0
    for fe in fixed_effects:
        nested = (d.groupby(fe)[cluster].nunique() == 1).all()
        if not nested:
            unnested += d[fe].nunique() - 1
    return FEData(yv, Xv, list(x), codes, labels, unnested + 1, d)


def _cluster_scores(X: np.ndarray, u: np.ndarray, clusters: np.ndarray, G: int) -> np.ndarray:
    """(G, k) matrix of per-cluster scores X_g' u_g."""
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, clusters, X * u[:, None])
    return S


@dataclass
class FEResult:
    """Coefficients with CR1 cluster-robust inference for one specification."""
    label: str
    outcome: str
    table: pd.DataFrame
    n_obs: int
    n_cells: int
    n_clusters: int
    r2_within: float
    vcov: np.ndarray
    data: FEData = field(repr=False)
    fixed_effects: list[str] = field(default_factory=list)
    notes: dict = field(default_factory=dict)

    def coef(self, name: str | None = None) -> float:
        return float(self.table.loc[name or self.table.index[0], "coef"])

    def row(self, name: str | None = None) -> dict:
        """Flat record for the result tables (one regressor)."""
        name = name or self.table.index[0]
        r = self.table.loc[name]
        return {"spec": self.label, "outcome": self.outcome, "term": name, "coef": r["coef"],
                "se_cr1": r["se"], "t": r["t"], "p_cr1": r["p"], "ci_low_cr1": r["ci_low"],
                "ci_high_cr1": r["ci_high"], "pct_effect": (np.exp(r["coef"]) - 1) * 100,
                "n_obs": self.n_obs, "n_cells": self.n_cells, "n_clusters": self.n_clusters,
                "r2_within": self.r2_within, **self.notes}


def fit(df: pd.DataFrame, y: str, x: list[str], fixed_effects: list[str], cluster: str = "soc_code",
        label: str = "", alpha: float = 0.05) -> FEResult:
    """Estimate ``y ~ x`` absorbing ``fixed_effects``, with CR1 standard errors clustered on ``cluster``.

    Small-sample factor: G/(G-1) * (n-1)/(n-k), where k counts the reported regressors plus the fixed
    effects not nested within clusters. Reference distribution: t with G - 1 degrees of freedom.
    """
    fd = prepare(df, y, x, fixed_effects, cluster)
    X, yv = fd.X, fd.y
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ yv
    u = yv - X @ beta
    S = _cluster_scores(X, u, fd.clusters, fd.G)
    k = X.shape[1] + fd.n_absorbed_unnested
    c = fd.G / (fd.G - 1) * (fd.n - 1) / (fd.n - k)
    V = c * xtx_inv @ (S.T @ S) @ xtx_inv
    se = np.sqrt(np.diag(V))
    dof = fd.G - 1
    crit = stats.t.ppf(1 - alpha / 2, dof)
    tval = beta / se
    tab = pd.DataFrame({"coef": beta, "se": se, "t": tval, "p": 2 * stats.t.sf(np.abs(tval), dof),
                        "ci_low": beta - crit * se, "ci_high": beta + crit * se}, index=x)
    r2w = 1 - (u @ u) / (yv @ yv) if yv @ yv > 0 else np.nan
    cell_col = "cell_id" if "cell_id" in fd.frame else None
    return FEResult(label, y, tab, fd.n, fd.frame[cell_col].nunique() if cell_col else fd.n, fd.G,
                    float(r2w), V, fd, list(fixed_effects))
