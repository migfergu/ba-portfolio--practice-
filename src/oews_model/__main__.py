"""Command line: ``uv run oews-model [run|simulate] [--db PATH]`` or ``--verify-against RUN_LOG``."""
from __future__ import annotations

import argparse
import json
import sys

from oews_eda import data

from . import report
from .estimate import ModelError


def main(argv: list[str] | None = None) -> int:
    """Run the A6 analysis (default), the Monte Carlo calibration, or a checksum verification."""
    ap = argparse.ArgumentParser(prog="oews-model", description="Run the A6 analytics engine.")
    ap.add_argument("command", nargs="?", default="run", choices=["run", "simulate"],
                    help="run = estimates, robustness, validation, figures (default); "
                         "simulate = Monte Carlo calibration of the inference (several minutes)")
    ap.add_argument("--db", default=str(data.DEFAULT_DB), help="Path to the pipeline SQLite database")
    ap.add_argument("--seeds", type=int, default=200, help="simulate: seeds per scenario (default 200)")
    ap.add_argument("--verify-against", metavar="RUN_LOG_JSON",
                    help="Only check that the database's input SHA-256s match a committed model_run_log.json")
    args = ap.parse_args(argv)
    if args.verify_against:
        expected = json.loads(open(args.verify_against, encoding="utf-8").read())["inputs"]
        res = data.compare_manifest(expected, args.db)
        print(res.to_string(index=False))
        ok = bool(res["match"].all())
        print("VERIFIED: inputs identical to the run log" if ok else "MISMATCH: inputs differ from the run log")
        return 0 if ok else 1
    try:
        if args.command == "simulate":
            s = report.simulate(seeds=args.seeds)
            print(s.round(4).to_string(index=False))
            print(f"    outputs: {report.TABLE_DIR}/monte_carlo_*.csv")
            return 0
        s = report.run_all(args.db)
    except (FileNotFoundError, ValueError, ModelError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    m = s["main"]["emp"]
    print(f"OK  A6 on {s['source_mode']} data: {s['panel']['rows']} rows, {s['panel']['cells']} cells, "
          f"{s['panel']['occupation_clusters']} occupation clusters")
    print(f"    beta (log emp per 1 SD exposure x post) = {m['coef']:+.4f}  "
          f"WCR 95% CI [{m['ci_low_wcr']:+.4f}, {m['ci_high_wcr']:+.4f}]  p_wcr = {m['p_wcr']:.4f}  "
          f"p_ri = {m['p_ri']:.4f}  -> {m['practical_verdict']}")
    if s["validation"]:
        v = s["validation"]
        print(f"    known-answer: EDA code {'PASS' if v['eda_code_pass'] else 'FAIL'}, "
              f"seed plausibility {'PASS' if v['eda_sampling_pass'] else 'FAIL'}, "
              f"model recovery {'PASS' if v['model_recovery_pass'] else 'FAIL'}")
    print(f"    outputs: {report.TABLE_DIR} and {report.FIG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
