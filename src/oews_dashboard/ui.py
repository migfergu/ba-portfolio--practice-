"""Streamlit helpers shared by every dashboard page.

Responsibilities kept here so pages stay short and declarative:

* cached loaders (keyed on file modification times, so rebuilding the database or re-running the
  model invalidates the cache without restarting the app);
* the global sidebar controls (outcome, inference method), persisted across page switches;
* the provenance banner and data-freshness caption shown on every page;
* graceful missing / empty states that tell the user which command fixes the problem.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from . import data_access as da

DEFAULTS = {"outcome_label": "Employment", "inference_label": next(iter(da.INFERENCE))}


# ----------------------------------------------------------------- formatting
def fmt_pct(x: float, digits: int = 1, sign: bool = True) -> str:
    """'-2.6%' style; 'n/a' for missing."""
    if x is None or pd.isna(x):
        return "n/a"
    return f"{x:+.{digits}f}%" if sign else f"{x:.{digits}f}%"


def fmt_p(p: float | None) -> str:
    """'p < 0.001' / 'p = 0.042' / 'n/a'."""
    if p is None or pd.isna(p):
        return "n/a"
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def fmt_time(iso: str | None) -> str:
    """'2026-10-29 11:19 UTC' from an ISO timestamp."""
    if not iso or iso == "unknown":
        return "unknown"
    return iso.replace("T", " ")[:16] + " UTC"


def show_figure(fig: plt.Figure) -> None:
    """Render a Matplotlib figure from the A5/A6 plotting modules and free its memory."""
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)


# ----------------------------------------------------------------- cached loaders
def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


@st.cache_data(show_spinner="Loading the analysis panel...")
def _cached_panel(db_path: str, mtime: float) -> pd.DataFrame:
    return da.load_panel(db_path)


@st.cache_data(show_spinner="Loading model results...")
def _cached_results(model_dir: str, mtimes: tuple[float, ...]) -> da.ModelResults:
    return da.load_results(model_dir)


@st.cache_data(show_spinner=False)
def _cached_provenance(model_dir: str, mtimes: tuple[float, ...], db_path: str, db_mtime: float) -> da.Provenance:
    return da.provenance(da.load_results(model_dir), db_path)


def _artifact_mtimes() -> tuple[float, ...]:
    return tuple(_mtime(da.resolve_model_dir() / f) for f in da.REQUIRED_ARTIFACTS)


def get_panel() -> pd.DataFrame | None:
    """The A5 analysis panel, or None when the database is missing or unreadable."""
    try:
        return _cached_panel(str(da.resolve_db()), _mtime(da.resolve_db()))
    except da.DataUnavailable:
        return None


def require_panel() -> pd.DataFrame:
    """The panel, or an explanatory error + one-click sample build, then stop the page."""
    try:
        return _cached_panel(str(da.resolve_db()), _mtime(da.resolve_db()))
    except da.DataUnavailable as exc:
        st.error(f"**{exc.what}.** This view reads the Assignment 4 database. "
                 f"Run `{exc.fix}` in the project folder, then refresh this page.")
        if exc.detail:
            st.caption(f"Detail: {exc.detail}")
        build_sample_button()
        st.stop()


def require_results() -> da.ModelResults:
    """The saved A6 results, or an explanatory error, then stop the page."""
    try:
        return _cached_results(str(da.resolve_model_dir()), _artifact_mtimes())
    except da.DataUnavailable as exc:
        st.error(f"**{exc.what}.** The dashboard shows saved Assignment 6 results and never re-estimates "
                 f"the model while you browse. Run `{exc.fix}` (about 3-4 minutes), then refresh.")
        if exc.detail:
            st.caption(f"Detail: {exc.detail}")
        st.stop()


def get_provenance(results: da.ModelResults) -> da.Provenance:
    return _cached_provenance(str(results.model_dir), _artifact_mtimes(), str(da.resolve_db()), _mtime(da.resolve_db()))


def build_sample_button() -> None:
    """Offer to build the database from the committed synthetic sample (no licensed data needed)."""
    if not da.SAMPLE_DIR.exists():
        return
    if st.button("Build the sample database now", type="primary",
                 help=f"Runs the Assignment 4 pipeline on data/sample/ (same as `{da.BUILD_DB_CMD}`)."):
        from oews_pipeline.pipeline import run_pipeline
        with st.spinner("Building data/processed/oews_genai.db from the synthetic sample..."):
            try:
                with tempfile.TemporaryDirectory() as tmp:   # do not overwrite the committed quality report
                    run_pipeline("sample", db_path=da.resolve_db(), report_md=None, report_json_dir=Path(tmp))
            except Exception as exc:  # noqa: BLE001 - surface any pipeline failure to the user
                st.error(f"The pipeline failed: {exc}. Run `{da.BUILD_DB_CMD}` in a terminal to see the full log.")
                return
        st.cache_data.clear()
        st.rerun()


# ----------------------------------------------------------------- sidebar controls
def _persist(widget_key: str, store_key: str) -> None:
    st.session_state[store_key] = st.session_state[widget_key]


def sidebar_controls() -> tuple[str, str]:
    """Global controls rendered once by the entrypoint; every page reads them via :func:`choices`."""
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)
    with st.sidebar:
        st.header("Show results for")
        outcomes = list(da.OUTCOMES)
        st.radio("Outcome", outcomes, index=outcomes.index(st.session_state["outcome_label"]),
                 key="_outcome_widget", on_change=_persist, args=("_outcome_widget", "outcome_label"),
                 help="Employment tests H1 (one-sided: beta < 0). Wages are two-sided.")
        infs = list(da.INFERENCE)
        st.radio("Uncertainty method", infs, index=infs.index(st.session_state["inference_label"]),
                 key="_inference_widget", on_change=_persist, args=("_inference_widget", "inference_label"),
                 help="With only 19 occupation clusters, the wild cluster bootstrap gives more reliable "
                      "intervals than the conventional cluster-robust t. Both are saved by Assignment 6.")
        st.caption("These choices apply to every page.")
    return choices()


def choices() -> tuple[str, str]:
    """(outcome key 'emp'|'wage', inference key 'wcr'|'cr1'), with safe defaults for invalid state."""
    o = st.session_state.get("outcome_label", DEFAULTS["outcome_label"])
    i = st.session_state.get("inference_label", DEFAULTS["inference_label"])
    return da.OUTCOMES.get(o, "emp"), da.INFERENCE.get(i, "wcr")


def inference_name(key: str) -> str:
    return "wild cluster bootstrap" if key == "wcr" else "CR1 cluster-robust t"


# ----------------------------------------------------------------- banner / footer
def provenance_banner(results: da.ModelResults) -> da.Provenance:
    """Synthetic-data warning, data-freshness caption and any provenance mismatch, on every page."""
    prov = get_provenance(results)
    if prov.is_sample:
        st.warning("**Synthetic sample.** These results come from the course-safe synthetic sample with a "
                   "planted employment effect and no wage effect. They show the method works; they are not "
                   "findings about the U.S. labor market. Licensed BLS/Eloundou/O*NET files are never committed.",
                   icon=":material/science:")
    if prov.inputs_match is False:
        st.error(f"**Results and database disagree.** Input files differ for: "
                 f"{', '.join(prov.mismatched_inputs) or 'unknown'}. Re-run `{da.BUILD_MODEL_CMD}` on this "
                 "database before relying on these numbers.")
    if not prov.outputs_intact:
        st.error(f"**Result files changed after the model run:** {', '.join(prov.changed_outputs)}. "
                 f"Re-run `{da.BUILD_MODEL_CMD}` to regenerate them.")
    check = ("inputs and outputs verified by SHA-256" if prov.verified
             else "database not built - inputs unverified" if prov.inputs_match is None else "verification failed")
    st.caption(f"Data: BLS OEWS May 2021-2025 ({prov.source_mode} mode) - Model results generated "
               f"{fmt_time(prov.model_generated_at)} (commit {prov.code_commit}) - Database built "
               f"{fmt_time(prov.etl_finished_at)} - {check}.")
    return prov


def limitations_note() -> None:
    st.caption("Read the full limitations, sample construction and data provenance on the "
               "**Data & limitations** page.")
