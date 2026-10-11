"""Load: idempotent upserts keyed on natural keys, with change detection on facts."""
from __future__ import annotations

import hashlib
import logging
import sqlite3

import pandas as pd

log = logging.getLogger(__name__)

FACT_KEY = ["soc_code", "naics_code", "year"]
FACT_VALUES = ["tot_emp", "emp_prse", "a_mean", "h_mean", "mean_prse",
               "emp_suppressed", "wage_suppressed", "wage_topcoded", "source_file"]


def _py(v):
    """Convert pandas/numpy scalars and missing values to plain Python for sqlite3."""
    if v is None or v is pd.NA or (isinstance(v, float) and v != v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def _rows(df: pd.DataFrame, cols: list[str]) -> list[tuple]:
    """Convert selected DataFrame columns to a list of plain-Python tuples for executemany."""
    return [tuple(_py(v) for v in row) for row in df[cols].itertuples(index=False, name=None)]


def upsert(conn: sqlite3.Connection, table: str, df: pd.DataFrame, key: list[str]) -> int:
    """INSERT ... ON CONFLICT(key) DO UPDATE only when a non-key value actually differs."""
    if df.empty:
        return 0
    cols = list(df.columns)
    non_key = [c for c in cols if c not in key]
    set_clause = ", ".join(f"{c} = excluded.{c}" for c in non_key)
    changed = " OR ".join(f"{table}.{c} IS NOT excluded.{c}" for c in non_key)
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
           f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {set_clause} WHERE {changed}")
    before = conn.total_changes
    conn.executemany(sql, _rows(df, cols))
    return conn.total_changes - before


def row_hash(df: pd.DataFrame) -> pd.Series:
    """Return a 16-hex SHA-256 per row over FACT_VALUES, used to detect changed facts."""
    def h(row) -> str:
        payload = "|".join("" if _py(v) is None else repr(_py(v)) for v in row)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
    return pd.Series([h(r) for r in df[FACT_VALUES].itertuples(index=False, name=None)], index=df.index)


def load_facts(conn: sqlite3.Connection, facts: pd.DataFrame, run_id: int) -> dict:
    """Insert new keys, update changed keys, leave unchanged keys untouched.

    Keys already in the database for a loaded year but absent from this run's source are
    *not* deleted; they are counted and reported as `stale_keys_not_in_source` so a
    refresh never silently changes row counts.
    """
    facts = facts.copy()
    facts["row_hash"] = row_hash(facts)
    years = sorted(int(y) for y in facts["year"].unique())
    q = f"SELECT soc_code, naics_code, year, row_hash FROM fact_oews_estimate WHERE year IN ({','.join('?' * len(years))})"
    existing = pd.DataFrame([tuple(r) for r in conn.execute(q, years).fetchall()],
                            columns=FACT_KEY + ["existing_hash"])
    m = facts.merge(existing, on=FACT_KEY, how="left", indicator=True)
    new = m[m["_merge"] == "left_only"]
    changed = m[(m["_merge"] == "both") & (m["row_hash"] != m["existing_hash"])]
    unchanged = int(((m["_merge"] == "both") & (m["row_hash"] == m["existing_hash"])).sum())
    stale = existing.merge(facts[FACT_KEY], on=FACT_KEY, how="left", indicator=True)
    stale_n = int((stale["_merge"] == "left_only").sum())

    cols = FACT_KEY + FACT_VALUES + ["row_hash"]
    if len(new):
        ins = new[cols].copy()
        ins["first_loaded_run"] = run_id
        ins["last_changed_run"] = run_id
        conn.executemany(
            f"INSERT INTO fact_oews_estimate ({', '.join(ins.columns)}) VALUES ({', '.join('?' * len(ins.columns))})",
            _rows(ins, list(ins.columns)))
    if len(changed):
        upd = changed[FACT_VALUES + ["row_hash"] + FACT_KEY].copy()
        set_clause = ", ".join(f"{c} = ?" for c in FACT_VALUES + ["row_hash"])
        conn.executemany(
            f"UPDATE fact_oews_estimate SET {set_clause}, last_changed_run = {int(run_id)} "
            f"WHERE soc_code = ? AND naics_code = ? AND year = ?",
            _rows(upd, list(upd.columns)))
    if stale_n:
        log.warning("%d fact keys exist in the database but not in this run's source; kept, not deleted", stale_n)
    result = {"inserted": int(len(new)), "updated": int(len(changed)), "unchanged": unchanged,
              "stale_keys_not_in_source": stale_n}
    log.info("facts: inserted=%d updated=%d unchanged=%d stale=%d", *result.values())
    return result


def write_rejects(conn: sqlite3.Connection, rejects: list[dict], run_id: int) -> None:
    """Insert quarantined rows into rejected_record, tagged with this run's id."""
    conn.executemany(
        "INSERT INTO rejected_record (run_id, source_name, record_key, reason_code, detail, raw_record) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(run_id, r["source_name"], r["record_key"], r["reason_code"], r["detail"], r["raw_record"]) for r in rejects])
