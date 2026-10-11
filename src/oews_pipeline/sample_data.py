"""Generate the committed SYNTHETIC sample. Same file layouts as the real sources; values are invented.

The sample deliberately contains the defects the pipeline must handle, so a reviewer can see
every validation path fire without access to the real files:
  - BLS suppression/top-code symbols (**, *, #) and comma-formatted numbers
  - aggregate rows outside the panel grain (totals, major groups, 3-digit industries)
  - an exact duplicate, a conflicting duplicate, a malformed SOC code, a negative employment
    count, a non-numeric value, a blank title, lowercase headers, 4-character NAICS codes
  - exposure rows with an out-of-range rating and a malformed O*NET code
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from .config import SAMPLE_DIR

YEARS = [2021, 2022, 2023, 2024, 2025]

# (SOC, title, base annual mean wage, synthetic exposure gamma, job zone)
OCCUPATIONS = [
    ("13-2051", "Financial and Investment Analysts", 98000, 0.82, 4),
    ("43-3031", "Bookkeeping, Accounting, and Auditing Clerks", 46000, 0.90, 3),
    ("13-2011", "Accountants and Auditors", 84000, 0.78, 4),
    ("13-2041", "Credit Analysts", 89000, 0.80, 4),
    ("13-2052", "Personal Financial Advisors", 119000, 0.62, 4),
    ("11-3031", "Financial Managers", 166000, 0.55, 4),
    ("41-3031", "Securities, Commodities, and Financial Services Sales Agents", 105000, 0.58, 4),
    ("43-3071", "Tellers", 37000, 0.60, 2),
    ("43-4051", "Customer Service Representatives", 41000, 0.72, 2),
    ("43-9021", "Data Entry Keyers", 39000, 0.95, 2),
    ("43-6014", "Secretaries and Administrative Assistants, Except Legal, Medical, and Executive", 43000, 0.74, 2),
    ("15-1252", "Software Developers", 132000, 0.88, 4),
    ("15-2031", "Operations Research Analysts", 95000, 0.79, 5),
    ("15-2041", "Statisticians", 104000, 0.70, 5),
    ("13-1111", "Management Analysts", 104000, 0.66, 4),
    ("23-2011", "Paralegals and Legal Assistants", 62000, 0.77, 3),
    ("29-1141", "Registered Nurses", 89000, 0.30, 3),
    ("53-7062", "Laborers and Freight, Stock, and Material Movers, Hand", 38000, 0.06, 1),
    ("47-2061", "Construction Laborers", 46000, 0.04, 2),
    ("35-2014", "Cooks, Restaurant", 35000, 0.05, 2),
]

# industry wage premium (securities/investment firms pay more -> exercises BLS '#' top-coding)
WAGE_PREMIUM = {"523100": 1.30, "523900": 1.25}

INDUSTRIES = [
    ("522100", "Depository Credit Intermediation"),
    ("523100", "Securities and Commodity Contracts Intermediation and Brokerage"),
    ("523900", "Other Financial Investment Activities"),
    ("524100", "Insurance Carriers"),
    ("541200", "Accounting, Tax Preparation, Bookkeeping, and Payroll Services"),
    ("541500", "Computer Systems Design and Related Services"),
    ("551100", "Management of Companies and Enterprises"),
    ("622100", "General Medical and Surgical Hospitals"),
    ("493100", "Warehousing and Storage"),
    ("722500", "Restaurants and Other Eating Places"),
]

HEADER = ["AREA", "AREA_TITLE", "AREA_TYPE", "PRIM_STATE", "NAICS", "NAICS_TITLE", "I_GROUP", "OWN_CODE",
          "OCC_CODE", "OCC_TITLE", "O_GROUP", "TOT_EMP", "EMP_PRSE", "PCT_TOTAL", "H_MEAN", "A_MEAN", "MEAN_PRSE"]
TOP_CODE = 239200


def _fmt_int(x: int, rng) -> str:
    """Format an integer, sometimes with thousands separators as in BLS CSV exports."""
    return f"{x:,}" if rng.random() < 0.3 else str(x)       # some comma-formatted like BLS CSV exports


def generate(out_dir: Path = SAMPLE_DIR, seed: int = 751) -> list[Path]:
    """Write the seeded synthetic OEWS, exposure, and Job Zone files to out_dir; return their paths."""
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Which occupation appears in which industry is fixed across years (like a real panel), ~70% density
    presence = {(s, n): rng.random() < 0.7 for s, *_ in OCCUPATIONS for n, _ in INDUSTRIES}
    base_emp = {k: int(rng.lognormal(7.2, 1.1)) + 30 for k in presence}
    exposure = {s: e for s, _, _, e, _ in OCCUPATIONS}
    written = []

    for year in YEARS:
        post = year >= 2023
        rows = []
        for naics, ntitle in INDUSTRIES:
            ind_total = 0
            for soc, title, wage, exp_g, _ in OCCUPATIONS:
                if not presence[(soc, naics)]:
                    continue
                trend = 1.02 ** (year - 2021)
                effect = (1 - 0.06 * (exp_g - 0.6) * (year - 2022)) if post else 1.0
                emp = max(30, int(base_emp[(soc, naics)] * trend * effect * rng.normal(1, 0.03)))
                ind_total += emp
                a_mean = round(wage * WAGE_PREMIUM.get(naics, 1.0) * (1.035 ** (year - 2021)) * rng.normal(1, 0.04), -1)
                emp_s = _fmt_int(emp, rng)
                a_s = f"{int(a_mean)}"
                h_s = f"{a_mean / 2080:.2f}"
                if a_mean >= TOP_CODE:
                    a_s, h_s = "#", "#"
                r = rng.random()
                if r < 0.07:
                    emp_s = "**"                                   # employment suppressed
                elif r < 0.10:
                    a_s, h_s = "*", "*"                            # wage not available
                rows.append(["99", "U.S.", "1", "US", naics, ntitle, "4-digit", "1235", soc, title, "detailed",
                             emp_s, f"{rng.uniform(1, 25):.1f}", f"{rng.uniform(0.1, 9):.2f}", h_s, a_s,
                             f"{rng.uniform(0.5, 6):.1f}"])
            # aggregate rows that are out of the panel's grain
            rows.append(["99", "U.S.", "1", "US", naics, ntitle, "4-digit", "1235", "00-0000", "All Occupations",
                         "total", str(ind_total), "1.0", "100.00", "30.00", "62400", "0.8"])
            rows.append(["99", "U.S.", "1", "US", naics, ntitle, "4-digit", "1235", "13-0000",
                         "Business and Financial Operations Occupations", "major", "5000", "2.0", "10.00",
                         "40.00", "83200", "1.0"])
        rows.append(["99", "U.S.", "1", "US", "522000", "Credit Intermediation and Related Activities", "3-digit",
                     "1235", "13-2051", "Financial and Investment Analysts", "detailed", "21000", "3.0", "1.2",
                     "50.00", "104000", "1.5"])

        # ---- injected defects (one family per year so each is easy to find)
        header = list(HEADER)
        if year == 2021:
            rows[3][11] = "n/a"                                    # NON_NUMERIC employment
            for r in rows[:4]:
                r[4] = r[4][:4]                                   # '522100' -> '5221' (normalization path)
        elif year == 2022:
            rows.insert(6, list(rows[5]))                          # exact duplicate
        elif year == 2023:
            dup = list(rows[8])                                    # conflicting duplicate: same key, new wage
            dup[15] = str(int(rows[8][15]) + 5000) if rows[8][15].isdigit() else "70000"
            rows.insert(9, dup)
            rows[12][9] = ""                                       # MISSING_REQUIRED title
        elif year == 2024:
            rows[2][8] = "132051"                                  # INVALID_SOC
            header = [h.lower() for h in header]                   # header case drift across BLS years
        elif year == 2025:
            rows[4][11] = "-40"                                    # RANGE: negative employment

        path = out_dir / f"oews_nat4d_M{year}_sample.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        written.append(path)

    # ---- Exposure (Eloundou et al. occ_level layout, O*NET-SOC granularity)
    exp_path = out_dir / "eloundou_occ_level_sample.csv"
    with open(exp_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["O*NET-SOC Code", "Title", "dv_rating_alpha", "dv_rating_beta", "dv_rating_gamma",
                    "human_rating_alpha", "human_rating_beta", "human_rating_gamma"])
        for soc, title, _, g, _ in OCCUPATIONS:
            if soc == "47-2061":
                continue                                           # panel SOC with no exposure score
            codes = [f"{soc}.00"] + ([f"{soc}.01"] if soc in {"13-2051", "15-1252", "43-4051"} else [])
            for i, code in enumerate(codes):
                gg = min(1.0, max(0.0, g + (0.04 if i else 0)))
                a = round(gg * 0.45, 4); b = round((a + gg) / 2, 4)
                w.writerow([code, title, a, b, round(gg, 4), round(a * 0.95, 4), round(b * 0.95, 4), round(gg * 0.95, 4)])
        w.writerow(["19-1029.01", "Bioinformatics Scientists", 0.30, 0.50, 0.70, 0.3, 0.5, 0.7])  # not in panel
        w.writerow(["13-2099.01", "Financial Quantitative Analysts", 0.50, 0.80, 1.30, 0.5, 0.8, 1.0])  # RANGE
        w.writerow(["132061", "Financial Examiners", 0.40, 0.60, 0.80, 0.4, 0.6, 0.8])  # INVALID_ONET
    written.append(exp_path)

    # ---- O*NET Job Zones layout (tab-delimited)
    jz_path = out_dir / "onet_job_zones_sample.txt"
    with open(jz_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["O*NET-SOC Code", "Title", "Job Zone", "Date", "Domain Source"])
        for soc, title, _, _, jz in OCCUPATIONS:
            w.writerow([f"{soc}.00", title, jz, "08/2022", "Analyst"])
    written.append(jz_path)
    return written
