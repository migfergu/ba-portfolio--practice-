"""Tests for the A6 analytics engine (oews_model)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from oews_eda import data, inference as eda_inference
from oews_model import analysis as A, inference, report, validation
from oews_model.__main__ import main as cli
from oews_model.estimate import ModelError, fit


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    from oews_pipeline.pipeline import run_pipeline
    tmp = tmp_path_factory.mktemp("model")
    path = tmp / "oews_genai.db"
    run_pipeline("sample", db_path=path, report_md=None, report_json_dir=tmp)
    return path


@pytest.fixture(scope="module")
def frame(db):
    return A.model_frame(data.load_panel(db))


@pytest.fixture(scope="module")
def main_res(frame):
    return A.run_spec(frame, next(s for s in A.specifications() if s.key == "main"))


def test_model_frame_variables(frame):
    share = frame.groupby("year")["post_panel_share"].first()
    assert share.loc[2021] == 0 and share.loc[2025] == pytest.approx(5 / 6)
    f = frame.dropna(subset=["exposure_z"])           # occupations without exposure stay NaN (excluded)
    assert (f.loc[f["year"] < 2023, "exp_post"] == 0).all()
    assert (f.loc[f["year"] == 2022, [f"exp_y{t}" for t in A.EVENT_YEARS]] == 0).all().all()


def test_absorbed_fe_equals_dummy_variable_ols(main_res):
    """Alternating-projection FE must give exactly the dummy-variable OLS coefficient (FWL)."""
    rows = main_res.data.frame
    dummy = eda_inference.ols_cluster(rows, "log_emp", ["exp_post"], ["cell_id", "indyear"])
    assert main_res.coef() == pytest.approx(dummy.table.loc["exp_post", "coef"], abs=1e-9)


def test_cr1_matches_reference_without_fixed_effects(frame):
    """With no absorbed effects both implementations use the same k, so CR1 SEs match exactly."""
    d = frame.dropna(subset=["log_emp", "exposure_z"])
    ours = fit(d, "log_emp", ["exp_post", "exposure_z", "post"], [], label="pooled")
    ref = eda_inference.ols_cluster(d, "log_emp", ["exp_post", "exposure_z", "post"])
    for term in ("exp_post", "exposure_z", "post"):
        assert ours.table.loc[term, "coef"] == pytest.approx(ref.table.loc[term, "coef"], abs=1e-9)
        assert ours.table.loc[term, "se"] == pytest.approx(ref.table.loc[term, "se_cluster"], rel=1e-9)


def test_wild_bootstrap_is_deterministic_and_consistent(main_res):
    a = inference.wild_cluster_bootstrap(main_res, B=499, seed=1)
    b = inference.wild_cluster_bootstrap(main_res, B=499, seed=1)
    assert a == b
    assert a["ci_low_wcr"] < main_res.coef() < a["ci_high_wcr"]
    assert 0 <= a["p_wcr"] <= 1


def test_randomization_inference_bounds(main_res):
    r = inference.randomization_inference(main_res.data.frame, main_res,
                                          lambda x: (x["exposure_z"] * x["post"]).to_numpy(), n_perm=99)
    assert 1 / 100 <= r["p_ri"] <= 1


def test_noise_free_recovery_and_closed_form():
    rec = validation.recovery()
    assert rec["recovery_pass"].all(), rec
    assert rec["closed_form_pass"].all(), rec


def test_lagged_effect_fails_recovery(tmp_path, monkeypatch, frame):
    """Mutation: an effect that starts in 2024 must not pass as the planted 2023 start."""
    from oews_eda.known_answer import build_sample_db
    from oews_pipeline import sample_data
    real = sample_data.planted_effect
    monkeypatch.setattr(sample_data, "planted_effect",
                        lambda e, y, slope=None: real(e, y - 1, slope) if y >= 2024 else 1.0)
    d = A.model_frame(data.load_panel(build_sample_db(tmp_path, seed=751, emp_noise_sd=0.0)))
    monkeypatch.setattr(sample_data, "planted_effect", real)
    cf = validation.closed_form(d)
    assert abs(A.event_study(d).coef("exp_y2023") - cf["exp_y2023"]) > validation.RECOVERY_TOL_EVENT


def test_placebo_and_wage_are_near_zero_on_noise_free(tmp_path):
    from oews_eda.known_answer import build_sample_db
    d = A.model_frame(data.load_panel(build_sample_db(tmp_path, seed=751, emp_noise_sd=0.0)))
    plac = A.run_spec(d, next(s for s in A.specifications() if s.key == "placebo"))
    assert abs(plac.coef()) < 1e-3          # no pre-period effect is planted
    wage = A.run_spec(d, next(s for s in A.specifications("log_wage") if s.key == "main"), "log_wage")
    assert abs(wage.coef()) < 0.01           # no wage effect is planted (wage noise remains)


def test_too_few_clusters_raises(frame):
    keep = frame["soc_code"].dropna().unique()[:5]
    with pytest.raises(ModelError, match="clusters"):
        fit(frame[frame["soc_code"].isin(keep)], "log_emp", ["exp_post"], A.MAIN_FE)


def test_missing_database_is_reported(tmp_path, capsys):
    with pytest.raises(FileNotFoundError):
        report.run_all(tmp_path / "nope.db", fig_dir=tmp_path, table_dir=tmp_path)
    assert cli(["--db", str(tmp_path / "nope.db")]) == 2
    assert "ERROR" in capsys.readouterr().err


def test_run_all_writes_artifacts_and_verifies(db, tmp_path):
    s = report.run_all(db, fig_dir=tmp_path / "fig", table_dir=tmp_path / "tab", B=199, n_perm=99, validate=False)
    for f in ("specifications_emp.csv", "specifications_wage.csv", "event_study_emp.csv", "leave_one_out.csv",
              "finance_contrast.csv", "model_summary.json", "model_run_log.json"):
        assert (tmp_path / "tab" / f).exists(), f
    assert len(list((tmp_path / "fig").glob("fig1[2-4]_*.png"))) == 3
    spec = pd.read_csv(tmp_path / "tab" / "specifications_emp.csv")
    assert {"comparison", "main", "robustness", "placebo"} <= set(spec["role"])
    assert s["main"]["emp"]["coef"] < 0
    log = tmp_path / "tab" / "model_run_log.json"
    assert all(len(o["sha256"]) == 64 for o in json.loads(log.read_text())["outputs"])
    assert cli(["--db", str(db), "--verify-against", str(log)]) == 0


def test_monte_carlo_smoke(tmp_path):
    mc = validation.monte_carlo(range(3000, 3003), effect_slope=0.0, B=99, n_perm=49, work_dir=tmp_path)
    summ = validation.summarize_monte_carlo(mc)
    assert len(mc) == 3 and summ["mean_truth"].iat[0] == 0
    assert mc[["p_cr1", "p_wcr", "p_ri"]].apply(lambda c: c.between(0, 1)).all().all()
