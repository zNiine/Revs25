#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SB rate leaders (min attempts filter) for Pointstreak ALPB batting data.

- Reads: pointstreak_alpb_batters.csv (default; override with --in)
- Attempts = SB + CS
- Filters Attempts >= MIN_ATTEMPTS (default 50; override with --min-attempts)
- SB_Rate = SB / (SB + CS)
- Writes: sb_rate_leaders_min50.csv (default; override with --out)

Adds robust header mapping, diagnostics, and always writes an output file.
"""

import csv
import argparse
import os
from typing import Dict, Any

DEFAULT_IN = "pointstreak_alpb_batters.csv"
DEFAULT_OUT = "sb_rate_leaders_min50.csv"
DEFAULT_MIN_ATTEMPTS = 50

# Canonical header mapping (lowercased comparison)
HEADER_ALIASES = {
    "season": {"season"},
    "team": {"team"},
    "season_id": {"season_id"},
    "team_id": {"team_id"},
    "player": {"player"},
    "player_id": {"player_id"},
    "sb": {"sb", "stolen base", "stolen bases"},
    "cs": {"cs", "caught stealing", "caught stealings"},
    "r": {"r", "runs"},
    "hr": {"hr", "home runs", "home run"},
    "rbi": {"rbi", "runs batted in"},
    "bb": {"bb", "walks"},
    "so": {"so", "strike outs", "strikeouts"},
    "avg": {"avg", "batting average"},
    "stats_url": {"stats_url", "url", "stats link"},
}

def canon(h: str) -> str:
    low = (h or "").strip().lower()
    for canon_name, alts in HEADER_ALIASES.items():
        if low == canon_name or low in alts:
            return canon_name  # return canonical *lowercase* key
    return low  # fall back to lowercase original for transparency

def to_int(x) -> int:
    if x is None:
        return 0
    s = str(x).strip().replace(",", "")
    if s in ("", "-", "—"):
        return 0
    try:
        return int(float(s))
    except:
        digits = "".join(ch for ch in s if ch.isdigit() or ch == ".")
        try:
            return int(float(digits)) if digits else 0
        except:
            return 0

def to_float(x) -> float:
    if x is None:
        return 0.0
    s = str(x).strip().replace(",", "")
    if s in ("", "-", "—"):
        return 0.0
    try:
        return float(s)
    except:
        filt = "".join(ch for ch in s if ch.isdigit() or ch == ".")
        try:
            return float(filt) if filt else 0.0
        except:
            return 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default=DEFAULT_IN, help="Input CSV path")
    ap.add_argument("--out", dest="out_path", default=DEFAULT_OUT, help="Output CSV path")
    ap.add_argument("--min-attempts", dest="min_attempts", type=int,
                    default=DEFAULT_MIN_ATTEMPTS, help="Minimum (SB+CS) attempts")
    args = ap.parse_args()

    in_path = args.in_path
    out_path = args.out_path
    min_attempts = args.min_attempts

    if not os.path.exists(in_path):
        print(f"[ERROR] Input file not found: {in_path}")
        print("        (Use --in PATH to point at your CSV.)")
        # still write an empty stub so you know it ran
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Season","season_id","Team","team_id","Player","player_id",
                "SB","CS","Attempts","SB_Rate","stats_url","_note"
            ])
            w.writeheader()
            w.writerow({"_note": f"Input file not found: {in_path}"})
        print(f"[INFO] Wrote stub output -> {out_path}")
        return

    # Load & normalize
    with open(in_path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        raw_headers = rdr.fieldnames or []
        fmap = {h: canon(h) for h in raw_headers}
        data = [{fmap[k]: v for k, v in row.items()} for row in rdr]

    print(f"[INFO] Read {len(data)} rows from {in_path}")
    print("[INFO] Header mapping (original -> canonical):")
    for orig, can in fmap.items():
        print(f"   - {orig}  ->  {can}")

    # Determine whether required fields exist after mapping
    required = {"sb", "cs"}
    have_required = required.issubset(set(fmap.values()))
    if not have_required:
        print("[WARN] Required columns not found after mapping (need SB and CS).")
        print("       Available canonical columns:", sorted(set(fmap.values())))
        # write stub file with explanation
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "Season","season_id","Team","team_id","Player","player_id",
                "SB","CS","Attempts","SB_Rate","stats_url","_note"
            ])
            w.writeheader()
            w.writerow({"_note": "Missing SB/CS columns after header mapping."})
        print(f"[INFO] Wrote stub output -> {out_path}")
        return

    out_rows = []
    for r in data:
        sb = to_int(r.get("sb"))
        cs = to_int(r.get("cs"))
        attempts = sb + cs
        if attempts < min_attempts:
            continue
        rate = sb / attempts if attempts > 0 else 0.0

        out_rows.append({
            "Season": r.get("season", ""),
            "season_id": r.get("season_id", ""),
            "Team": r.get("team", ""),
            "team_id": r.get("team_id", ""),
            "Player": r.get("player", ""),
            "player_id": r.get("player_id", ""),
            "SB": sb,
            "CS": cs,
            "Attempts": attempts,
            "SB_Rate": round(rate, 4),
            "stats_url": r.get("stats_url", r.get("url", "")),
        })

    # Sort: best rate desc, then more attempts, then more SB
    out_rows.sort(key=lambda x: (-to_float(x["SB_Rate"]), -to_int(x["Attempts"]), -to_int(x["SB"])))

    fieldnames = ["Season","season_id","Team","team_id","Player","player_id",
                  "SB","CS","Attempts","SB_Rate","stats_url"]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    print(f"[INFO] Qualifying rows (Attempts >= {min_attempts}): {len(out_rows)}")
    print(f"[OK] Wrote -> {out_path}")

    # Quick preview
    for r in out_rows[:20]:
        print(f'{r["Season"]} | {r["Team"]} | {r["Player"]}: '
              f'{r["SB"]}-{r["CS"]} ({r["SB_Rate"]:.3f}) in {r["Attempts"]} att')

if __name__ == "__main__":
    main()
