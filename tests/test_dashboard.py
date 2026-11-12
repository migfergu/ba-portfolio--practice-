"""A7 dashboard tests: data-access layer (always) and Streamlit AppTest smoke tests (when streamlit is installed).

The smoke tests load the entrypoint and every page in a headless Streamlit runtime and fail on any
uncaught exception. They also exercise the empty-filter, missing-database and missing-results states.
A fresh sample database is built in a temporary folder and passed via $OEWS_DB_PATH, so the tests
never touch data/processed/.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from oews_dashboard import data_access as da

REPO = Path(__file__).resolve().parents[1]
ENTRY = REPO / "streamlit_app.py"
PAGES = sorted((REPO / "app_pages").glob("*.py"))
TIMEOUT = 120


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    from oews_pipeline.pipeline import run_pipeline
    tmp = tmp_path_factory.mktemp("dash")
    path = tmp / "oews_genai.db"
    run_pipeline("sample", db_path=path, report_md=None, report_json_dir=tmp)
    return path


@pytest.fixture(scope="module")
def results():
    return da.load_results()


@pytest.fixture(scope="module")
def panel(db):
    return da.load_panel(db)


@pytest.fixture
def env_db(db, monkeypatch):
    monkeypatch.setenv("OEWS_DB_PATH", str(db))
    return db


# ------------------------------------------------------------------ data-access layer
def test_headline_matches_saved_summary(results):
    """The dashboard reports the A6 artifact, it does not recompute it."""
    h = da.headline(results, "emp", "wcr")
    main = results.summary["main"]["emp"]
    assert h["coef"] == pytest.approx(main["coef"])
    assert h["ci_low"] == pytest.approx(main["ci_low_wcr"]) and h["ci_high"] == pytest.approx(main["ci_high_wcr"])
    assert h["pct"] == pytest.approx(main["pct_effect"], rel=1e-6)
    assert h["verdict"] == main["practical_verdict"]
    w = da.headline(results, "wage", "cr1")
    assert w["ci_low"] == pytest.approx(results.summary["main"]["wage"]["ci_low_cr1"])


def test_headline_rejects_invalid_choices(results):
    with pytest.raises(ValueError):
        da.headline(results, "revenue")
    with pytest.raises(ValueError):
        da.headline(results, "emp", "bayes")


def test_interpretation_is_hedged(results):
    text = da.interpret(da.headline(results, "emp"), results)
    assert "association, not proof" in text and "95% CI" in text


def test_provenance_verifies_fresh_sample_build(results, db):
    prov = da.provenance(results, db)
    assert prov.inputs_match is True and prov.outputs_intact and prov.verified
    assert prov.is_sample and prov.db_source_mode == "sample"


def test_provenance_flags_edited_artifact(results, db, tmp_path):
    copy = tmp_path / "model"
    shutil.copytree(da.MODEL_DIR, copy)
    spec = copy / "specifications_emp.csv"
    spec.write_text(spec.read_text(encoding="utf-8").replace("Primary estimate", "edited"), encoding="utf-8")
    prov = da.provenance(da.load_results(copy), db)
    assert not prov.outputs_intact and "specifications_emp.csv" in prov.changed_outputs


def test_provenance_without_database(results, tmp_path):
    prov = da.provenance(results, tmp_path / "missing.db")
    assert prov.inputs_match is None and not prov.verified


def test_missing_database_raises_with_fix(tmp_path):
    with pytest.raises(da.DataUnavailable) as err:
        da.load_panel(tmp_path / "missing.db")
    assert err.value.fix == da.BUILD_DB_CMD


def test_missing_and_corrupt_results_raise_with_fix(tmp_path):
    with pytest.raises(da.DataUnavailable) as err:
        da.load_results(tmp_path)
    assert err.value.fix == da.BUILD_MODEL_CMD and "model_summary.json" in err.value.detail
    copy = tmp_path / "model"
    shutil.copytree(da.MODEL_DIR, copy)
    (copy / "model_summary.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(da.DataUnavailable):
        da.load_results(copy)


def test_empty_selection_returns_empty_frames(panel):
    none = da.filter_panel(panel, industries=[])
    assert none.empty
    assert da.trend_by_exposure(none).empty and da.occupation_view(none).empty and da.focal_view(none).empty
    unknown = da.filter_panel(panel, industries=["999999"])
    assert unknown.empty


def test_trend_reuses_a5_index(panel):
    t = da.trend_by_exposure(panel, "emp")
    assert list(t.columns) == ["High exposure", "Middle exposure", "Low exposure"]
    assert (t.loc["2022"] == 100).all()


def test_occupation_view_one_row_per_occupation(panel):
    occ = da.occupation_view(panel, "emp")
    assert occ["SOC"].is_unique and occ["GenAI exposure (share of tasks)"].between(0, 1).all()
    assert "13-2051" in set(occ["SOC"])


def test_robustness_and_loo_tables(results, panel):
    tab = da.robustness_table(results, "emp", "wcr")
    assert tab.loc[0, "Role"] == "Main" and len(tab) == len(results.specs["emp"])
    s = da.robustness_summary(results)
    assert s["n_alt"] >= 1 and s["same_sign"] <= s["n_alt"]
    labels = da.code_labels(panel)
    for by in ("naics_code", "soc_code"):
        v = da.leave_one_out_view(results, by, labels[by])
        assert not v.empty and v["Effect per 1 SD (%)"].is_monotonic_increasing
    with pytest.raises(ValueError):
        da.leave_one_out_view(results, "year")


def test_event_table_has_reference_year(results):
    t = da.event_table(results, "wage", "cr1")
    assert (t.loc[t["May reference year"] == "2022", "Gap per 1 SD vs 2022 (%)"] == 0).all()


def test_no_model_estimation_in_page_code():
    """Rubric: pages read saved results; they must not call the estimator."""
    for page in [ENTRY, *PAGES]:
        src = page.read_text(encoding="utf-8")
        for banned in ("run_spec(", "estimate.fit(", "wild_cluster_bootstrap(", "run_all("):
            assert banned not in src, f"{page.name} calls {banned}"


# ------------------------------------------------------------------ Streamlit smoke tests
try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # data-layer tests above still run without streamlit
    AppTest = None
needs_streamlit = pytest.mark.skipif(AppTest is None, reason="streamlit not installed (run `uv sync`)")


def _run(path: Path, **state) -> AppTest:
    at = AppTest.from_file(str(path), default_timeout=TIMEOUT)
    for k, v in state.items():
        at.session_state[k] = v
    return at.run()


@needs_streamlit
def test_entrypoint_loads_without_exception(env_db):
    at = _run(ENTRY)
    assert not at.exception, at.exception
    assert any("generative AI" in t.value for t in at.title)
    assert len(at.metric) >= 4                         # KPIs above the fold


@needs_streamlit
def test_entrypoint_sidebar_switches_outcome(env_db):
    at = _run(ENTRY)
    at.radio(key="_outcome_widget").set_value("Wages").run()
    assert not at.exception, at.exception
    assert at.session_state["outcome_label"] == "Wages"


@needs_streamlit
@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
@pytest.mark.parametrize("outcome", list(da.OUTCOMES))
def test_every_page_loads(env_db, page, outcome):
    at = _run(page, outcome_label=outcome)
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]


@needs_streamlit
def test_explorer_empty_filter_warns_not_crashes(env_db):
    page = REPO / "app_pages" / "3_explorer.py"
    at = _run(page)
    at.multiselect[0].set_value([]).run()
    assert not at.exception, at.exception
    assert any("No industries" in w.value for w in at.warning)


@needs_streamlit
def test_pages_without_database_show_fix(tmp_path, monkeypatch):
    monkeypatch.setenv("OEWS_DB_PATH", str(tmp_path / "missing.db"))
    for page in PAGES:
        at = _run(page)
        assert not at.exception, (page.name, at.exception)
    explorer = _run(REPO / "app_pages" / "3_explorer.py")
    assert any(da.BUILD_DB_CMD in e.value for e in explorer.error)


@needs_streamlit
def test_pages_without_results_show_fix(env_db, tmp_path, monkeypatch):
    monkeypatch.setenv("OEWS_MODEL_DIR", str(tmp_path))
    for page in PAGES:
        at = _run(page)
        assert not at.exception, (page.name, at.exception)
        assert any(da.BUILD_MODEL_CMD in e.value for e in at.error), page.name
