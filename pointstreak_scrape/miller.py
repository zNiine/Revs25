#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Find ALPB hitters who met or got close to:
  Runs >= 100, HR >= 20, SB >= 40
Close windows: within 20 runs, 5 HR, 10 SB (i.e., R>=80, HR>=15, SB>=30)

Input:  pointstreak_alpb_batters.csv (from the scraper)
Output: alpb_power_speed_candidates.csv
"""

import csv
import math

IN_PATH = "pointstreak_alpb_batters.csv"
OUT_PATH = "alpb_power_speed_candidates.csv"

# Targets and "close" windows (below the targets)
TARGETS = {"R": 100, "HR": 20, "SB": 40}
CLOSE_WITHIN = {"R": 20, "HR": 5, "SB": 10}  # how far *below* target we still consider "close"

# Some pages can label columns slightly differently; map synonyms to canonical keys.
HEADER_ALIASES = {
    "R": {"r", "runs"},
    "HR": {"hr", "home runs", "home run"},
    "SB": {"sb", "stolen base", "stolen bases"},
    "Player": {"player"},
    "Season": {"season"},
    "Team": {"team"},
    "season_id": {"season_id"},
    "team_id": {"team_id"},
    "player_id": {"player_id"},
}

def canon_name(h):
    """Return canonical header name if recognized, else the original."""
    low = h.strip().lower()
    for canon, alts in HEADER_ALIASES.items():
        if low == canon.lower() or low in alts:
            return canon
    return h  # keep as-is

def to_number(x):
    if x is None:
        return 0
    s = str(x).strip()
    if s == "" or s == "-":
        return 0
    # handle things like ".278" or "1,234"
    s = s.replace(",", "")
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        # last resort: strip non-numeric
        num = "".join(ch for ch in s if ch.isdigit() or ch == ".")
        if num == "" or num == ".":
            return 0
        try:
            return float(num) if "." in num else int(num)
        except:
            return 0

def qualifies(row):
    """
    Return ("met" | "close" | None) for the triple condition in the same season.
    We require R, HR, SB all to be >= close floors; and mark "met" only if all >= targets.
    """
    R = to_number(row.get("R"))
    HR = to_number(row.get("HR"))
    SB = to_number(row.get("SB"))

    met = (R >= TARGETS["R"] and HR >= TARGETS["HR"] and SB >= TARGETS["SB"])
    if met:
        return "met"

    # Close if each is at least (target - window)
    close = (
        R >= (TARGETS["R"] - CLOSE_WITHIN["R"]) and
        HR >= (TARGETS["HR"] - CLOSE_WITHIN["HR"]) and
        SB >= (TARGETS["SB"] - CLOSE_WITHIN["SB"])
    )
    return "close" if close else None

def main():
    # Read & normalize headers
    with open(IN_PATH, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        field_map = {h: canon_name(h) for h in rdr.fieldnames}

        rows = []
        for raw in rdr:
            r = {field_map[k]: v for k, v in raw.items()}
            status = qualifies(r)
            if status:
                r["Status"] = status
                # For convenience, add “distance to target” fields (negative means short of target)
                r["R_from_100"]  = to_number(r.get("R"))  - TARGETS["R"]
                r["HR_from_20"]  = to_number(r.get("HR")) - TARGETS["HR"]
                r["SB_from_40"]  = to_number(r.get("SB")) - TARGETS["SB"]
                rows.append(r)

    # Sort: met first, then by Season desc (if numeric), then by (R+HR+SB) desc
    def season_key(x):
        s = str(x.get("season_id", "0"))
        try:
            return int(s)
        except:
            return 0

    def power_speed_sum(x):
        return to_number(x.get("R")) + to_number(x.get("HR")) + to_number(x.get("SB"))

    rows.sort(key=lambda r: (0 if r["Status"] == "met" else 1, -season_key(r), -power_speed_sum(r)))

    # Pick tidy columns for output
    keep_cols = [
        "Status", "Season", "season_id", "Team", "team_id",
        "Player", "player_id",
        "R", "HR", "SB",
        "R_from_100", "HR_from_20", "SB_from_40",
        "stats_url",
    ]
    # keep any that exist
    out_headers = [c for c in keep_cols if c in (rows[0].keys() if rows else keep_cols)]

    # Write CSV
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_headers)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in out_headers})

    print(f"Wrote {len(rows)} players → {OUT_PATH}")
    # Also print a small preview
    for r in rows[:25]:
        print(f'{r.get("Status").upper():4} | {r.get("Season")} | {r.get("Team")} | {r.get("Player")} '
              f'R={r.get("R")} HR={r.get("HR")} SB={r.get("SB")}')

if __name__ == "__main__":
    main()
