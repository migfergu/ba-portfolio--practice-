"""Publication-quality static figures for stakeholders (Matplotlib + Seaborn).

Accessibility rules applied to every figure:
* Okabe-Ito colorblind-safe hues, always paired with a second encoding (marker, line style or
  hatch), so each figure also reads in grayscale and print.
* Titles state the takeaway; axes carry units; legends sit outside the data where possible.
* One y-axis per panel (no dual axes); different measures go in separate panels.

Each function returns the Matplotlib ``Figure`` and, when ``path`` is given, saves a 300-dpi PNG.
Dashboard interactivity is deliberately left to Assignment 7.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

from .data import FOCAL_LABELS, REFERENCE_YEAR

# Okabe-Ito (validated: lightness band, chroma, CVD separation with secondary encoding)
BLUE, ORANGE, GREEN, PINK, GREY = "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#6B6B6B"
GROUP_STYLE = {  # color + marker + line style: identity never relies on color alone
    "High": {"color": ORANGE, "marker": "o", "linestyle": "-"},
    "Middle": {"color": GREY, "marker": "s", "linestyle": ":"},
    "Low": {"color": BLUE, "marker": "^", "linestyle": "--"},
    "analyst": {"color": BLUE, "marker": "o", "linestyle": "-"},
    "clerk_contrast": {"color": ORANGE, "marker": "s", "linestyle": "--"},
}


def set_style() -> None:
    """Apply the shared figure style (call once; every plotting function also calls it)."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight",
        "axes.titlesize": 13, "axes.titleweight": "bold", "axes.labelsize": 11,
        "axes.spines.top": False, "axes.spines.right": False, "grid.color": "#E6E6E6",
        "legend.frameon": False, "font.family": "DejaVu Sans"})


def fmt_p(p: float) -> str:
    """Format a p-value for display ('p < 0.001' instead of 'p = 0.0000')."""
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _finish(fig: plt.Figure, path: Path | str | None, source_mode: str | None, foot_y: float = -0.02) -> plt.Figure:
    """Add the data-source footnote (sample vs raw) and save if a path is given."""
    if source_mode:
        note = ("Source: BLS OEWS (May), Eloundou et al. (2024), O*NET 27.0 via A4 pipeline. "
                + ("SYNTHETIC SAMPLE - demonstrates the method; do not interpret values."
                   if source_mode == "sample" else "Real-data run."))
        fig.text(0.01, foot_y, note, fontsize=8, color="#555555", ha="left", va="top")
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path)
    return fig


# ---------------------------------------------------------------- data quality
def plot_coverage(coverage: pd.DataFrame, path=None, source_mode=None) -> plt.Figure:
    """Stacked bars per year: model-ready cells vs cells lost to suppression (data-quality view)."""
    set_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    years = coverage.index.astype(str)
    ready = coverage["emp_model_ready"]
    supp = coverage["emp_suppressed"]
    other = coverage["rows"] - ready - supp
    ax.bar(years, ready, color=BLUE, edgecolor="white", linewidth=2, label="Model-ready (employment + exposure)")
    ax.bar(years, supp, bottom=ready, color=ORANGE, hatch="//", edgecolor="white", linewidth=2,
           label="Employment suppressed by BLS (**)")
    ax.bar(years, other, bottom=ready + supp, color=GREY, hatch="..", edgecolor="white", linewidth=2,
           label="No exposure score")
    for x, (r, t) in enumerate(zip(ready, coverage["rows"])):
        ax.text(x, t + 1.5, f"{r / t:.0%} usable", ha="center", fontsize=9)
    ax.set(title="Most occupation x industry cells are usable in every year",
           xlabel="May reference year", ylabel="Occupation x industry cells")
    ax.set_ylim(0, coverage["rows"].max() * 1.32)
    ax.legend(loc="upper center", ncol=3, fontsize=8.5)
    return _finish(fig, path, source_mode)


# ---------------------------------------------------------------- univariate
def plot_exposure_distribution(occ: pd.DataFrame, median: float, path=None, source_mode=None) -> plt.Figure:
    """Histogram + rug of occupation-level exposure, with the median split and focal occupations marked."""
    set_style()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = occ["exposure_main"].dropna()
    ax.hist(x, bins=np.linspace(0, 1, 11), color=BLUE, edgecolor="white", linewidth=2, alpha=0.85,
            label="Occupations")
    ax.plot(x, np.full(len(x), -0.15), "|", color="#333333", markersize=12, label="Each occupation")
    ax.axvline(median, color=GREY, linestyle="--", linewidth=1.5, label=f"Median split ({median:.2f})")
    for role, marker in (("analyst", "o"), ("clerk_contrast", "s")):
        row = occ[occ["focal_role"] == role]
        if len(row):
            v = float(row["exposure_main"].iloc[0])
            ax.plot(v, 0.35, marker=marker, color=ORANGE, markersize=9, linestyle="none",
                    label=FOCAL_LABELS[role])
    ax.set(title="GenAI exposure is concentrated in office and analytical occupations",
           xlabel="Share of tasks exposed to GenAI (Eloundou et al. gamma, 0-1)", ylabel="Number of occupations",
           xlim=(0, 1))
    ax.set_ylim(bottom=-0.4)
    ax.legend(loc="upper left", fontsize=9)
    return _finish(fig, path, source_mode)


def plot_outcome_distributions(panel: pd.DataFrame, path=None, source_mode=None) -> plt.Figure:
    """Raw vs log distributions of employment and wages: justifies modeling outcomes in logs."""
    set_style()
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    spec = [("tot_emp", "Employment (jobs)", BLUE), ("log_emp", "log(employment)", BLUE),
            ("a_mean", "Mean annual wage ($)", GREEN), ("log_wage", "log(mean annual wage)", GREEN)]
    for ax, (col, label, color) in zip(axes.flat, spec):
        x = panel[col].dropna()
        ax.hist(x, bins=25, color=color, edgecolor="white", linewidth=1.5)
        ax.set(xlabel=label, ylabel="Cells (all years)",
               title=f"{label}: skew = {stats.skew(x):.2f}")
        ax.title.set_fontsize(11)
        if col == "a_mean":
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5))
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v / 1000:.0f}k"))
        elif col == "tot_emp":
            ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k"))
    fig.suptitle("Logs remove the long right tail in employment, so outcomes are modeled in logs",
                 fontweight="bold", fontsize=13)
    fig.tight_layout()
    return _finish(fig, path, source_mode)


# ---------------------------------------------------------------- bivariate
def plot_exposure_vs_change(cells: pd.DataFrame, occ: pd.DataFrame, value: str = "d_log_emp",
                            path=None, source_mode=None) -> plt.Figure:
    """Cell-level scatter of pre->post change vs exposure, occupation means overlaid, OLS fit line."""
    set_style()
    fig, ax = plt.subplots(figsize=(8.5, 5))
    d = cells.dropna(subset=[value, "exposure_main"])
    ax.scatter(d["exposure_main"], d[value] * 100, s=28, color=BLUE, alpha=0.45, marker="o",
               edgecolor="white", linewidth=0.6, label="Occupation x industry cell")
    o = occ.dropna(subset=[value])
    ax.scatter(o["exposure_main"], o[value] * 100, s=80, color=ORANGE, marker="D", edgecolor="white",
               linewidth=1.5, zorder=3, label="Occupation (employment-weighted)")
    slope, intercept, *_ = stats.linregress(d["exposure_main"], d[value] * 100)
    xs = np.linspace(d["exposure_main"].min(), d["exposure_main"].max(), 50)
    ax.plot(xs, intercept + slope * xs, color="#222222", linestyle="--", linewidth=2,
            label=f"Linear fit: {slope / 10:+.1f} pts per +0.1 exposure")
    for role in ("analyst", "clerk_contrast"):
        r = o[o["focal_role"] == role]
        if len(r):
            ax.annotate(FOCAL_LABELS[role].split(" (")[0], (r["exposure_main"].iloc[0], r[value].iloc[0] * 100),
                        xytext=(10, 14) if role == "analyst" else (14, -22), textcoords="offset points", fontsize=9,
                        arrowprops={"arrowstyle": "-", "color": "#555555"})
    ax.axhline(0, color="#999999", linewidth=1)
    what = "employment" if "emp" in value else "mean wage"
    ax.set(title=f"Occupations with higher predicted GenAI exposure: slower {what} growth after 2022",
           xlabel="Share of tasks exposed to GenAI (0-1)",
           ylabel=f"Change in log {what}, post vs pre (x100 = approx. %)")
    ax.legend(loc="lower left", fontsize=9)
    return _finish(fig, path, source_mode)


def plot_trend_index(trend: pd.DataFrame, outcome_label: str = "Employment", path=None,
                     source_mode=None) -> plt.Figure:
    """Indexed (2022 = 100) trend by exposure group on a balanced panel, with the ChatGPT line."""
    set_style()
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for grp in ("Low", "Middle", "High"):
        t = trend[trend["group"] == grp]
        if t.empty:
            continue
        st = GROUP_STYLE[grp]
        ax.plot(t["year"], t["index"], linewidth=2, markersize=8, label=f"{grp} exposure (n = {t['n_cells'].iat[0]} cells)",
                **st)
        ax.annotate(grp, (t["year"].iat[-1], t["index"].iat[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=10, color="#222222")
    ax.axvline(REFERENCE_YEAR + 0.5, color=GREY, linestyle=":", linewidth=1.5)
    ax.text(REFERENCE_YEAR + 0.55, ax.get_ylim()[1], "ChatGPT release\n(Nov 2022)", va="top", fontsize=9, color="#444444")
    ax.axhline(100, color="#BBBBBB", linewidth=1)
    ax.set(title=f"{outcome_label} paths split after 2022 by GenAI exposure",
           xlabel="May reference year", ylabel=f"{outcome_label} index (2022 = 100)")
    ax.set_xticks(sorted(trend["year"].unique()))
    ax.set_xlim(trend["year"].min() - 0.3, trend["year"].max() + 0.6)
    ax.legend(loc="upper left", fontsize=9)
    return _finish(fig, path, source_mode)


# ---------------------------------------------------------------- multivariate
def plot_correlation_heatmap(corr: pd.DataFrame, labels: dict[str, str] | None = None, path=None,
                             source_mode=None) -> plt.Figure:
    """Annotated Spearman correlation heatmap (diverging, gray midpoint; numbers make it grayscale-safe)."""
    set_style()
    c = corr.rename(index=labels or {}, columns=labels or {})
    mask = np.triu(np.ones_like(c, dtype=bool), k=1)
    fig, ax = plt.subplots(figsize=(8, 6.5))
    sns.heatmap(c, mask=mask, annot=True, fmt=".2f", cmap="vlag", vmin=-1, vmax=1, center=0, square=True,
                linewidths=2, linecolor="white", cbar_kws={"label": "Spearman rank correlation", "shrink": 0.8},
                annot_kws={"fontsize": 10}, ax=ax)
    ax.set_title("How exposure, preparation, pay and size relate across cells")
    ax.tick_params(axis="x", rotation=35)
    plt.setp(ax.get_xticklabels(), ha="right")
    return _finish(fig, path, source_mode, foot_y=-0.12)


def plot_coefficients(table: pd.DataFrame, labels: dict[str, str] | None = None, title: str = "",
                      path=None, source_mode=None) -> plt.Figure:
    """Dot-and-whisker plot of regression coefficients with 95% cluster-robust CIs."""
    set_style()
    t = table.drop(index="const", errors="ignore").iloc[::-1]
    names = [(labels or {}).get(i, i) for i in t.index]
    fig, ax = plt.subplots(figsize=(8, 0.9 * len(t) + 1.8))
    ax.errorbar(t["coef"] * 100, names, xerr=[(t["coef"] - t["ci_low"]) * 100, (t["ci_high"] - t["coef"]) * 100],
                fmt="o", color=BLUE, ecolor=BLUE, elinewidth=2, capsize=5, markersize=9)
    ax.axvline(0, color=GREY, linestyle="--")
    for y, (_, r) in enumerate(t.iterrows()):
        ax.text(r["ci_high"] * 100, y + 0.18, f" {r['coef'] * 100:+.2f} ({fmt_p(r['p_value'])})", fontsize=9)
    ax.set(title=title or "Exposure association with employment change holds after controls",
           xlabel="Association with change in log employment (x100 = approx. % points), 95% CI clustered by occupation")
    ax.set_ylim(-0.6, len(t) - 0.4)
    return _finish(fig, path, source_mode)


# ---------------------------------------------------------------- hypothesis test
def plot_group_test(cells: pd.DataFrame, value: str, result, path=None, source_mode=None) -> plt.Figure:
    """Box + strip plot of the two groups beside Q-Q plots (visual assumption check)."""
    set_style()
    d = cells.dropna(subset=[value, "exposure_group"]).copy()
    d["pct"] = d[value] * 100
    fig = plt.figure(figsize=(11, 4.8))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.6, 1, 1])
    ax = fig.add_subplot(gs[:, 0])
    order = ["Low", "High"]
    sns.boxplot(data=d, x="exposure_group", y="pct", order=order, width=0.5, showfliers=False,
                palette={"Low": BLUE, "High": ORANGE}, hue="exposure_group", legend=False,
                boxprops={"alpha": 0.35}, ax=ax)
    sns.stripplot(data=d, x="exposure_group", y="pct", order=order, hue="exposure_group",
                  palette={"Low": BLUE, "High": ORANGE}, legend=False, size=4, jitter=0.18, alpha=0.7, ax=ax)
    means = d.groupby("exposure_group")["pct"].mean()
    for i, g in enumerate(order):
        ax.plot(i, means[g], marker="D", color="#222222", markersize=9, zorder=4)
        ax.text(i + 0.28, means[g], f"mean {means[g]:+.1f}", va="center", fontsize=9)
    what = "employment" if "emp" in value else "mean wage"
    wi = ", relative to industry mean" if value.endswith("_wi") else ""
    ax.set(xlabel="Occupation GenAI exposure (median split)",
           ylabel=f"Change in log {what}, post vs pre{wi} (x100)",
           title=f"{result.test_used}: {fmt_p(result.p_value)}, Hedges' g = {result.hedges_g:.2f}")
    ax.title.set_fontsize(11)
    for k, g in enumerate(order):
        q = fig.add_subplot(gs[k, 1])
        (osm, osr), (sl, ic, _) = stats.probplot(d.loc[d["exposure_group"] == g, "pct"], dist="norm")
        q.scatter(osm, osr, s=14, color=GROUP_STYLE[g]["color"], marker=GROUP_STYLE[g]["marker"])
        q.plot(osm, sl * osm + ic, color="#222222", linewidth=1.2)
        q.set_title(f"Q-Q: {g} exposure", fontsize=10)
        q.set_xlabel("Theoretical quantile", fontsize=9)
        q.set_ylabel("Observed", fontsize=9)
    a = result.assumptions
    txt = (f"Assumption checks\n\nShapiro-Wilk p\n  High: {a['shapiro_a_p']:.3f}\n  Low:  {a['shapiro_b_p']:.3f}\n\n"
           f"Levene p: {a['levene_p']:.3f}\n\nTest used: {result.test_used}\nMann-Whitney {fmt_p(result.mann_whitney_p)}\n"
           f"Cluster-bootstrap 95% CI\n  [{result.cluster_ci_low * 100:+.2f}, {result.cluster_ci_high * 100:+.2f}]")
    t = fig.add_subplot(gs[:, 2])
    t.axis("off")
    t.text(0, 1, txt, va="top", fontsize=9.5, family="DejaVu Sans Mono")
    fig.suptitle(f"Hypothesis test: did high-exposure cells' {what} grow less?", fontweight="bold", fontsize=13)
    fig.tight_layout()
    return _finish(fig, path, source_mode)


def plot_focal_contrast(contrast: pd.DataFrame, path=None, source_mode=None) -> plt.Figure:
    """Two panels (employment, wage), each indexed 2022 = 100: analysts vs clerks. Descriptive only."""
    set_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharex=True)
    for ax, col, label in ((axes[0], "emp_index", "Employment"), (axes[1], "wage_index", "Mean annual wage")):
        for role in ("analyst", "clerk_contrast"):
            t = contrast[contrast["focal_role"] == role]
            if t.empty:
                continue
            ax.plot(t["year"], t[col], linewidth=2, markersize=8,
                    label=f"{FOCAL_LABELS[role]} - {t['n_industries'].iat[0]} industries", **GROUP_STYLE[role])
        ax.axhline(100, color="#BBBBBB", linewidth=1)
        ax.axvline(REFERENCE_YEAR + 0.5, color=GREY, linestyle=":", linewidth=1.5)
        ax.set(title=label, xlabel="May reference year", ylabel=f"{label} index (2022 = 100)")
        ax.set_xticks(sorted(contrast["year"].unique()))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Finance contrast (descriptive): analysts vs bookkeeping clerks", fontweight="bold", fontsize=13)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=9, bbox_to_anchor=(0.5, 0.0))
    return _finish(fig, path, source_mode, foot_y=-0.03)


def plot_attrition(attrition: pd.DataFrame, path=None, source_mode=None) -> plt.Figure:
    """Horizontal bars: rows / cells surviving each filter and merge, source file to analysis sample."""
    set_style()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    a = attrition.iloc[::-1].reset_index(drop=True)
    colors = [GREEN if u == "cells" else BLUE for u in a["unit"]]
    hatches = ["//" if u == "cells" else "" for u in a["unit"]]
    bars = ax.barh(a["stage"], a["n"], color=colors, edgecolor="white", linewidth=2)
    for b, h in zip(bars, hatches):
        b.set_hatch(h)
    for y, (n, u) in enumerate(zip(a["n"], a["unit"])):
        ax.text(n + a["n"].max() * 0.01, y, f"{n:,} {u}", va="center", fontsize=9)
    ax.set(title="From source file to analysis sample: what survives each step",
           xlabel="Count (rows: occupation x industry x year; cells: occupation x industry)")
    ax.set_xlim(0, a["n"].max() * 1.18)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="Rows"), Patch(facecolor=GREEN, hatch="//", edgecolor="white", label="Cells")],
              loc="lower right")
    return _finish(fig, path, source_mode)


def plot_event_time_gaps(gaps: pd.DataFrame, vintage: pd.DataFrame, path=None, source_mode=None,
                         outcome_label: str = "employment") -> plt.Figure:
    """Year-by-year High-minus-Low gap (within industry, 2022 = 0) with cluster CIs and the share of
    each May estimate's six pooled survey panels collected after ChatGPT's release."""
    set_style()
    fig, ax = plt.subplots(figsize=(9, 5))
    g = gaps.sort_values("year")
    ax.fill_between(g["year"], g["ci_low"] * 100, g["ci_high"] * 100, color=BLUE, alpha=0.15,
                    label="95% CI (occupation-cluster bootstrap)")
    ax.plot(g["year"], g["gap"] * 100, color=BLUE, marker="o", markersize=9, linewidth=2,
            label="High minus Low exposure, within industry")
    ax.axhline(0, color=GREY, linewidth=1.2, linestyle="--")
    ax.axvline(REFERENCE_YEAR + 0.5, color=GREY, linestyle=":", linewidth=1.5)
    lo = min(g["ci_low"].min() * 100, -1)
    ax.set_ylim(lo * 1.2, max(g["ci_high"].max() * 100, 1) + 1.5)
    ticks = [int(y) for y in g["year"]]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{y}\n{vintage.loc[y, 'post_chatgpt_panels']}/6 panels post" if y in vintage.index else str(y)
                        for y in ticks])
    ax.set(title=f"The {outcome_label} gap opens as more post-ChatGPT survey panels enter the estimates",
           xlabel="May reference year, and how many of its 6 pooled survey panels post-date ChatGPT (2022 = 0)",
           ylabel=f"Gap in change in log {outcome_label} since 2022 (x100)")
    ax.legend(loc="upper right", fontsize=9)
    return _finish(fig, path, source_mode, foot_y=-0.06)
