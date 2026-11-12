"""Data-access layer for the A7 dashboard. No Streamlit imports: everything here is unit-tested.

Sources, in the order the dashboard trusts them:

1. **A6 result artifacts** (``reports/model/``): the fixed-effects estimates, event study,
   robustness suite, leave-one-out and finance contrast written by ``uv run oews-model``. The
   dashboard only *reads* these; it never re-runs the model inside page code.
2. **A4 database** (``data/processed/oews_genai.db``), read through the A5 loader
   ``oews_eda.data.load_panel`` so the dashboard sees exactly the rows the EDA and the model saw.
3. **A5 functions** (``oews_eda.describe``) for the descriptive views that respond to filters
   (trend index, occupation changes, analyst/clerk contrast). These are cheap aggregations.

Every loader raises :class:`DataUnavailable` with a ``fix`` command instead of a bare stack trace,
so the UI can show the user what to run. :func:`provenance` checks that the database the user built
has the same input files (SHA-256) as the run that produced the artifacts, and that no artifact was
edited after it was written.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from oews_eda import data as eda_data
from oews_eda import describe
from oews_model.analysis import PRACTICAL_THRESHOLD

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = eda_data.DEFAULT_DB
MODEL_DIR = REPO_ROOT / "reports" / "model"
EDA_DIR = REPO_ROOT / "reports" / "eda"
FIG_DIR = REPO_ROOT / "reports" / "figures"
SAMPLE_DIR = REPO_ROOT / "data" / "sample"

BUILD_DB_CMD = "uv run oews-pipeline run"
BUILD_MODEL_CMD = "uv run oews-model"

OUTCOMES = {"Employment": "emp", "Wages": "wage"}
OUTCOME_COLUMN = {"emp": "log_emp", "wage": "log_wage"}
OUTCOME_NOUN = {"emp": "employment", "wage": "mean annual wage"}
INFERENCE = {"Wild cluster bootstrap (recommended)": "wcr", "CR1 cluster-robust t": "cr1"}
HYPOTHESIS = {"emp": "H1: beta < 0 (one-sided)", "wage": "H2: beta != 0 (two-sided)"}



def resolve_db(db_path: Path | str | None = None) -> Path:
    """Database location: explicit argument, else ``$OEWS_DB_PATH``, else data/processed/oews_genai.db."""
    return Path(db_path or os.environ.get("OEWS_DB_PATH") or DB_PATH)


def resolve_model_dir(model_dir: Path | str | None = None) -> Path:
    """Result-artifact folder: explicit argument, else ``$OEWS_MODEL_DIR``, else reports/model/."""
    return Path(model_dir or os.environ.get("OEWS_MODEL_DIR") or MODEL_DIR)


REQUIRED_ARTIFACTS = ("model_summary.json", "model_run_log.json", "specifications_emp.csv",
                      "specifications_wage.csv", "event_study_emp.csv", "event_study_wage.csv",
                      "leave_one_out.csv", "finance_contrast.csv")


class DataUnavailable(Exception):
    """A data source the dashboard needs is missing or unusable.

    Attributes:
        what: Short name of the missing piece (shown as the error title).
        fix: The command or step that resolves it (shown to the user verbatim).
    """

    def __init__(self, what: str, fix: str, detail: str = ""):
        self.what, self.fix, self.detail = what, fix, detail
        super().__init__(f"{what}. Fix: {fix}" + (f" ({detail})" if detail else ""))


# ----------------------------------------------------------------- helpers
def pct(log_points: float) -> float:
    """Convert a log-point coefficient to an exact percent change: (exp(b) - 1) x 100."""
    return float((np.exp(log_points) - 1) * 100)


def naics4(code: str) -> str:
    """Display form of a padded NAICS code ('522100' -> '5221')."""
    return str(code)[:4]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ----------------------------------------------------------------- A4 database
def db_exists(db_path: Path | str | None = None) -> bool:
    """True when the A4 database file is present."""
    db_path = resolve_db(db_path)
    return Path(db_path).exists()


def etl_info(db_path: Path | str | None = None) -> dict:
    """Latest successful ETL run: id, finish time (UTC) and source mode ('sample' or 'raw').

    Raises:
        DataUnavailable: if the database is missing or has no successful run.
    """
    db_path = resolve_db(db_path)
    if not db_exists(db_path):
        raise DataUnavailable("Database not built", BUILD_DB_CMD, str(db_path))
    with eda_data.connect(db_path) as conn:
        row = conn.execute("SELECT run_id, finished_at, source_mode FROM etl_run WHERE status='succeeded' "
                           "ORDER BY run_id DESC LIMIT 1").fetchone()
    if row is None:
        raise DataUnavailable("Database has no successful pipeline run", BUILD_DB_CMD)
    return {"run_id": int(row[0]), "finished_at": row[1], "source_mode": row[2]}


def load_panel(db_path: Path | str | None = None) -> pd.DataFrame:
    """The A5 analysis panel (``v_analysis_panel`` + derived columns), one row per occ x industry x year.

    Raises:
        DataUnavailable: if the database is missing, unreadable, or the panel is empty.
    """
    db_path = resolve_db(db_path)
    if not db_exists(db_path):
        raise DataUnavailable("Database not built", BUILD_DB_CMD, str(db_path))
    try:
        panel = eda_data.load_panel(db_path)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        raise DataUnavailable("Database could not be read", f"delete {db_path} and run `{BUILD_DB_CMD}`",
                              str(exc)) from exc
    if panel.empty:
        raise DataUnavailable("Database contains no panel rows", BUILD_DB_CMD)
    return panel


def quality_gate(panel: pd.DataFrame) -> dict:
    """A5 data-quality gate (``oews_eda.data.validate_panel``) as plain dicts for display."""
    q = eda_data.validate_panel(panel)
    return {"passed": bool(q.passed), "checks": {k: bool(v) for k, v in q.checks.items()},
            "details": q.details, "coverage": q.coverage.reset_index()}


def attrition(panel: pd.DataFrame, db_path: Path | str | None = None) -> pd.DataFrame:
    """A5 merge-attrition table: source rows -> analysis sample."""
    db_path = resolve_db(db_path)
    return eda_data.attrition_table(panel, db_path)


def input_manifest(db_path: Path | str | None = None) -> pd.DataFrame:
    """Input files of the latest ETL run with SHA-256 checksums (A5 run log)."""
    db_path = resolve_db(db_path)
    return eda_data.input_manifest(db_path)


# ----------------------------------------------------------------- A6 artifacts
@dataclass
class ModelResults:
    """Everything the A6 runner saved, loaded once.

    ``specs`` and ``event`` are keyed by outcome ('emp', 'wage').
    """
    summary: dict
    run_log: dict
    specs: dict[str, pd.DataFrame]
    event: dict[str, pd.DataFrame]
    loo: pd.DataFrame
    finance: pd.DataFrame
    model_dir: Path = field(default=MODEL_DIR)

    @property
    def source_mode(self) -> str:
        return self.summary.get("source_mode", "unknown")

    @property
    def generated_at(self) -> str:
        return self.run_log.get("generated_at_utc", "unknown")


def missing_artifacts(model_dir: Path | str | None = None) -> list[str]:
    """Names of required A6 artifacts that are absent from ``model_dir``."""
    model_dir = resolve_model_dir(model_dir)
    return [f for f in REQUIRED_ARTIFACTS if not (model_dir / f).exists()]


def load_results(model_dir: Path | str | None = None) -> ModelResults:
    """Read the saved A6 outputs. Does not estimate anything.

    Raises:
        DataUnavailable: if any required artifact is missing, unreadable, or has no main row.
    """
    model_dir = resolve_model_dir(model_dir)
    missing = missing_artifacts(model_dir)
    if missing:
        raise DataUnavailable("Model results not found", BUILD_MODEL_CMD, "missing: " + ", ".join(missing))
    try:
        summary = json.loads((model_dir / "model_summary.json").read_text(encoding="utf-8"))
        run_log = json.loads((model_dir / "model_run_log.json").read_text(encoding="utf-8"))
        specs = {o: pd.read_csv(model_dir / f"specifications_{o}.csv") for o in OUTCOMES.values()}
        event = {o: pd.read_csv(model_dir / f"event_study_{o}.csv") for o in OUTCOMES.values()}
        loo = pd.read_csv(model_dir / "leave_one_out.csv", dtype={"dropped": str})
        finance = pd.read_csv(model_dir / "finance_contrast.csv")
    except (json.JSONDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DataUnavailable("Model results are unreadable", BUILD_MODEL_CMD, str(exc)) from exc
    for o, tab in specs.items():
        if tab.empty or not (tab["spec"] == "main").any():
            raise DataUnavailable(f"No main estimate in specifications_{o}.csv", BUILD_MODEL_CMD)
    return ModelResults(summary, run_log, specs, event, loo, finance, model_dir)


# ----------------------------------------------------------------- provenance
@dataclass
class Provenance:
    """Can the numbers on screen be trusted to come from the data the user has?"""
    source_mode: str                 # of the model results
    db_source_mode: str | None       # of the user's database (None when not built)
    etl_finished_at: str | None
    model_generated_at: str
    code_commit: str
    inputs_match: bool | None        # DB input checksums == model run inputs (None: no DB)
    outputs_intact: bool             # artifact checksums == run log
    changed_outputs: list[str]
    mismatched_inputs: list[str]

    @property
    def verified(self) -> bool:
        return bool(self.inputs_match) and self.outputs_intact

    @property
    def is_sample(self) -> bool:
        return self.source_mode == "sample"


def provenance(results: ModelResults, db_path: Path | str | None = None) -> Provenance:
    """Compare the model run log with the user's database and with the artifacts on disk."""
    db_path = resolve_db(db_path)
    changed = []
    for out in results.run_log.get("outputs", []):
        p = REPO_ROOT / out["file"]
        if Path(results.model_dir).resolve() != MODEL_DIR.resolve():   # artifacts copied elsewhere
            p = results.model_dir / Path(out["file"]).name
        if not p.exists() or _sha256(p) != out["sha256"]:
            changed.append(Path(out["file"]).name)

    db_mode = etl_at = None
    inputs_match, mismatched = None, []
    if db_exists(db_path):
        try:
            info = etl_info(db_path)
            db_mode, etl_at = info["source_mode"], info["finished_at"]
            cmp = eda_data.compare_manifest(results.run_log.get("inputs", []), db_path)
            mismatched = cmp.loc[~cmp["match"], "source_name"].tolist()
            inputs_match = not mismatched
        except (DataUnavailable, sqlite3.Error, KeyError, pd.errors.DatabaseError):
            inputs_match = False
    return Provenance(results.source_mode, db_mode, etl_at, results.generated_at,
                      str(results.run_log.get("code_commit", "unknown"))[:7], inputs_match,
                      not changed, changed, mismatched)


# ----------------------------------------------------------------- headline results
def headline(results: ModelResults, outcome: str = "emp", inference: str = "wcr") -> dict:
    """The primary A3 estimate for one outcome, in the units a stakeholder reads.

    Args:
        outcome: 'emp' or 'wage'.
        inference: 'wcr' (wild cluster restricted bootstrap, the small-cluster default) or 'cr1'.

    Returns:
        dict with coef (log points), pct and its CI in percent, two-sided p, one-sided p (employment
        H1), practical verdict, sample sizes and the hypothesis label.
    """
    if outcome not in OUTCOME_COLUMN:
        raise ValueError(f"outcome must be one of {list(OUTCOME_COLUMN)}, got {outcome!r}")
    if inference not in ("wcr", "cr1"):
        raise ValueError(f"inference must be 'wcr' or 'cr1', got {inference!r}")
    row = results.specs[outcome].set_index("spec").loc["main"]
    lo, hi = row[f"ci_low_{inference}"], row[f"ci_high_{inference}"]
    p = row[f"p_{inference}"]
    if inference == "wcr":
        p_one = row.get("p_wcr_lower")
    else:  # one-sided from the symmetric t test
        p_one = p / 2 if row["coef"] < 0 else 1 - p / 2
    verdict = _verdict(lo, hi)
    return {"outcome": outcome, "coef": float(row["coef"]), "pct": pct(row["coef"]),
            "pct_low": pct(lo), "pct_high": pct(hi), "ci_low": float(lo), "ci_high": float(hi),
            "p": float(p), "p_one_sided": None if p_one is None or pd.isna(p_one) else float(p_one),
            "p_ri": None if pd.isna(row.get("p_ri")) else float(row["p_ri"]),
            "verdict": verdict, "n_obs": int(row["n_obs"]), "n_cells": int(row["n_cells"]),
            "n_clusters": int(row["n_clusters"]), "hypothesis": HYPOTHESIS[outcome],
            "inference": inference}


def _verdict(lo: float, hi: float, threshold: float = PRACTICAL_THRESHOLD) -> str:
    """Same rule as ``oews_model.analysis.practical_verdict`` (re-exported for the chosen interval)."""
    from oews_model.analysis import practical_verdict
    return practical_verdict(lo, hi, threshold)


def pretrend(results: ModelResults, outcome: str = "emp") -> dict:
    """2021 event-study coefficient (pre-period, 2022 = 0): should be near zero if trends were parallel."""
    es = results.event[outcome]
    r = es.loc[es["year"] == 2021]
    if r.empty:
        return {"coef": float("nan"), "pct": float("nan"), "p_wcr": float("nan"), "pass": False}
    r = r.iloc[0]
    passed = bool(r["ci_low_wcr"] <= 0 <= r["ci_high_wcr"])
    return {"coef": float(r["coef"]), "pct": pct(r["coef"]), "p_wcr": float(r["p_wcr"]),
            "pct_low": pct(r["ci_low_wcr"]), "pct_high": pct(r["ci_high_wcr"]), "pass": passed}


def iqr_effect(results: ModelResults, h: dict) -> float:
    """Percent effect for moving from the 25th to the 75th percentile occupation on exposure."""
    iqr = results.summary.get("panel", {}).get("iqr_z", float("nan"))
    return pct(h["coef"] * iqr)


def interpret(h: dict, results: ModelResults) -> str:
    """One plain-language sentence for the headline, honest about uncertainty and scope."""
    noun = OUTCOME_NOUN[h["outcome"]]
    direction = "lower" if h["pct"] < 0 else "higher"
    sd = results.summary.get("panel", {}).get("sd_exposure_share")
    sd_txt = f" (about {sd * 100:.0f} percentage points of tasks exposed)" if sd else ""
    lead = (f"Each 1 standard deviation of additional GenAI exposure{sd_txt} is associated with {noun} about "
            f"{abs(h['pct']):.1f}% {direction} after ChatGPT's release, relative to less-exposed occupations in "
            f"the same industry and to each cell's own pre-2023 level "
            f"(95% CI {h['pct_low']:+.1f}% to {h['pct_high']:+.1f}%).")
    v = h["verdict"]
    if v == "practically meaningful":
        tail = " The whole interval is beyond the 1-point practical bar, so the gap is both detectable and material."
    elif v.startswith("negligible"):
        tail = " The whole interval sits inside the +/-1-point practical bar: no economically meaningful change."
    elif v.startswith("nonzero"):
        tail = " The interval excludes zero but may be smaller than the 1-point practical bar."
    else:
        tail = " The interval includes zero and values beyond the practical bar, so the evidence is inconclusive."
    return lead + tail + " This is an association, not proof that GenAI caused it."


# ----------------------------------------------------------------- robustness
ROLE_ORDER = {"main": 0, "comparison": 1, "robustness": 2, "placebo": 3}


def robustness_table(results: ModelResults, outcome: str = "emp", inference: str = "wcr") -> pd.DataFrame:
    """Every specification with its estimate in percent, the chosen CI, p-value and verdict."""
    t = results.specs[outcome].copy()
    t["order"] = t["role"].map(ROLE_ORDER).fillna(9)
    t = t.sort_values(["order"], kind="stable")
    lo, hi = t[f"ci_low_{inference}"], t[f"ci_high_{inference}"]
    out = pd.DataFrame({
        "Specification": t["label"].to_numpy(),
        "Role": t["role"].str.capitalize().to_numpy(),
        "Effect per 1 SD (%)": [pct(x) for x in t["coef"]],
        "95% CI low (%)": [pct(x) if pd.notna(x) else np.nan for x in lo],
        "95% CI high (%)": [pct(x) if pd.notna(x) else np.nan for x in hi],
        "p-value": t[f"p_{inference}"].to_numpy(),
        "Rows": t["n_obs"].astype(int).to_numpy(),
        "Verdict": [_verdict(a, b) if pd.notna(a) else "n/a" for a, b in zip(lo, hi)],
    })
    return out.reset_index(drop=True)


def robustness_summary(results: ModelResults, outcome: str = "emp", inference: str = "wcr") -> dict:
    """How many non-placebo specifications agree in sign with the main estimate and clear the bar."""
    t = robustness_table(results, outcome, inference)
    main_sign = np.sign(t.loc[t["Role"] == "Main", "Effect per 1 SD (%)"].iat[0])
    alt = t[t["Role"].isin(["Comparison", "Robustness"])]
    same_sign = int((np.sign(alt["Effect per 1 SD (%)"]) == main_sign).sum())
    meaningful = int((alt["Verdict"] == "practically meaningful").sum())
    placebo = t[t["Role"] == "Placebo"]
    return {"n_alt": len(alt), "same_sign": same_sign, "meaningful": meaningful,
            "range_pct": (float(alt["Effect per 1 SD (%)"].min()), float(alt["Effect per 1 SD (%)"].max())),
            "placebo_pct": float(placebo["Effect per 1 SD (%)"].iat[0]) if len(placebo) else float("nan"),
            "placebo_p": float(placebo["p-value"].iat[0]) if len(placebo) else float("nan")}


def leave_one_out_view(results: ModelResults, by: str, labels: dict[str, str] | None = None) -> pd.DataFrame:
    """Leave-one-out estimates (employment) for one dimension, labeled and sorted, in percent.

    Args:
        by: 'naics_code' (drop one industry) or 'soc_code' (drop one occupation).
        labels: optional code -> title map (from the database) for readable names.
    """
    if by not in ("naics_code", "soc_code"):
        raise ValueError("by must be 'naics_code' or 'soc_code'")
    d = results.loo[results.loo["dropped_by"] == by].dropna(subset=["coef"]).copy()
    if d.empty:
        return pd.DataFrame(columns=["code", "Dropped", "Effect per 1 SD (%)", "95% CI low (%)",
                                     "95% CI high (%)", "Rows"])
    labels = labels or {}
    code = d["dropped"].astype(str)
    disp = code.map(naics4) if by == "naics_code" else code
    return pd.DataFrame({
        "code": code.to_numpy(),
        "Dropped": [f"{c} {labels.get(k, '')}".strip() for c, k in zip(disp, code)],
        "Effect per 1 SD (%)": [pct(x) for x in d["coef"]],
        "95% CI low (%)": [pct(c - 1.96 * s) for c, s in zip(d["coef"], d["se_cr1"])],
        "95% CI high (%)": [pct(c + 1.96 * s) for c, s in zip(d["coef"], d["se_cr1"])],
        "Rows": d["n_obs"].astype(int).to_numpy(),
    }).sort_values("Effect per 1 SD (%)").reset_index(drop=True)


def code_labels(panel: pd.DataFrame | None) -> dict[str, dict[str, str]]:
    """{'naics_code': {code: title}, 'soc_code': {code: title}} from the panel (empty if no DB)."""
    if panel is None or panel.empty:
        return {"naics_code": {}, "soc_code": {}}
    ind = panel.drop_duplicates("naics_code").set_index("naics_code")["naics_title"].astype(str).to_dict()
    occ = panel.drop_duplicates("soc_code").set_index("soc_code")["occ_title"].astype(str).to_dict()
    return {"naics_code": ind, "soc_code": occ}


def event_table(results: ModelResults, outcome: str = "emp", inference: str = "wcr") -> pd.DataFrame:
    """Event-study path in percent for display (2022 = reference)."""
    es = results.event[outcome].sort_values("year")
    lo, hi = es[f"ci_low_{inference}"], es[f"ci_high_{inference}"]
    return pd.DataFrame({
        "May reference year": es["year"].astype(int).astype(str).to_numpy(),
        "Gap per 1 SD vs 2022 (%)": [pct(x) for x in es["coef"]],
        "95% CI low (%)": [pct(x) for x in lo],
        "95% CI high (%)": [pct(x) for x in hi],
        "Period": np.where(es["year"] <= eda_data.REFERENCE_YEAR, "Pre-ChatGPT", "Post-ChatGPT"),
    })


# ----------------------------------------------------------------- descriptive (A5 code, filterable)
def industry_options(panel: pd.DataFrame) -> dict[str, str]:
    """Display label -> naics_code for every industry in the panel, sorted by code."""
    ind = panel.drop_duplicates("naics_code").sort_values("naics_code")
    return {f"{naics4(c)} {t}": c for c, t in zip(ind["naics_code"], ind["naics_title"])}


def filter_panel(panel: pd.DataFrame, industries: list[str] | None = None,
                 terciles: list[str] | None = None) -> pd.DataFrame:
    """Restrict the panel to selected industries (naics codes) and exposure terciles.

    ``None`` means no restriction; an empty list means "nothing selected" and returns an empty frame,
    which the UI turns into an explanatory warning rather than a crash. Unknown codes are ignored.
    """
    out = panel
    if industries is not None:
        out = out[out["naics_code"].isin(industries)]
    if terciles is not None:
        out = out[out["exposure_tercile"].isin(terciles)]
    out = out.copy()
    out.attrs.update(panel.attrs)
    return out


def trend_long(panel: pd.DataFrame, outcome: str = "emp", balanced: bool = True) -> pd.DataFrame:
    """A5 trend index by exposure tercile (2022 = 100), long form (group, year, n_cells, index).

    Uses ``oews_eda.data.balanced_cells`` + ``oews_eda.describe.trend_index`` (A5 code, not re-implemented),
    the input ``oews_eda.plots.plot_trend_index`` expects. Empty when the selection has no 2022 rows.
    """
    col = OUTCOME_COLUMN[outcome]
    d = eda_data.balanced_cells(panel, col) if balanced else panel
    d = d.dropna(subset=["exposure_tercile", col])
    if d.empty or not (d["year"] == eda_data.REFERENCE_YEAR).any():
        return pd.DataFrame(columns=["group", "year", "n_cells", "index"])
    return describe.trend_index(d, by="exposure_tercile", outcome=col).dropna(subset=["index"])


def trend_by_exposure(panel: pd.DataFrame, outcome: str = "emp", balanced: bool = True) -> pd.DataFrame:
    """:func:`trend_long` pivoted wide (one column per tercile) for ``st.line_chart``; empty if unavailable."""
    t = trend_long(panel, outcome, balanced)
    if t.empty:
        return pd.DataFrame()
    t = t.assign(group=t["group"].map({"High": "High exposure", "Middle": "Middle exposure",
                                       "Low": "Low exposure"}))
    wide = t.pivot(index="year", columns="group", values="index")
    wide = wide[[c for c in ("High exposure", "Middle exposure", "Low exposure") if c in wide]]
    wide.index = wide.index.astype(int).astype(str)
    wide.index.name = "May reference year"
    wide.attrs["n_cells"] = t.groupby("group")["n_cells"].max().to_dict()
    return wide


def occupation_view(panel: pd.DataFrame, outcome: str = "emp") -> pd.DataFrame:
    """One row per occupation: exposure and its employment-weighted, within-industry pre->post change.

    Built from A5 ``describe.cell_changes`` (within-industry long difference) and
    ``describe.occupation_changes`` (pre-period employment weights). Descriptive, not the model.
    """
    col = f"d_{OUTCOME_COLUMN[outcome]}_wi"
    if panel.empty:
        return pd.DataFrame()
    cells = describe.cell_changes(panel)
    cells = cells.dropna(subset=[col, "exposure_main"])
    if cells.empty:
        return pd.DataFrame()
    occ = describe.occupation_changes(cells, value=col).reset_index()
    tercile = panel.drop_duplicates("soc_code").set_index("soc_code")["exposure_tercile"]
    return pd.DataFrame({
        "SOC": occ["soc_code"],
        "Occupation": occ["occ_title"],
        "GenAI exposure (share of tasks)": occ["exposure_main"].astype(float),
        "Exposure tercile": occ["soc_code"].map(tercile),
        "Change vs same-industry peers (%)": [pct(x) for x in occ[col]],
        "Industry cells": occ["n_cells"].astype(int),
        "Focal role": occ["focal_role"].map({"analyst": "Analyst", "clerk_contrast": "Clerk contrast"}).fillna(""),
    }).sort_values("GenAI exposure (share of tasks)", ascending=False).reset_index(drop=True)


def focal_long(panel: pd.DataFrame) -> pd.DataFrame:
    """A5 analyst-vs-clerk contrast (``describe.focal_contrast``), the input ``plots.plot_focal_contrast`` expects."""
    f = panel[panel["focal_role"].notna()]
    if f.empty:
        return pd.DataFrame()
    return describe.focal_contrast(f)


def focal_view(panel: pd.DataFrame, outcome: str = "emp") -> pd.DataFrame:
    """:func:`focal_long` for one outcome, wide for ``st.line_chart``. Empty if not available."""
    c = focal_long(panel)
    if c.empty:
        return pd.DataFrame()
    val = "emp_index" if outcome == "emp" else "wage_index"
    c = c.assign(role=c["focal_role"].map({"analyst": "Financial & investment analysts",
                                           "clerk_contrast": "Bookkeeping & accounting clerks"}))
    wide = c.pivot(index="year", columns="role", values=val).dropna(how="all")
    wide.index = wide.index.astype(int).astype(str)
    wide.index.name = "May reference year"
    return wide


def occupation_detail(panel: pd.DataFrame, soc_code: str) -> pd.DataFrame:
    """Every industry-year row for one occupation, with suppression flags, for spot checks."""
    d = panel[panel["soc_code"] == soc_code].sort_values(["naics_code", "year"])
    if d.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "Industry": [f"{naics4(c)} {t}" for c, t in zip(d["naics_code"], d["naics_title"])],
        "Year": d["year"].astype(int).astype(str),
        "Employment": d["tot_emp"],
        "Mean annual wage (USD)": d["a_mean"],
        "Employment suppressed": d["emp_suppressed"].astype(bool),
        "Wage suppressed": d["wage_suppressed"].astype(bool),
    }).reset_index(drop=True)


def finance_view(results: ModelResults, outcome: str = "emp") -> pd.DataFrame:
    """A6 descriptive finance contrast for one outcome, in percent."""
    f = results.finance[results.finance["outcome"] == OUTCOME_COLUMN[outcome]]
    return pd.DataFrame({"Term": f["role"].to_numpy(),
                         "Post-2022 deviation (%)": f["pct_effect"].astype(float).to_numpy()})
