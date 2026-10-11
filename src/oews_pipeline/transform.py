"""Transform: parse BLS conventions, enforce grain, validate, de-duplicate, aggregate O*NET -> SOC."""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

import pandas as pd
from pydantic import ValidationError

from .config import Settings
from .extract import Extracted
from .validate import (ExposureRecord, JobZoneRecord, OewsRecord, RejectLog,
                       classify_validation_error)

log = logging.getLogger(__name__)

EMP_SUPPRESSED = {"**"}          # BLS: employment estimate not released
WAGE_SUPPRESSED = {"*", "**"}    # BLS: wage estimate not available
WAGE_TOPCODED = {"#"}            # BLS: wage at/above the published top-code threshold
PRSE_MISSING = {"*", "**"}


class ParseError(ValueError):
    """A numeric field holds a value that is neither a number nor a documented BLS symbol."""
    pass


def _blank(v) -> bool:
    """True for None, NaN, pd.NA, or an all-whitespace string."""
    return v is None or (isinstance(v, float) and v != v) or (isinstance(v, str) and v.strip() == "") or v is pd.NA


def parse_number(v, field_name: str, null_symbols: set[str] = frozenset(), as_int: bool = False):
    """Return a number, or None for blanks / documented BLS null symbols. Raise ParseError otherwise."""
    if _blank(v):
        return None
    s = str(v).strip().replace(",", "").replace("$", "")
    if s in null_symbols:
        return None
    try:
        x = float(s)
    except ValueError as exc:
        raise ParseError(f"{field_name}: {v!r} is not numeric or a documented BLS symbol") from exc
    if as_int:
        if x != int(x):
            raise ParseError(f"{field_name}: {v!r} is not a whole number")
        return int(x)
    return x


def normalize_naics(v) -> str:
    """Strip and right-pad NAICS codes to BLS's 6-character form ('5221' -> '522100')."""
    s = "" if _blank(v) else str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if s.isdigit() and 2 <= len(s) < 6:
        s = s.ljust(6, "0")          # e.g., '5221' -> '522100' (BLS publishes 6-character NAICS)
    return s


def onet_to_soc(code: str) -> str:
    """O*NET-SOC 2019 taxonomy aligns to 2018 SOC at the 6-digit level: '13-2051.00' -> '13-2051'."""
    return code.split(".")[0]


@dataclass
class OewsResult:
    """Validated OEWS rows for one year plus their transform statistics."""
    records: pd.DataFrame
    stats: dict = field(default_factory=dict)


def transform_oews(ex: Extracted, settings: Settings, rejects: RejectLog) -> OewsResult:
    """Filter one OEWS year to the panel grain, parse BLS symbols, validate each row, and de-duplicate."""
    df = ex.frame
    year = ex.source.year
    src = ex.source.name
    stats: Counter = Counter(rows_read=len(df))

    o_ok = df["O_GROUP"].fillna("").str.strip().str.lower() == settings.occupation_level
    i_ok = df["I_GROUP"].fillna("").str.strip().str.lower() == settings.industry_level
    in_scope = df[o_ok & i_ok]
    stats["out_of_scope_filtered"] = int(len(df) - len(in_scope))

    valid: list[dict] = []
    for raw in in_scope.to_dict(orient="records"):
        soc = "" if _blank(raw.get("OCC_CODE")) else str(raw["OCC_CODE"]).strip()
        naics = normalize_naics(raw.get("NAICS"))
        key = f"{soc}|{naics}|{year}"
        try:
            emp_raw = raw.get("TOT_EMP")
            a_raw = raw.get("A_MEAN")
            rec = dict(
                soc_code=soc,
                occ_title="" if _blank(raw.get("OCC_TITLE")) else str(raw["OCC_TITLE"]).strip(),
                naics_code=naics,
                naics_title="" if _blank(raw.get("NAICS_TITLE")) else str(raw["NAICS_TITLE"]).strip(),
                industry_level=settings.industry_level,
                year=year,
                tot_emp=parse_number(emp_raw, "TOT_EMP", EMP_SUPPRESSED, as_int=True),
                emp_prse=parse_number(raw.get("EMP_PRSE"), "EMP_PRSE", PRSE_MISSING),
                a_mean=parse_number(a_raw, "A_MEAN", WAGE_SUPPRESSED | WAGE_TOPCODED),
                h_mean=parse_number(raw.get("H_MEAN"), "H_MEAN", WAGE_SUPPRESSED | WAGE_TOPCODED),
                mean_prse=parse_number(raw.get("MEAN_PRSE"), "MEAN_PRSE", PRSE_MISSING),
                emp_suppressed=int(str(emp_raw).strip() in EMP_SUPPRESSED),
                wage_suppressed=int(str(a_raw).strip() in WAGE_SUPPRESSED),
                wage_topcoded=int(str(a_raw).strip() in WAGE_TOPCODED),
                source_file=ex.source.path.name,
            )
        except ParseError as exc:
            rejects.add(src, "NON_NUMERIC", str(exc), raw, key)
            stats["rejected_NON_NUMERIC"] += 1
            continue
        try:
            valid.append(OewsRecord(**rec).model_dump())
        except ValidationError as exc:
            code, detail = classify_validation_error(exc)
            rejects.add(src, code, detail, raw, key)
            stats[f"rejected_{code}"] += 1

    out = pd.DataFrame(valid, columns=list(OewsRecord.model_fields))
    out["tot_emp"] = out["tot_emp"].astype("Int64")
    for c in ["emp_prse", "a_mean", "h_mean", "mean_prse"]:
        out[c] = out[c].astype("float64")
    out = _dedupe(out, src, rejects, stats)
    stats["rows_valid"] = int(len(out))
    log.info("transformed %-10s read=%d out_of_scope=%d valid=%d rejected=%d",
             src, stats["rows_read"], stats["out_of_scope_filtered"], stats["rows_valid"],
             sum(v for k, v in stats.items() if k.startswith("rejected_")))
    return OewsResult(out, dict(stats))


def _dedupe(df: pd.DataFrame, src: str, rejects: RejectLog, stats: Counter) -> pd.DataFrame:
    """Quarantine extra exact copies (keep one) and all rows of conflicting duplicate keys."""
    key = ["soc_code", "naics_code", "year"]
    if df.empty:
        return df
    exact_extra = df.duplicated(keep="first")                  # identical in every column
    for raw in df[exact_extra].to_dict(orient="records"):
        rejects.add(src, "DUPLICATE_EXACT", "identical copy of an earlier row", raw,
                    f"{raw['soc_code']}|{raw['naics_code']}|{raw['year']}")
    stats["rejected_DUPLICATE_EXACT"] += int(exact_extra.sum())
    df = df[~exact_extra]

    conflict = df.duplicated(subset=key, keep=False)            # same key, different values
    for raw in df[conflict].to_dict(orient="records"):
        rejects.add(src, "DUPLICATE_CONFLICT", "same key with different values", raw,
                    f"{raw['soc_code']}|{raw['naics_code']}|{raw['year']}")
    stats["rejected_DUPLICATE_CONFLICT"] += int(conflict.sum())
    return df[~conflict].reset_index(drop=True)


def _validate_onet_rows(ex: Extracted, build, model, rejects: RejectLog, stats: Counter) -> pd.DataFrame:
    """Build and validate one Pydantic record per O*NET row; route failures to the reject log."""
    good = []
    for raw in ex.frame.to_dict(orient="records"):
        code = "" if _blank(raw.get("O*NET-SOC Code")) else str(raw["O*NET-SOC Code"]).strip()
        try:
            good.append(model(**build(raw, code)).model_dump())
        except ParseError as exc:
            rejects.add(ex.source.name, "NON_NUMERIC", str(exc), raw, code)
            stats["rejected_NON_NUMERIC"] += 1
        except ValidationError as exc:
            reason, detail = classify_validation_error(exc)
            rejects.add(ex.source.name, reason, detail, raw, code)
            stats[f"rejected_{reason}"] += 1
    return pd.DataFrame(good, columns=list(model.model_fields))


def transform_exposure(ex: Extracted, settings: Settings, panel_socs: set[str],
                       rejects: RejectLog) -> tuple[pd.DataFrame, dict]:
    """Validate exposure rows, average O*NET codes to 6-digit SOC, keep panel SOCs, and standardize."""
    measure = settings.exposure_measure
    stats: Counter = Counter(rows_read=len(ex.frame))

    def build(raw, code):
        get = lambda c: parse_number(raw.get(c), c) if c in raw else None  # noqa: E731
        return dict(onet_code=code, title="" if _blank(raw.get("Title")) else str(raw["Title"]).strip(),
                    exposure_alpha=get("dv_rating_alpha"), exposure_beta=get("dv_rating_beta"),
                    exposure_gamma=get("dv_rating_gamma"), exposure_main=parse_number(raw.get(measure), measure))

    rows = _validate_onet_rows(ex, build, ExposureRecord, rejects, stats)
    stats["rows_valid"] = int(len(rows))
    rows["soc_code"] = rows["onet_code"].map(onet_to_soc)
    agg = (rows.groupby("soc_code", as_index=False)
               .agg(exposure_alpha=("exposure_alpha", "mean"), exposure_beta=("exposure_beta", "mean"),
                    exposure_gamma=("exposure_gamma", "mean"), exposure_main=("exposure_main", "mean"),
                    n_onet_codes=("onet_code", "nunique")))
    stats["socs_after_aggregation"] = int(len(agg))
    stats["socs_not_in_oews_panel"] = int((~agg["soc_code"].isin(panel_socs)).sum())
    agg = agg[agg["soc_code"].isin(panel_socs)].copy()
    stats["panel_socs_without_exposure"] = int(len(panel_socs - set(agg["soc_code"])))

    sd = agg["exposure_main"].std(ddof=1)
    agg["exposure_z"] = (agg["exposure_main"] - agg["exposure_main"].mean()) / sd if sd and sd > 0 else 0.0
    agg["measure"] = measure
    agg["source_version"] = ex.source.version
    stats["socs_loaded"] = int(len(agg))
    log.info("transformed exposure: %d O*NET rows -> %d SOCs loaded (%d unmatched SOCs, %d panel SOCs lack exposure)",
             stats["rows_valid"], stats["socs_loaded"], stats["socs_not_in_oews_panel"],
             stats["panel_socs_without_exposure"])
    return agg.reset_index(drop=True), dict(stats)


def transform_job_zones(ex: Extracted, panel_socs: set[str], rejects: RejectLog) -> tuple[pd.DataFrame, dict]:
    """Validate Job Zone rows and aggregate them to 6-digit SOC (mean and max)."""
    stats: Counter = Counter(rows_read=len(ex.frame))

    def build(raw, code):
        return dict(onet_code=code, title="" if _blank(raw.get("Title")) else str(raw["Title"]).strip(),
                    job_zone=parse_number(raw.get("Job Zone"), "Job Zone", as_int=True))

    rows = _validate_onet_rows(ex, build, JobZoneRecord, rejects, stats)
    stats["rows_valid"] = int(len(rows))
    rows["soc_code"] = rows["onet_code"].map(onet_to_soc)
    agg = (rows.groupby("soc_code", as_index=False)
               .agg(job_zone_mean=("job_zone", "mean"), job_zone_max=("job_zone", "max"),
                    n_onet_codes=("onet_code", "nunique")))
    stats["socs_not_in_oews_panel"] = int((~agg["soc_code"].isin(panel_socs)).sum())
    agg = agg[agg["soc_code"].isin(panel_socs)].copy()
    agg["onet_version"] = ex.source.version
    stats["socs_loaded"] = int(len(agg))
    return agg.reset_index(drop=True), dict(stats)


def build_dimensions(oews: pd.DataFrame, settings: Settings) -> dict[str, pd.DataFrame]:
    """Dimension rows come from the latest year in which each code appears (titles can be revised)."""
    latest = oews.sort_values("year").groupby("soc_code", as_index=False).last()
    occ = pd.DataFrame({
        "soc_code": latest["soc_code"],
        "occ_title": latest["occ_title"],
        "major_group": latest["soc_code"].str[:2] + "-0000",
        "focal_role": latest["soc_code"].map(settings.focal_occupations),
        "soc_vintage": "2018 SOC",
    })
    ind_latest = oews.sort_values("year").groupby("naics_code", as_index=False).last()
    ind = pd.DataFrame({
        "naics_code": ind_latest["naics_code"],
        "naics_title": ind_latest["naics_title"],
        "industry_level": ind_latest["industry_level"],
        "naics_sector": ind_latest["naics_code"].str[:2],
    })
    yrs = pd.DataFrame({"year": settings.years})
    yrs["post"] = (yrs["year"] >= settings.post_start_year).astype(int)
    yrs["period"] = yrs["post"].map({0: "pre", 1: "post"})
    yrs["post_delayed"] = (yrs["year"] >= settings.delayed_post_start_year).astype(int)
    yrs["reference_month"] = "May"
    return {"dim_occupation": occ, "dim_industry": ind, "dim_year": yrs}
