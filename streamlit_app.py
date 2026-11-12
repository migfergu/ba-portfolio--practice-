"""BUS 751 Assignment 7 dashboard entrypoint.

Launch:  uv run streamlit run streamlit_app.py

Defines page navigation and the sidebar controls shared by every page. The pages live in
``app_pages/``; data access and shared UI helpers live in ``src/oews_dashboard/``.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:          # works with or without the editable install
    sys.path.insert(0, str(ROOT / "src"))

import streamlit as st

from oews_dashboard import ui

st.set_page_config(page_title="GenAI Exposure & Jobs", page_icon=":material/insights:", layout="wide")

PAGES = [
    st.Page("app_pages/1_answer.py", title="The answer", icon=":material/insights:", default=True),
    st.Page("app_pages/2_robustness.py", title="Is it robust?", icon=":material/fact_check:"),
    st.Page("app_pages/3_explorer.py", title="Occupation explorer", icon=":material/travel_explore:"),
    st.Page("app_pages/4_data_limitations.py", title="Data & limitations", icon=":material/info:"),
]

navigation = st.navigation(PAGES)
ui.sidebar_controls()
with st.sidebar:
    st.divider()
    st.caption("BUS 751 - Miguel L. Ferguson II - University of South Alabama. "
               "Setup and interpretation: docs/APP_GUIDE.md")
navigation.run()
