"""Stakeholder dashboard (BUS 751, Assignment 7) for the GenAI-exposure OEWS study.

The package has two layers:

data_access  Streamlit-free, documented data-access layer. Reads the A4 SQLite database through the
             A5 loader (``oews_eda.data``), reuses A5 descriptive functions (``oews_eda.describe``),
             and reads the saved A6 result artifacts in ``reports/model/``. It never re-estimates
             the fixed-effects model, so every number on screen traces to a committed artifact.
ui           Streamlit helpers shared by every page: cached loaders, sidebar controls, the
             data-provenance banner and the empty / missing-data states.

Launch with ``uv run streamlit run streamlit_app.py`` (see docs/APP_GUIDE.md).
"""
import matplotlib

# Non-interactive backend: figures are rendered to images for Streamlit. Without this, Windows defaults to
# the Tk GUI backend, which fails when Streamlit (or AppTest) draws from a worker thread.
matplotlib.use("Agg")

__version__ = "0.7.1"
