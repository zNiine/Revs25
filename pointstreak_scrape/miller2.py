#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Find ALPB hitters who met or got close to:
  Runs >= 100, SB >= 50, HR >= 15
Close windows: within 20 runs, 10 SB, 3 HR (i.e., R>=80, SB>=40, HR>=12)

Input:  pointstreak_alpb_batters.csv
Output: alpb_speed_power_candidates.csv
"""

import csv

IN_PATH = "pointstreak_alpb_batters.csv"
OUT_PATH = "alpb_speed_power_candidates.csv"

TARGETS = {"R": 100, "SB": 50, "HR": 15}
CLOSE_WITHIN = {"R": 20, "SB": 10, "HR": 3}

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
    low = h.strip().lower()
    for canon, alts in HEADER_ALIASES.items():
        if low == canon.lower() or low in alts:
            return canon
    return h

def to_number(x):
    if x is None:
        return 0
    s = str(x).strip().replace(",", "")
    if s == "" or s == "-":
        return 0
    try:
        return float(s) if "." in s else int(s)
    except:
        return 0

def qualifies(row):
    R, HR, SB = map(to_number, [row.get("R"), row.get("HR"), row.get("SB")])

    if R >= TARGETS["R"] and HR >= TARGETS["HR"] and SB >= TARGETS["SB"]:
        return "met"

    if (R >= TARGETS["R"] - CLOSE_WITHIN["R"] and
        HR >= TARGETS["HR"] - CLOSE_WITHIN["HR"] and
        SB >= TARGETS["SB"] - CLOSE_WITHIN["SB"]):
        return "close"
    return None

def main():
    with open(IN_PATH, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        field_map = {h: canon_name(h) for h in rdr.fieldnames}
        rows = []
        for raw in rdr:
            r = {field_map[k]: v for k, v in raw.items()}
            status = qualifies(r)
            if status:
                r["Status"] = status
                r["R_from_100"] = to_number(r.get("R")) - TARGETS["R"]
                r["HR_from_15"] = to_number(r.get("HR")) - TARGETS["HR"]
                r["SB_from_50"] = to_number(r.get("SB")) - TARGETS["SB"]
                rows.append(r)

    rows.sort(key=lambda r: (0 if r["Status"] == "met" else 1,
                             -int(r.get("season_id", 0) or 0),
                             -(to_number(r.get("R"))+to_number(r.get("HR"))+to_number(r.get("SB")))))

    keep_cols = ["Status","Season","season_id","Team","team_id","Player","player_id",
                 "R","HR","SB","R_from_100","HR_from_15","SB_from_50","stats_url"]

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keep_cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keep_cols})

    print(f"Wrote {len(rows)} rows → {OUT_PATH}")
    for r in rows[:25]:
        print(f'{r["Status"].upper():4} | {r["Season"]} | {r["Team"]} | {r["Player"]} '
              f'R={r["R"]} HR={r["HR"]} SB={r["SB"]}')

if __name__ == "__main__":
    main()
