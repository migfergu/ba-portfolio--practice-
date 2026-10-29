"""A6 figures, in the A5 house style (Okabe-Ito colors, second encoding, takeaway-free neutral titles on the sample)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from oews_eda.plots import BLUE, GREY, ORANGE, _finish, set_style

ROLE_STYLE = {"main": (ORANGE, "D"), "comparison": (GREY, "s"), "robustness": (BLUE, "o"),
              "placebo": (GREY, "x")}


def plot_event_study(es: pd.DataFrame, planted: pd.DataFrame | None = None, path=None, source_mode=None,
                     outcome_label: str = "employment") -> plt.Figure:
    """Exposure-by-year coefficients (2022 = 0) with CR1 and WCR 95% intervals; planted path if given."""
    set_style()
    fig, ax = plt.subplots(figsize=(9, 5))
    e = es.sort_values("year")
    x = e["year"].to_numpy()
    ax.errorbar(x - 0.06, e["coef"] * 100, yerr=[(e["coef"] - e["ci_low_cr1"]) * 100, (e["ci_high_cr1"] - e["coef"]) * 100],
                fmt="o", color=BLUE, markersize=8, capsize=4, linewidth=1.8, label="Estimate, 95% CI (CR1, t with G-1 df)")
    if "ci_low_wcr" in e:
        ax.errorbar(x + 0.06, e["coef"] * 100, yerr=[(e["coef"] - e["ci_low_wcr"]) * 100, (e["ci_high_wcr"] - e["coef"]) * 100],
                    fmt="none", color=ORANGE, capsize=4, linewidth=1.8, linestyle="--",
                    label="95% CI (wild cluster bootstrap)")
    if planted is not None:
        p = planted.sort_values("year")
        ax.plot(p["year"], p["coef"] * 100, color=GREY, linestyle=":", marker="s", markersize=5,
                label="Planted by the synthetic generator (known answer)")
    ax.axhline(0, color=GREY, linewidth=1)
    ax.axvline(2022.5, color=GREY, linestyle=":", linewidth=1.2)
    ax.set_xticks(x)
    ax.set_title(f"Exposure-by-year coefficients for log {outcome_label} (2022 = 0)", pad=12)
    ax.set(xlabel="May reference year", ylabel="Log points x100 per 1 SD exposure")
    ax.legend(loc="lower left", fontsize=9)
    return _finish(fig, path, source_mode, foot_y=-0.04)


def plot_spec_forest(tab: pd.DataFrame, threshold: float, path=None, source_mode=None) -> plt.Figure:
    """Main, comparison and robustness coefficients with CR1 (solid) and WCR (dashed) intervals."""
    set_style()
    t = tab.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(t) + 1.6))
    for i, r in t.iterrows():
        color, marker = ROLE_STYLE.get(r["role"], (GREY, "o"))
        ax.plot([r["ci_low_cr1"] * 100, r["ci_high_cr1"] * 100], [i, i], color=color, linewidth=2)
        if pd.notna(r.get("ci_low_wcr")):
            ax.plot([r["ci_low_wcr"] * 100, r["ci_high_wcr"] * 100], [i - 0.18, i - 0.18], color=color,
                    linewidth=1.2, linestyle="--")
        ax.plot(r["coef"] * 100, i, marker=marker, color=color, markersize=8, linestyle="none")
    ax.axvline(0, color=GREY, linewidth=1)
    for s in (-1, 1):
        ax.axvline(s * threshold * 100, color=GREY, linestyle=":", linewidth=1)
    ax.set_yticks(range(len(t)))
    ax.set_yticklabels(t["label"], fontsize=9)
    ax.set_title("Exposure x post coefficient across specifications (log employment)", pad=12)
    ax.set_xlabel(f"Log points x100 per 1 SD exposure; dotted = +/-{threshold * 100:.0f} pt practical bar\n"
                  "solid = CR1 95% CI, dashed = wild cluster bootstrap 95% CI; diamond = A3 model")
    return _finish(fig, path, source_mode, foot_y=-0.07)


def plot_leave_one_out(loo: pd.DataFrame, main_coef: float, path=None, source_mode=None) -> plt.Figure:
    """Main coefficient when each industry / occupation is dropped in turn."""
    set_style()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True)
    for ax, (by, title) in zip(axes, [("naics_code", "Drop one industry"), ("soc_code", "Drop one occupation")]):
        d = loo[loo["dropped_by"] == by].dropna(subset=["coef"]).sort_values("coef")
        y = np.arange(len(d))
        ax.errorbar(d["coef"] * 100, y, xerr=1.96 * d["se_cr1"] * 100, fmt="o", color=BLUE, capsize=2, markersize=5)
        ax.axvline(main_coef * 100, color=ORANGE, linestyle="--", linewidth=1.5, label="Full sample")
        ax.axvline(0, color=GREY, linewidth=1)
        ax.set_yticks(y)
        ax.set_yticklabels(d["dropped"], fontsize=7)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Log points x100 per 1 SD exposure")
    axes[0].legend(loc="lower right", fontsize=8)
    fig.suptitle("Main coefficient with one industry or one occupation removed", fontweight="bold", fontsize=12)
    fig.tight_layout()
    return _finish(fig, path, source_mode, foot_y=-0.02)
