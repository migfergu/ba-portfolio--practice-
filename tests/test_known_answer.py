"""Known-answer tests for the A5 EDA statistics (A5 feedback items 1 and 3).

Two kinds of check, kept separate on purpose:
* Noise-free sample: the EDA must equal the oracle to within rounding. This is the test that can tell
  a code defect from sampling noise; the mutation test below proves it catches a one-year shift.
* Noisy seeds: the committed seed's estimate must lie within SAMPLING_Z SDs of the noise-free value.
"""
from __future__ import annotations

import numpy as np
import pytest

from oews_eda import data, known_answer as ka


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    return ka.known_answer(ka.build_sample_db(tmp_path_factory.mktemp("clean"), seed=751, emp_noise_sd=0.0))


@pytest.fixture(scope="module")
def committed(tmp_path_factory):
    return ka.known_answer(ka.build_sample_db(tmp_path_factory.mktemp("seed751"), seed=751))


def test_closed_form_slope_is_derived_from_the_generator():
    # -a * mean(k) * 100 / 10 with a = 0.06 and k = 1, 2, 3 -> -1.2 points per +0.1 exposure
    assert ka.closed_form_slope() == pytest.approx(-1.2)


def test_oracle_slope_close_to_closed_form(clean):
    # gap = log-approximation and suppression/attrition of cells; documented bound 0.05 pts
    assert abs(clean.slope_oracle - ka.closed_form_slope()) <= 0.05


def test_noise_free_slope_recovers_oracle(clean):
    assert abs(clean.slope - clean.slope_oracle) <= ka.CODE_TOL_SLOPE


def test_noise_free_gaps_recover_oracle_every_year(clean):
    err = (clean.gaps - clean.gaps_oracle).abs()
    assert (err <= ka.CODE_TOL_GAP).all(), err.to_dict()
    # 2023 carries one unit of the planted ramp, so its oracle gap is clearly nonzero
    assert clean.gaps_oracle[2023] < -1.0
    assert clean.gaps[2022] == pytest.approx(0.0)


def test_committed_seed_is_within_sampling_band(clean, committed):
    dist = ka.seed_distribution(range(752, 792))
    for stat, est, seed_val in [("slope", clean.slope, committed.slope),
                                ("gap_2023", clean.gaps[2023], committed.gaps[2023]),
                                ("gap_2025", clean.gaps[2025], committed.gaps[2025])]:
        z = (seed_val - est) / dist[stat].std(ddof=1)
        assert abs(z) <= ka.SAMPLING_Z, (stat, z)


def test_committed_database_matches_regenerated_seed(committed):
    """The committed sample is seed 751 at the default noise: same statistics either way."""
    on_disk = ka.known_answer(data.DEFAULT_DB) if data.DEFAULT_DB.exists() else committed
    assert on_disk.slope == pytest.approx(committed.slope, abs=1e-9)


def test_one_year_shift_in_generator_is_caught(tmp_path, monkeypatch):
    """Mutation test: if the effect started a year late, the noise-free check must fail in 2023."""
    from oews_pipeline import sample_data
    real = sample_data.planted_effect
    monkeypatch.setattr(sample_data, "planted_effect",
                        lambda e, y, slope=None: real(e, y - 1, slope) if y >= 2024 else 1.0)
    db = ka.build_sample_db(tmp_path, seed=751, emp_noise_sd=0.0)
    monkeypatch.setattr(sample_data, "planted_effect", real)     # oracle uses the intended effect
    res = ka.known_answer(db)
    assert abs(res.gaps[2023] - res.gaps_oracle[2023]) > ka.CODE_TOL_GAP
    assert abs(res.slope - res.slope_oracle) > ka.CODE_TOL_SLOPE


def test_evaluate_report_shape(tmp_path):
    out = ka.evaluate(seeds=range(752, 757), work_dir=tmp_path)
    chk = out["checks"]
    assert {"code_pass", "sampling_pass", "seed751_z"} <= set(chk.columns)
    assert chk["code_pass"].all()
    assert np.isfinite(chk["seed_sd"]).all()
