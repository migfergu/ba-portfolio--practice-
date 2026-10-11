"""Paths and source manifest loading."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.toml"
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_DB = PROJECT_ROOT / "data" / "processed" / "oews_genai.db"
LOG_DIR = PROJECT_ROOT / "logs"
REPORT_DIR = PROJECT_ROOT / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"


class ConfigError(RuntimeError):
    """Raised when the manifest or a required source file is missing or invalid."""


@dataclass(frozen=True)
class SourceFile:
    """One source file resolved from the manifest."""
    name: str          # logical source: oews_2021, exposure, job_zones
    path: Path
    version: str = ""
    year: int | None = None


@dataclass(frozen=True)
class Settings:
    """Study settings and resolved source files for one run mode (sample or raw)."""
    source_mode: str
    years: list[int]
    post_start_year: int
    delayed_post_start_year: int
    industry_level: str
    occupation_level: str
    exposure_measure: str
    focal_occupations: dict[str, str]
    oews_files: dict[int, SourceFile] = field(default_factory=dict)
    exposure_file: SourceFile | None = None
    job_zones_file: SourceFile | None = None


def load_settings(source_mode: str = "sample", config_path: Path = CONFIG_PATH,
                  data_dir: Path | None = None) -> Settings:
    """Read config/sources.toml and resolve file paths for `sample` or `raw` mode."""
    if source_mode not in {"sample", "raw"}:
        raise ConfigError(f"source must be 'sample' or 'raw', got {source_mode!r}")
    if not config_path.exists():
        raise ConfigError(f"Manifest not found: {config_path}")
    cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    study = cfg["study"]
    block = cfg[source_mode]
    base = data_dir or (SAMPLE_DIR if source_mode == "sample" else RAW_DIR)

    years = [int(y) for y in study["years"]]
    oews = {}
    for y in years:
        fname = block["oews"].get(str(y))
        if fname is None:
            raise ConfigError(f"No OEWS file listed for year {y} in [{source_mode}.oews]")
        oews[y] = SourceFile(f"oews_{y}", base / fname, f"OEWS May {y} national industry-specific", y)

    return Settings(
        source_mode=source_mode,
        years=years,
        post_start_year=int(study["post_start_year"]),
        delayed_post_start_year=int(study["delayed_post_start_year"]),
        industry_level=study["industry_level"],
        occupation_level=study["occupation_level"],
        exposure_measure=study["exposure_measure"],
        focal_occupations=dict(study.get("focal_occupations", {})),
        oews_files=oews,
        exposure_file=SourceFile("exposure", base / block["exposure"]["file"], block["exposure"]["version"]),
        job_zones_file=SourceFile("job_zones", base / block["job_zones"]["file"], block["job_zones"]["version"]),
    )


def check_files_exist(settings: Settings) -> None:
    """Fail fast with an actionable message if any source file is missing."""
    files = list(settings.oews_files.values()) + [settings.exposure_file, settings.job_zones_file]
    missing = [f for f in files if f is not None and not f.path.exists()]
    if missing:
        lines = "\n".join(f"  - {f.name}: {f.path}" for f in missing)
        hint = ("Run `uv run oews-pipeline make-sample` to regenerate the synthetic sample."
                if settings.source_mode == "sample"
                else "Download the real files per docs/DATA_ACCESS.md and place them in data/raw/.")
        raise ConfigError(f"Missing source file(s):\n{lines}\n{hint}")
