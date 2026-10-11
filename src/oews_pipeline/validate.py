"""Validation layer: Pydantic record contracts + a reject log that quarantines bad rows.

Every row that leaves `transform` has passed one of these models. Rows that fail are
never silently dropped: they go to `RejectLog`, which is written to the
`rejected_record` table with the raw source values and a reason code.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SOC_PATTERN = r"^\d{2}-\d{4}$"
ONET_PATTERN = r"^\d{2}-\d{4}\.\d{2}$"
NAICS_PATTERN = r"^\d{6}$"

# Reason codes -> action taken. This table is reproduced in the quality report.
REASON_ACTIONS = {
    "INVALID_SOC":        "Rejected: OCC_CODE not in SOC 'NN-NNNN' form; row quarantined.",
    "INVALID_NAICS":      "Rejected: NAICS not a 6-digit code after padding; row quarantined.",
    "NON_NUMERIC":        "Rejected: numeric field held a value that is neither a number nor a documented BLS symbol.",
    "RANGE":              "Rejected: value outside its valid range (e.g., negative employment, rating > 1).",
    "MISSING_REQUIRED":   "Rejected: required identifier or title is blank.",
    "DUPLICATE_EXACT":    "Extra identical copy quarantined; one copy kept.",
    "DUPLICATE_CONFLICT": "All copies quarantined: same key, different values (cannot pick a truth).",
    "INVALID_ONET":       "Rejected: O*NET-SOC code not in 'NN-NNNN.NN' form.",
}


class OewsRecord(BaseModel):
    """One OEWS estimate at detailed-occupation x industry x year grain (post-parse)."""
    model_config = ConfigDict(extra="forbid")

    soc_code: str = Field(pattern=SOC_PATTERN)
    occ_title: str = Field(min_length=1)
    naics_code: str = Field(pattern=NAICS_PATTERN)
    naics_title: str = Field(min_length=1)
    industry_level: str
    year: int = Field(ge=2000, le=2100)
    tot_emp: Optional[int] = Field(default=None, ge=0)
    emp_prse: Optional[float] = Field(default=None, ge=0)
    a_mean: Optional[float] = Field(default=None, gt=0, lt=1_000_000)
    h_mean: Optional[float] = Field(default=None, gt=0, lt=1_000)
    mean_prse: Optional[float] = Field(default=None, ge=0)
    emp_suppressed: int = Field(ge=0, le=1)
    wage_suppressed: int = Field(ge=0, le=1)
    wage_topcoded: int = Field(ge=0, le=1)
    source_file: str

    @model_validator(mode="after")
    def flags_consistent(self):
        """Suppression and top-code flags must coincide with NULL values."""
        if self.emp_suppressed and self.tot_emp is not None:
            raise ValueError("emp_suppressed=1 but tot_emp present")
        if (self.wage_suppressed or self.wage_topcoded) and self.a_mean is not None:
            raise ValueError("wage flag set but a_mean present")
        return self


class ExposureRecord(BaseModel):
    """One Eloundou et al. exposure row at O*NET-SOC granularity."""
    model_config = ConfigDict(extra="forbid")
    onet_code: str = Field(pattern=ONET_PATTERN)
    title: str = Field(min_length=1)
    exposure_alpha: Optional[float] = Field(default=None, ge=0, le=1)
    exposure_beta: Optional[float] = Field(default=None, ge=0, le=1)
    exposure_gamma: Optional[float] = Field(default=None, ge=0, le=1)
    exposure_main: float = Field(ge=0, le=1)


class JobZoneRecord(BaseModel):
    """One O*NET Job Zone row at O*NET-SOC granularity."""
    model_config = ConfigDict(extra="forbid")
    onet_code: str = Field(pattern=ONET_PATTERN)
    title: str = Field(min_length=1)
    job_zone: int = Field(ge=1, le=5)


def classify_validation_error(err: ValidationError) -> tuple[str, str]:
    """Map a Pydantic error to (reason_code, detail)."""
    first = err.errors()[0]
    loc = ".".join(str(p) for p in first.get("loc", ())) or "record"
    etype = first.get("type", "")
    if loc == "soc_code":
        code = "INVALID_SOC"
    elif loc == "naics_code":
        code = "INVALID_NAICS"
    elif loc == "onet_code":
        code = "INVALID_ONET"
    elif etype in {"string_too_short", "missing"}:
        code = "MISSING_REQUIRED"
    elif etype.startswith(("greater_than", "less_than")):
        code = "RANGE"
    else:
        code = "RANGE" if "flag" in str(first.get("msg", "")) else "NON_NUMERIC"
    return code, f"{loc}: {first.get('msg')}"


@dataclass
class RejectLog:
    """Collects quarantined rows during a run; written to rejected_record at load time."""
    rows: list[dict] = field(default_factory=list)

    def add(self, source_name: str, reason_code: str, detail: str, raw: dict, record_key: str | None = None):
        """Record one quarantined row with its raw values, reason code, and key."""
        clean = {k: (None if v is None or (isinstance(v, float) and v != v) else str(v)) for k, v in raw.items()}
        self.rows.append({
            "source_name": source_name,
            "record_key": record_key,
            "reason_code": reason_code,
            "detail": detail,
            "raw_record": json.dumps(clean, sort_keys=True),
        })

    def counts(self) -> Counter:
        """Count rejected rows by (source, reason code)."""
        return Counter((r["source_name"], r["reason_code"]) for r in self.rows)

    def __len__(self) -> int:
        """Number of rejected rows collected."""
        return len(self.rows)
