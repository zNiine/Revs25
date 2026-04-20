#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Least GDP rate leaders (min AB filter) for Pointstreak ALPB batting data.

- Reads: pointstreak_alpb_batters.csv
- Computes DP Rate = GDP / AB
- Filters AB >= MIN_AB
- Sorts ascending (least DP rate is better)
- Writes: dp_rate_leaders_min200.csv
- Prints top 20
"""

import csv

IN_PATH = "pointstreak_alpb_batters.csv"
OUT_PATH = "dp_rate_leaders_min200.csv"
MIN_AB = 200  # <- minimum AB cutoff

HEADER_ALIASES = {
    "Season": {"season"},
    "Team": {"team"},
    "season_id": {"season_id"},
    "team_id": {"team_id"},
    "Player": {"player"},
    "player_id": {"player_id"},
    "AB": {"ab", "at bats", "at-bats"},
    "GDP": {"gdp", "gidp", "double plays", "dp"},
    "stats_url": {"stats_url"},
}

def canon(h: str) -> str:
    low = h.strip().lower()
    for c, alts in HEADER_ALIASES.items():
        if low == c.lower() or low in alts:
            return c
    return h

def to_int(x) -> int:
    if x is None:
        return 0
    s = str(x).strip().replace(",", "")
    if s in ("", "-", "—"):
        return 0
    try:
        return int(float(s))
    except:
        digits = "".join(ch for ch in s if ch.isdigit())
        return int(digits) if digits else 0

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
    with open(IN_PATH, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        fmap = {h: canon(h) for h in rdr.fieldnames}
        data = [{fmap[k]: v for k, v in row.items()} for row in rdr]

    if not data or ("AB" not in data[0] or "GDP" not in data[0]):
        raise SystemExit("Input missing AB or GDP columns after normalization.")

    out_rows = []
    for r in data:
        ab = to_int(r.get("AB"))
        dp = to_int(r.get("GDP"))
        if ab < MIN_AB:
            continue
        rate = dp / ab if ab > 0 else 0.0

        out_rows.append({
            "Season": r.get("Season", ""),
            "season_id": r.get("season_id", ""),
            "Team": r.get("Team", ""),
            "team_id": r.get("team_id", ""),
            "Player": r.get("Player", ""),
            "player_id": r.get("player_id", ""),
            "AB": ab,
            "GDP": dp,
            "DP_Rate": round(rate, 4),
            "stats_url": r.get("stats_url", ""),
        })

    # Sort: lowest DP rate, then most AB (to reward volume)
    out_rows.sort(key=lambda x: (to_float(x["DP_Rate"]), -to_int(x["AB"])))

    # Write full results
    fieldnames = ["Season","season_id","Team","team_id","Player","player_id","AB","GDP","DP_Rate","stats_url"]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows -> {OUT_PATH}")
    # Show top 20 preview
    print("\nTop 20 least GDP rate hitters (min 200 AB):\n")
    for r in out_rows[:20]:
        print(f'{r["Season"]} | {r["Team"]} | {r["Player"]}: {r["GDP"]} GDP in {r["AB"]} AB '
              f'({r["DP_Rate"]:.3f})')

if __name__ == "__main__":
    main()
