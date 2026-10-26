"""Exploratory data analysis (BUS 751, Assignment 5) for the GenAI-exposure OEWS panel.

The package reads the SQLite database built by ``oews_pipeline`` (Assignment 4) and provides
reusable, documented functions for data-quality validation, univariate / bivariate /
multivariate description, hypothesis testing, and stakeholder-ready figures.

Typical use (see ``notebooks/02_eda.ipynb``)::

    from oews_eda import data, describe, inference, plots
    panel = data.load_panel()                 # v_analysis_panel + derived columns
    cells = describe.cell_changes(panel)      # pre -> post change per occupation x industry cell
    result = inference.exposure_group_test(cells, "d_log_emp", alternative="less")

Modules
-------
data       connection, panel loading, derived variables, data-quality checks
describe   univariate, bivariate and multivariate summaries
inference  hypothesis tests, assumption checks, effect sizes, cluster-robust OLS
plots      publication-quality static Matplotlib/Seaborn figures (colorblind-safe)
report     one-call runner that writes all figures, tables and a JSON summary
"""
__version__ = "0.2.0"

from . import data, describe, inference, plots, report  # noqa: E402,F401

__all__ = ["data", "describe", "inference", "plots", "report"]
