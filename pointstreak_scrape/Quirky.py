#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Quirky hitters finder for Pointstreak ALPB data

Input:
  pointstreak_alpb_batters.csv  (from your scraper)

Output:
  One CSV per quirky combo in the working dir, e.g.:
    quirky__100R_80RBI.csv
    quirky__100R_80RBI_50SB.csv
    quirky__30HR_30SB.csv
    ...

Each output includes: Season/Team/Player IDs, raw stats used, and a Status column
("met" or "close" when a combo defines close windows).
"""

import csv
import re
import os
from typing import Dict, Any, List, Tuple

IN_PATH = "pointstreak_alpb_batters.csv"

# Map common/scraped headers to canonical names
HEADER_ALIASES = {
    "Season": {"season"},
    "Team": {"team"},
    "season_id": {"season_id"},
    "team_id": {"team_id"},
    "Player": {"player"},
    "player_id": {"player_id"},
    "AVG": {"avg", "batting average"},
    "G": {"g", "games"},
    "AB": {"ab", "at bats"},
    "R": {"r", "runs"},
    "H": {"h", "hits"},
    "2B": {"2b", "doubles"},
    "3B": {"3b", "triples"},
    "HR": {"hr", "home runs", "home run"},
    "RBI": {"rbi", "runs batted in"},
    "BB": {"bb", "walks"},
    "HBP": {"hbp", "hit by pitch"},
    "SO": {"so", "strike outs", "strikeouts"},
    "SF": {"sf", "sacrifice fly"},
    "SH": {"sh", "sacrifice hit"},
    "SB": {"sb", "stolen base", "stolen bases"},
    "CS": {"cs", "caught stealing"},
    "DP": {"dp", "double play"},
    "E": {"e", "errors"},
    "stats_url": {"stats_url"},
}

# -------- Define quirky combos here --------
# Use only stats present in the scraped table.
# Each rule = {"name": <file/label>, "clauses": [ ... ], "close": {optional windows}}
# Clause format: {"field": "R", "op": "ge", "value": 100}  (ops: "ge" >=, "le" <=)
# Optional "close" windows only apply to "ge" clauses and mean "within X below".
QUIRKY_COMBOS: List[Dict[str, Any]] = [
    {
        "name": "100R_80RBI",
        "clauses": [
            {"field": "R",   "op": "ge", "value": 100},
            {"field": "RBI", "op": "ge", "value": 80},
        ],
        "close": {  # optional
            "R": 20,     # within 20 of 100 → >= 80
            "RBI": 10,   # within 10 of 80  → >= 70
        },
    },
    {
        "name": "100R_80RBI_50SB",
        "clauses": [
            {"field": "R",   "op": "ge", "value": 100},
            {"field": "RBI", "op": "ge", "value": 80},
            {"field": "SB",  "op": "ge", "value": 50},
        ],
        "close": {"R": 20, "RBI": 10, "SB": 10},
    },
    {
        "name": "30HR_30SB",
        "clauses": [
            {"field": "HR", "op": "ge", "value": 30},
            {"field": "SB", "op": "ge", "value": 30},
        ],
        "close": {"HR": 5, "SB": 5},
    },
    {
        "name": "20HR_40SB",
        "clauses": [
            {"field": "HR", "op": "ge", "value": 20},
            {"field": "SB", "op": "ge", "value": 40},
        ],
        "close": {"HR": 9, "SB": 10},
    },
    {
        "name": "200H_100R",
        "clauses": [
            {"field": "H", "op": "ge", "value": 200},
            {"field": "R", "op": "ge", "value": 100},
        ],
        "close": {"H": 20, "R": 20},
    },
    {
        "name": "50SB_<=60SO",
        "clauses": [
            {"field": "SB", "op": "ge", "value": 50},
            {"field": "SO", "op": "le", "value": 60},
        ],
        # close only makes sense for "ge" SB here
        "close": {"SB": 10},
    },
    {
        "name": "20HR_<=60SO",
        "clauses": [
            {"field": "HR", "op": "ge", "value": 20},
            {"field": "SO", "op": "le", "value": 60},
        ],
        "close": {"HR": 3},
    },
    {
        "name": "AVG330_15HR",
        "clauses": [
            {"field": "AVG", "op": "ge", "value": 0.330},
            {"field": "HR",  "op": "ge", "value": 15},
        ],
        "close": {"AVG": 0.010, "HR": 2},  # within .010 AVG and 2 HR
    },
    {
        "name": "40Doubles_10Triples",
        "clauses": [
            {"field": "2B", "op": "ge", "value": 40},
            {"field": "3B", "op": "ge", "value": 10},
        ],
        "close": {"2B": 5, "3B": 2},
    },
    {
        "name": "80BB_20HR",
        "clauses": [
            {"field": "BB", "op": "ge", "value": 80},
            {"field": "HR", "op": "ge", "value": 20},
        ],
        "close": {"BB": 10, "HR": 3},
    },
]

# ------------------------------------------

def canon(h: str) -> str:
    low = h.strip().lower()
    for c, alts in HEADER_ALIASES.items():
        if low == c.lower() or low in alts:
            return c
    return h

def to_number(x: Any) -> float:
    if x is None:
        return 0.0
    s = str(x).strip()
    if s in ("", "-", "—"):
        return 0.0
    s = s.replace(",", "")
    try:
        return float(s)
    except:
        # extract digits and dot (handles ".278")
        filt = "".join(ch for ch in s if ch.isdigit() or ch == ".")
        if filt in ("", "."):
            return 0.0
        try:
            return float(filt)
        except:
            return 0.0

def meets_clause(row: Dict[str, Any], field: str, op: str, value: float) -> bool:
    val = to_number(row.get(field))
    if op == "ge":
        return val >= value
    elif op == "le":
        return val <= value
    else:
        raise ValueError(f"Unsupported op: {op}")

def meets_clause_close(row: Dict[str, Any], field: str, op: str, value: float, within: float) -> bool:
    val = to_number(row.get(field))
    if op == "ge":
        # within X *below* the target
        return val >= (value - within)
    elif op == "le":
        # optional: define closeness for <= if you want; here we don't apply it
        return meets_clause(row, field, op, value)
    else:
        return False

def status_for_combo(row: Dict[str, Any], combo: Dict[str, Any]) -> str:
    clauses = combo["clauses"]
    # First check "met"
    if all(meets_clause(row, c["field"], c["op"], c["value"]) for c in clauses):
        return "met"
    # Then "close" (only if combo defines close windows)
    cw = combo.get("close")
    if cw:
        if all(
            meets_clause_close(
                row,
                c["field"],
                c["op"],
                c["value"],
                cw.get(c["field"], 0)
            ) for c in clauses
        ):
            return "close"
    return ""

def distances_from_targets(row: Dict[str, Any], combo: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for c in combo["clauses"]:
        f, op, tgt = c["field"], c["op"], float(c["value"])
        val = to_number(row.get(f))
        # Positive means exceeded for >=, negative means short.
        if op == "ge":
            out[f"{f}_from_{tgt:g}"] = round(val - tgt, 3)
        elif op == "le":
            # For <= thresholds, positive means *under* the cap (good), negative means exceeded cap
            out[f"{f}_under_cap_{tgt:g}"] = round(tgt - val, 3)
    return out

def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    return s or "combo"

def main():
    # Read and normalize
    with open(IN_PATH, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        fmap = {h: canon(h) for h in rdr.fieldnames}
        data = [{fmap[k]: v for k, v in row.items()} for row in rdr]

    # For summarizing
    summary: List[Tuple[str, int]] = []

    for combo in QUIRKY_COMBOS:
        label = combo["name"]
        rows_out: List[Dict[str, Any]] = []

        for r in data:
            st = status_for_combo(r, combo)
            if not st:
                continue
            out = dict(r)  # copy
            out["Status"] = st
            out.update(distances_from_targets(r, combo))
            rows_out.append(out)

        if not rows_out:
            summary.append((label, 0))
            continue

        # Order: MET first, newest season_id next, then a simple score
        def season_key(x):
            try:
                return int(str(x.get("season_id", "0")).strip() or "0")
            except:
                return 0

        # crude ranking: sum of tracked ge thresholds
        def score(x):
            sc = 0.0
            for c in combo["clauses"]:
                if c["op"] == "ge":
                    sc += to_number(x.get(c["field"]))
                elif c["op"] == "le":
                    sc += max(0.0, c["value"] - to_number(x.get(c["field"])))
            return sc

        rows_out.sort(key=lambda r: (0 if r["Status"] == "met" else 1, -season_key(r), -score(r)))

        # Choose a tidy column order (leading IDs -> player -> stats used -> rest)
        used_fields = [c["field"] for c in combo["clauses"]]
        dist_fields = [k for k in rows_out[0].keys() if k.startswith(tuple(f"{f}_" for f in used_fields))]

        leading = ["Status", "Season", "season_id", "Team", "team_id", "Player", "player_id"]
        stats = []
        for f in ["AVG","G","AB","R","H","2B","3B","HR","RBI","BB","HBP","SO","SF","SH","SB","CS","DP","E"]:
            if f in used_fields or f in ("R","HR","RBI","SB","AVG","BB","SO","H","2B","3B"):
                stats.append(f)
        tail = [k for k in rows_out[0].keys() if k not in set(leading + stats + dist_fields + ["stats_url"])]
        fieldnames = leading + stats + dist_fields + ["stats_url"] + tail

        out_path = f"quirky__{slugify(label)}.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in rows_out:
                w.writerow({k: r.get(k, "") for k in fieldnames})

        summary.append((label, len(rows_out)))
        print(f"Wrote {len(rows_out)} rows -> {out_path}")

    print("\nSummary:")
    for name, cnt in summary:
        print(f"  {name:<20} : {cnt} rows")

if __name__ == "__main__":
    main()
