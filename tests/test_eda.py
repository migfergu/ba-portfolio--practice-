"""Tests for the A5 EDA module (oews_eda). Builds a fresh sample database in a temp folder."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from oews_eda import data, describe, inference, report


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    """Run the A4 pipeline on the committed synthetic sample into a temporary database."""
    from oews_pipeline.pipeline import run_pipeline
    tmp = tmp_path_factory.mktemp("eda")
    path = tmp / "oews_genai.db"
    run_pipeline("sample", db_path=path, report_md=None, report_json_dir=tmp)
    return path


@pytest.fixture(scope="module")
def panel(db):
    return data.load_panel(db)


def test_panel_loads_and_passes_quality(panel):
    qc = data.validate_panel(panel)
    assert qc.passed, qc.checks
    assert panel.attrs["source_mode"] == "sample"
    assert {"log_emp", "log_wage", "exposure_group", "cell_id"} <= set(panel.columns)
    # exposure groups are defined per occupation, so each occupation has exactly one label
    assert panel.dropna(subset=["exposure_group"]).groupby("soc_code")["exposure_group"].nunique().max() == 1


def test_validate_flags_duplicates(panel):
    bad = pd.concat([panel, panel.iloc[[0]]], ignore_index=True)
    qc = data.validate_panel(bad)
    assert not qc.checks["unique_key"] and not qc.passed


def test_cell_changes_match_manual_calculation(panel):
    cells = describe.cell_changes(panel)
    cell = cells.dropna(subset=["d_log_emp"]).iloc[0]
    rows = panel[panel["cell_id"] == cell["cell_id"]]
    manual = rows.loc[rows["post"] == 1, "log_emp"].mean() - rows.loc[rows["post"] == 0, "log_emp"].mean()
    assert np.isclose(cell["d_log_emp"], manual)
    assert cells["cell_id"].is_unique


def test_hedges_g_and_group_test_on_known_data():
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 200), rng.normal(0.5, 1, 200)
    assert -0.75 < inference.hedges_g(a, b) < -0.25
    cells = pd.DataFrame({"d_log_emp": np.r_[a, b], "exposure_group": ["High"] * 200 + ["Low"] * 200,
                          "soc_code": [f"o{i % 20}" for i in range(200)] + [f"p{i % 20}" for i in range(200)]})
    r = inference.exposure_group_test(cells, "d_log_emp", alternative="less")
    assert r.decision == "Reject H0" and r.p_value < 0.01 and r.cluster_ci_high < 0


def test_ols_cluster_point_estimates_match_lstsq():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"x": rng.normal(size=300), "g": np.repeat(np.arange(30), 10)})
    df["y"] = 1 + 2 * df["x"] + rng.normal(size=300)
    res = inference.ols_cluster(df, "y", ["x"], cluster="g")
    slope = stats.linregress(df["x"], df["y"]).slope
    assert np.isclose(res.table.loc["x", "coef"], slope)
    assert res.n_clusters == 30 and res.table.loc["x", "ci_low"] < 2 < res.table.loc["x", "ci_high"]


def test_permutation_test_detects_monotone_relation():
    occ = pd.DataFrame({"exposure_main": np.linspace(0, 1, 15), "d_log_emp": -np.linspace(0, 1, 15)})
    out = inference.occupation_permutation_test(occ, n_perm=2000)
    assert out["spearman_rho"] == pytest.approx(-1.0) and out["p_value"] < 0.01


def test_run_all_writes_every_output(db, tmp_path):
    s = report.run_all(db, fig_dir=tmp_path / "fig", table_dir=tmp_path / "tab")
    assert len(list((tmp_path / "fig").glob("fig*.png"))) == 9
    saved = json.loads((tmp_path / "tab" / "eda_summary.json").read_text())
    assert saved["test_emp"]["h1"].endswith("< 0") and s["source_mode"] == "sample"
