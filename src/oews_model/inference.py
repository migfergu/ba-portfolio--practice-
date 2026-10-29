"""Small-cluster inference for the fixed-effects estimates.

The panel has about 19 occupation clusters. CR1 standard errors with t(G-1) critical values can
over-reject with so few clusters (Cameron, Gelbach & Miller 2008; MacKinnon & Webb 2018), so each
headline coefficient also gets:

* **Wild cluster restricted bootstrap (WCR)**: residuals from the model with the null imposed are
  multiplied by one Webb six-point weight per occupation; the p-value compares the observed CR1
  t-statistic with its bootstrap distribution. The 95% interval is the set of null values not rejected
  at 5% (test inversion, common random weights across nulls).
* **Randomization inference (RI)**: exposure scores are reassigned at random across occupations, which
  keeps industry, cell and year structure fixed; the p-value is the share of reassignments with a
  coefficient at least as far from zero as the observed one. It tests the sharp null that exposure is
  unrelated to the outcome path and needs no large-G approximation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .estimate import FEData, FEResult, absorb

WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])


def _weights(G: int, B: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).choice(WEBB, size=(G, B))


def _t_stats(fd: FEData, j: int, b0: float, W: np.ndarray, chunk: int = 2000) -> tuple[float, np.ndarray]:
    """Observed and WCR bootstrap t-statistics for H0: beta_j = b0."""
    X, y, cl, G, n = fd.X, fd.y, fd.clusters, fd.G, fd.n
    k = X.shape[1] + fd.n_absorbed_unnested
    c = G / (G - 1) * (n - 1) / (n - k)
    xtx_inv = np.linalg.inv(X.T @ X)
    A = xtx_inv @ X.T                      # beta = A y
    h = X @ xtx_inv[j]                     # var_j = c * sum_g (sum_{i in g} h_i u_i)^2

    def t_of(Y: np.ndarray) -> np.ndarray:
        beta = A @ Y
        U = Y - X @ beta
        s = np.zeros((G, Y.shape[1]))
        np.add.at(s, cl, h[:, None] * U)
        return (beta[j] - b0) / np.sqrt(c * (s ** 2).sum(axis=0))

    t_obs = float(t_of(y[:, None])[0])
    # restricted model: impose beta_j = b0, re-estimate the other coefficients
    others = [i for i in range(X.shape[1]) if i != j]
    y_r = y - b0 * X[:, j]
    if others:
        Xo = X[:, others]
        br = np.linalg.lstsq(Xo, y_r, rcond=None)[0]
        fitted_r = Xo @ br
    else:
        fitted_r = np.zeros(n)
    u_r = y_r - fitted_r
    base = fitted_r + b0 * X[:, j]
    out = []
    for s in range(0, W.shape[1], chunk):
        Wc = W[:, s:s + chunk]
        out.append(t_of(base[:, None] + u_r[:, None] * Wc[cl]))
    return t_obs, np.concatenate(out)


def wild_cluster_bootstrap(res: FEResult, term: str | None = None, B: int = 9999, seed: int = 751,
                           alpha: float = 0.05, ci: bool = True) -> dict[str, float]:
    """WCR bootstrap p-values (two-sided and lower-tail) and, optionally, the test-inversion CI.

    Returns:
        dict with ``p_wcr`` (two-sided), ``p_wcr_lower`` (H1: beta < 0), ``ci_low_wcr``, ``ci_high_wcr``.
    """
    fd = res.data
    j = fd.names.index(term or fd.names[0])
    W = _weights(fd.G, B, seed)
    t_obs, t_b = _t_stats(fd, j, 0.0, W)
    out = {"p_wcr": float((np.abs(t_b) >= abs(t_obs)).mean()),
           "p_wcr_lower": float((t_b <= t_obs).mean())}
    if ci:
        beta, se = res.table.iloc[j]["coef"], res.table.iloc[j]["se"]

        def p_at(b0: float) -> float:
            t0, tb = _t_stats(fd, j, b0, W)
            return float((np.abs(tb) >= abs(t0)).mean())

        def edge(direction: int) -> float:
            inside, outside = beta, beta + direction * 2 * se
            for _ in range(20):                       # widen until rejected
                if p_at(outside) < alpha:
                    break
                inside, outside = outside, outside + direction * 2 * se
            else:
                return float("nan")
            for _ in range(30):                       # bisection
                mid = (inside + outside) / 2
                if p_at(mid) < alpha:
                    outside = mid
                else:
                    inside = mid
                if abs(outside - inside) < 1e-4 * max(se, 1e-8):
                    break
            return float((inside + outside) / 2)

        out["ci_low_wcr"], out["ci_high_wcr"] = edge(-1), edge(+1)
    return out


def randomization_inference(df: pd.DataFrame, res: FEResult, build_x, n_perm: int = 4999,
                            seed: int = 751, cluster: str = "soc_code") -> dict[str, float]:
    """Permutation p-value from reassigning exposure across occupations.

    Args:
        df: The rows actually used in ``res`` (``res.data.frame``).
        build_x: function(frame_with_permuted_exposure) -> 1-D array of the tested regressor.
            Only the first (tested) regressor is permuted; any others are held fixed.

    Returns:
        ``p_ri`` (two-sided), ``p_ri_lower`` (H1: beta < 0) and ``n_perm``; p-values are
        (count + 1) / (n_perm + 1), so the smallest reportable value is 1 / (n_perm + 1).
    """
    fd = res.data
    d = df.reset_index(drop=True)
    occ = d[[cluster, "exposure_z"]].drop_duplicates(cluster)
    rng = np.random.default_rng(seed)
    fe_cols = res.fixed_effects
    groups = [pd.factorize(d[fe])[0] for fe in fe_cols]
    cols = []
    for _ in range(n_perm):
        perm = dict(zip(occ[cluster], rng.permutation(occ["exposure_z"].to_numpy())))
        dp = d.assign(exposure_z=d[cluster].map(perm))
        cols.append(build_x(dp))
    Xp = np.column_stack(cols)
    Xp = absorb(Xp, groups) if groups else Xp - Xp.mean(axis=0)
    others = fd.X[:, 1:]
    if others.shape[1]:                               # partial out the other regressors (FWL)
        P = others @ np.linalg.lstsq(others, Xp, rcond=None)[0]
        Xp = Xp - P
        yv = fd.y - others @ np.linalg.lstsq(others, fd.y, rcond=None)[0]
    else:
        yv = fd.y
    b_perm = (Xp * yv[:, None]).sum(axis=0) / (Xp ** 2).sum(axis=0)
    b_obs = res.coef()
    # (count + 1) / (n_perm + 1): the observed assignment counts as one draw, so p is never exactly 0
    n_two = int((np.abs(b_perm) >= abs(b_obs) - 1e-12).sum())
    n_low = int((b_perm <= b_obs + 1e-12).sum())
    return {"p_ri": (n_two + 1) / (n_perm + 1), "p_ri_lower": (n_low + 1) / (n_perm + 1), "n_perm": n_perm}
