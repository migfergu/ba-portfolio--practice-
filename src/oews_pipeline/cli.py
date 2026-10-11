"""Command-line entry point: `uv run oews-pipeline <command>`."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import DEFAULT_DB, LOG_DIR, ConfigError
from .extract import ExtractError


def setup_logging(verbose: bool = False) -> Path:
    """Log to the console and a timestamped file in logs/; return the log file path."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"pipeline_{datetime.now():%Y%m%d_%H%M%S}.log"
    fmt = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format=fmt,
                        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file, encoding="utf-8")],
                        force=True)
    return log_file


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to run, rerun-check, or make-sample. Returns a process exit code."""
    p = argparse.ArgumentParser(prog="oews-pipeline", description="Build the GenAI exposure x OEWS SQLite database.")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="build or refresh the database end to end")
    run.add_argument("--source", choices=["sample", "raw"], default="sample",
                     help="sample = committed synthetic files; raw = real files in data/raw/ (authorized users)")
    run.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite path (default {DEFAULT_DB.name})")
    run.add_argument("--data-dir", type=Path, default=None, help="override the folder holding source files")

    rc = sub.add_parser("rerun-check", help="run twice on a fresh DB and write docs/RERUN_CHECK.md")
    rc.add_argument("--source", choices=["sample", "raw"], default="sample")

    sub.add_parser("make-sample", help="regenerate the synthetic sample in data/sample/")
    for sp in (run, rc):
        sp.add_argument("-v", "--verbose", action="store_true")

    args = p.parse_args(argv)
    log_file = setup_logging(getattr(args, "verbose", False))
    log = logging.getLogger("oews_pipeline")
    log.info("log file: %s", log_file)

    try:
        if args.command == "run":
            from .pipeline import run_pipeline
            res = run_pipeline(args.source, db_path=args.db, data_dir=args.data_dir)
            print(f"\nOK  run {res['run_id']}: {res['table_counts']['fact_oews_estimate']} facts, "
                  f"{res['rows_rejected']} rejected, load {res['load_outcome']}\n"
                  f"    database: {args.db}\n    report:   docs/QUALITY_REPORT.md")
        elif args.command == "rerun-check":
            from .rerun_check import run_check
            ok = run_check(args.source)
            print(f"\n{'PASS' if ok else 'FAIL'}  re-runnability check -> docs/RERUN_CHECK.md")
            return 0 if ok else 1
        elif args.command == "make-sample":
            from .sample_data import generate
            for path in generate():
                log.info("wrote %s", path)
        return 0
    except (ConfigError, ExtractError) as exc:
        log.error("%s", exc)
        return 2
    except Exception:  # noqa: BLE001 - logged with traceback in pipeline; non-zero exit for callers
        log.error("pipeline failed; see %s", log_file)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
