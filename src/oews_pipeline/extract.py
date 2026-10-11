"""Extract: read source files exactly as published (all columns as text) and fingerprint them."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import pandas as pd

from .config import SourceFile

log = logging.getLogger(__name__)

OEWS_REQUIRED = ["NAICS", "NAICS_TITLE", "I_GROUP", "OCC_CODE", "OCC_TITLE", "O_GROUP",
                 "TOT_EMP", "EMP_PRSE", "A_MEAN", "MEAN_PRSE"]
EXPOSURE_REQUIRED = ["O*NET-SOC Code", "Title"]
JOBZONE_REQUIRED = ["O*NET-SOC Code", "Title", "Job Zone"]


class ExtractError(RuntimeError):
    """A source file is unreadable or lacks required columns."""
    pass


@dataclass
class Extracted:
    """A source file's raw text frame plus its SHA-256 and size, for lineage."""
    source: SourceFile
    frame: pd.DataFrame
    sha256: str
    size_bytes: int


def _sha256(path) -> str:
    """Return the SHA-256 hex digest of a file, read in 1 MB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text_table(path, sep=",") -> pd.DataFrame:
    """Read a delimited file with every cell as text; only empty cells become NaN."""
    # Everything as text: suppression symbols (**, *, #) must survive extraction untouched.
    return pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False, na_values=[""],
                       encoding="utf-8-sig")


def _read_any(src: SourceFile, sep=",") -> pd.DataFrame:
    """Read .xlsx/.xls, tab-delimited .txt, or .csv, keeping every cell as text."""
    suffix = src.path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(src.path, dtype=str, keep_default_na=False, na_values=[""])
    elif suffix == ".txt":
        df = _read_text_table(src.path, sep="\t")
    else:
        df = _read_text_table(src.path, sep=sep)
    return df


def _require(df: pd.DataFrame, cols: list[str], src: SourceFile) -> None:
    """Raise ExtractError naming any required column missing from the source."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ExtractError(f"{src.name} ({src.path.name}) is missing required columns {missing}. "
                           f"Found: {list(df.columns)[:20]}")


def extract_oews(src: SourceFile) -> Extracted:
    """Read one OEWS industry-specific file; upper-case headers and verify required columns."""
    df = _read_any(src)
    df.columns = [str(c).strip().upper() for c in df.columns]   # BLS header case varies by year
    _require(df, OEWS_REQUIRED, src)
    if "H_MEAN" not in df.columns:
        df["H_MEAN"] = pd.NA
    log.info("extracted %-10s %7d rows from %s", src.name, len(df), src.path.name)
    return Extracted(src, df, _sha256(src.path), src.path.stat().st_size)


def extract_exposure(src: SourceFile, measure: str) -> Extracted:
    """Read the Eloundou et al. occupation-level exposure file and verify required columns."""
    df = _read_any(src)
    df.columns = [str(c).strip() for c in df.columns]
    _require(df, EXPOSURE_REQUIRED + [measure], src)
    log.info("extracted %-10s %7d rows from %s", src.name, len(df), src.path.name)
    return Extracted(src, df, _sha256(src.path), src.path.stat().st_size)


def extract_job_zones(src: SourceFile) -> Extracted:
    """Read the O*NET Job Zones file and verify required columns."""
    df = _read_any(src)
    df.columns = [str(c).strip() for c in df.columns]
    _require(df, JOBZONE_REQUIRED, src)
    log.info("extracted %-10s %7d rows from %s", src.name, len(df), src.path.name)
    return Extracted(src, df, _sha256(src.path), src.path.stat().st_size)
