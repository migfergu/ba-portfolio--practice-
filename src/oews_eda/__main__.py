"""Command line: ``uv run python -m oews_eda [--db PATH]`` regenerates all EDA outputs."""
from __future__ import annotations

import argparse
import json
import sys

from . import data, report


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, run :func:`oews_eda.report.run_all`, and print the headline result."""
    ap = argparse.ArgumentParser(prog="oews-eda", description="Run the A5 exploratory data analysis.")
    ap.add_argument("--db", default=str(data.DEFAULT_DB), help="Path to the pipeline SQLite database")
    ap.add_argument("--verify-against", metavar="RUN_LOG_JSON",
                    help="Only check that the database's input SHA-256s match a committed eda_run_log.json")
    args = ap.parse_args(argv)
    if args.verify_against:
        expected = json.loads(open(args.verify_against, encoding="utf-8").read())["inputs"]
        res = data.compare_manifest(expected, args.db)
        print(res.to_string(index=False))
        ok = bool(res["match"].all())
        print("VERIFIED: inputs identical to the run log" if ok else "MISMATCH: inputs differ from the run log")
        return 0 if ok else 1
    try:
        s = report.run_all(args.db)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    t = s["tests"]["primary_emp_within_industry"]
    print(f"OK  EDA on {s['source_mode']} data: {s['panel']['cells']} cells, {s['panel']['occupations']} occupations")
    print(f"    H1 employment: {t['test_used']} p = {t['p_value']:.4g}, Hedges g = {t['hedges_g']:.2f} -> {t['decision']} ({t['practical_verdict']})")
    print(f"    outputs: {report.FIG_DIR} and {report.TABLE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
