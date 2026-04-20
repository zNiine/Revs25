#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pointstreak ALPB Game Logs scraper (Batting & Pitching) — FIXED VERSION

Key fixes vs old script:
- Scrapes each player (player_id) only once, instead of once per (player_id, season_id).
- "Batting Game Log" and "Pitching Game Log" tables on player.html are CAREER logs.
- For each game row, we infer the REAL season from the opponent link's seasonid=...
- Then we look up (player_id, season_id) in a global map to get the correct Season label,
  Team, and team_id for that year.

Input:
- pointstreak_alpb_teams.csv

Output:
- batters.csv
- pitchers.csv
"""

import csv
import os
import sys
import time
from typing import List, Dict, Tuple, Optional
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

INPUT_TEAMS_CSV = "pointstreak_alpb_teams.csv"
OUT_BATTERS = "batters.csv"
OUT_PITCHERS = "pitchers.csv"

BASE = "https://baseball.pointstreak.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

PLAYER_ID_RE = re.compile(r"playerid=(\d+)")
SEASON_ID_RE = re.compile(r"seasonid=(\d+)")
TEAM_ID_RE = re.compile(r"teamid=(\d+)")

MAX_WORKERS = int(os.environ.get("POINTSTREAK_MAX_WORKERS", "8"))

# --------------------------------------------------------------------
# GLOBAL MAPS (populated in main)
# --------------------------------------------------------------------
# For each (player_id, season_id) we know Season label, Team, team_id, Player name
player_seasons: Dict[Tuple[str, str], Dict[str, str]] = {}
# For each player_id, a "primary" meta (we'll just pick one of their seasons)
players_primary_meta: Dict[str, Dict[str, str]] = {}
# season_id -> Season label (from team CSV)
season_id_to_label: Dict[str, str] = {}


# --------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=MAX_WORKERS,
        pool_maxsize=MAX_WORKERS,
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    return s


def fetch_html(session: requests.Session, url: str) -> BeautifulSoup:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# --------------------------------------------------------------------
# CSV + team list helpers
# --------------------------------------------------------------------
def read_team_rows(path: str) -> List[Dict[str, str]]:
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("team_url"):
                out.append(row)
    return out


def build_batting_url(team_url: str) -> str:
    return team_url.replace("team_home.html", "team_stats.html")


def build_pitching_url(batting_url: str) -> str:
    sep = "&" if "?" in batting_url else "?"
    return f"{batting_url}{sep}view=pitching"


def is_total_row(tr: BeautifulSoup) -> bool:
    first_td = tr.find("td")
    if not first_td:
        return False
    return "total" in first_td.get_text(" ", strip=True).lower()


def extract_player_cell(td: BeautifulSoup) -> Tuple[str, str, str]:
    a = td.find("a", href=True)
    if a:
        name = a.get_text(strip=True)
        href = a["href"].replace("&amp;", "&")
        m = PLAYER_ID_RE.search(href)
        pid = m.group(1) if m else ""
        url = href if href.startswith("http") else f"{BASE}/{href.lstrip('/')}"
        return name, pid, url
    return td.get_text(strip=True), "", ""


def parse_season_table_collect_players(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    From a team season stats page, collect player name + id.
    """
    tbl = soup.select_one("table.nova-stats-table")
    if not tbl:
        return []
    rows = []
    for tr in tbl.select("tbody tr"):
        if is_total_row(tr):
            continue
        tds = tr.find_all("td")
        if not tds:
            continue
        name, pid, purl = extract_player_cell(tds[0])
        if pid:
            rows.append({"Player": name, "player_id": pid, "player_profile_url": purl})
    return rows


def parse_table_headers(tbl: BeautifulSoup) -> List[str]:
    headers = []
    thead = tbl.find("thead")
    if thead:
        for th in thead.find_all("th"):
            label = th.get_text(strip=True) or th.get("data-orderby") or ""
            headers.append(label.replace("\xa0", " ").strip())
    else:
        first = tbl.find("tr")
        if first:
            for td in first.find_all(["th", "td"]):
                headers.append(td.get_text(strip=True).replace("\xa0", " ").strip())
    return headers


def table_after_h4(soup: BeautifulSoup, h4_text_exact: str) -> Optional[BeautifulSoup]:
    """
    Find the first TABLE after the H4 whose text exactly matches h4_text_exact.
    """
    target = None
    wanted = h4_text_exact.strip().lower()
    for h4 in soup.find_all("h4"):
        txt = h4.get_text(" ", strip=True).strip().lower()
        if txt == wanted:
            target = h4
            break
    if not target:
        return None
    sib = target.find_next_sibling()
    while sib is not None and getattr(sib, "name", None):
        if sib.name.lower() == "table":
            return sib
        sib = sib.find_next_sibling()
    # fallback
    return target.find_next("table")


# --------------------------------------------------------------------
# Player-season collection
# --------------------------------------------------------------------
def collect_player_seasons(
    session: requests.Session,
    teams: List[Dict[str, str]],
) -> Dict[Tuple[str, str], Dict[str, str]]:
    """
    Load each team's batting/pitching season stats page and collect unique
    (player_id, season_id) entries with Season label, Team, team_id, etc.

    Returns:
        dict[(player_id, season_id)] -> {
            "Season", "season_id", "Team", "team_id", "Player", "player_id"
        }
    """
    player_seasons_local: Dict[Tuple[str, str], Dict[str, str]] = {}

    for i, t in enumerate(teams, 1):
        season_label = t.get("season", "")
        season_id = t.get("season_id", "")
        team_name = t.get("team", "")
        team_id = t.get("team_id", "")
        team_url = t.get("team_url", "")

        bat_url = build_batting_url(team_url)
        pit_url = build_pitching_url(bat_url)

        print(f"[teams {i}/{len(teams)}] {season_label} | {team_name}")

        # Batting stats page
        try:
            soup_bat = fetch_html(session, bat_url)
            for r in parse_season_table_collect_players(soup_bat):
                key = (r["player_id"], season_id)
                if key not in player_seasons_local:
                    player_seasons_local[key] = {
                        "Season": season_label,
                        "season_id": season_id,
                        "Team": team_name,
                        "team_id": team_id,
                        "Player": r["Player"],
                        "player_id": r["player_id"],
                    }
        except Exception as e:
            print(f"  ! season batting list error: {e}", file=sys.stderr)

        # Pitching stats page
        try:
            soup_pit = fetch_html(session, pit_url)
            for r in parse_season_table_collect_players(soup_pit):
                key = (r["player_id"], season_id)
                if key not in player_seasons_local:
                    player_seasons_local[key] = {
                        "Season": season_label,
                        "season_id": season_id,
                        "Team": team_name,
                        "team_id": team_id,
                        "Player": r["Player"],
                        "player_id": r["player_id"],
                    }
        except Exception as e:
            print(f"  ! season pitching list error: {e}", file=sys.stderr)

        time.sleep(0.25)

    return player_seasons_local


# --------------------------------------------------------------------
# Game-log parsing with per-row season inference
# --------------------------------------------------------------------
def parse_batting_log_rows(
    tbl: BeautifulSoup,
    player_id: str,
    default_meta: Dict[str, str],
    profile_url: str,
) -> List[Dict[str, str]]:
    """
    Parse the 'Batting Game Log' table as a CAREER log.

    For each row:
    - Infer game_season_id from the opponent link's seasonid=...
    - Look up (player_id, game_season_id) in player_seasons to get true Season, Team, team_id.
    - Fallback to default_meta & season_id_to_label if needed.
    """
    if not tbl:
        return []

    headers = parse_table_headers(tbl)
    if not headers:
        first_tr = tbl.find("tr")
        n = len(first_tr.find_all(["td", "th"])) if first_tr else 0
        headers = [f"col_{i+1}" for i in range(n)]

    out_rows: List[Dict[str, str]] = []
    tbody = tbl.find("tbody") or tbl

    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue

        vals = [c.get_text(strip=True).replace("\xa0", " ") for c in cells]
        if len(vals) < len(headers):
            vals += [""] * (len(headers) - len(vals))
        elif len(vals) > len(headers):
            vals = vals[:len(headers)]

        row = {h: v for h, v in zip(headers, vals)}

        # --- infer game-specific season from opponent link ----
        game_season_id = default_meta.get("season_id", "")
        game_season_label = default_meta.get("Season", "")
        team_name = default_meta.get("Team", "")
        team_id = default_meta.get("team_id", "")

        if len(cells) >= 2:
            opp_td = cells[1]
            a = opp_td.find("a", href=True)
            if a:
                href = a["href"].replace("&amp;", "&")
                m = SEASON_ID_RE.search(href)
                if m:
                    game_season_id = m.group(1)
                    # Look up (player_id, game_season_id)
                    meta_ps = player_seasons.get((player_id, game_season_id))
                    if meta_ps:
                        game_season_label = meta_ps.get("Season", game_season_label)
                        team_name = meta_ps.get("Team", team_name)
                        team_id = meta_ps.get("team_id", team_id)
                    else:
                        # Fallback: use pretty label if we know it
                        game_season_label = season_id_to_label.get(
                            game_season_id, game_season_label
                        )

        row.update(
            {
                "Season": game_season_label,
                "season_id": game_season_id,
                "Team": team_name,
                "team_id": team_id,
                "Player": default_meta.get("Player", ""),
                "player_id": player_id,
                "gamelog_url": profile_url,
                "log_type": "batting",
            }
        )

        out_rows.append(row)

    return out_rows


def parse_pitching_log_rows(
    tbl: BeautifulSoup,
    player_id: str,
    default_meta: Dict[str, str],
    profile_url: str,
) -> List[Dict[str, str]]:
    """
    Same idea as parse_batting_log_rows, but for 'Pitching Game Log'.
    """
    if not tbl:
        return []

    headers = parse_table_headers(tbl)
    if not headers:
        first_tr = tbl.find("tr")
        n = len(first_tr.find_all(["td", "th"])) if first_tr else 0
        headers = [f"col_{i+1}" for i in range(n)]

    out_rows: List[Dict[str, str]] = []
    tbody = tbl.find("tbody") or tbl

    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue

        vals = [c.get_text(strip=True).replace("\xa0", " ") for c in cells]
        if len(vals) < len(headers):
            vals += [""] * (len(headers) - len(vals))
        elif len(vals) > len(headers):
            vals = vals[:len(headers)]

        row = {h: v for h, v in zip(headers, vals)}

        # --- infer game-specific season from opponent link ----
        game_season_id = default_meta.get("season_id", "")
        game_season_label = default_meta.get("Season", "")
        team_name = default_meta.get("Team", "")
        team_id = default_meta.get("team_id", "")

        if len(cells) >= 2:
            opp_td = cells[1]
            a = opp_td.find("a", href=True)
            if a:
                href = a["href"].replace("&amp;", "&")
                m = SEASON_ID_RE.search(href)
                if m:
                    game_season_id = m.group(1)
                    meta_ps = player_seasons.get((player_id, game_season_id))
                    if meta_ps:
                        game_season_label = meta_ps.get("Season", game_season_label)
                        team_name = meta_ps.get("Team", team_name)
                        team_id = meta_ps.get("team_id", team_id)
                    else:
                        game_season_label = season_id_to_label.get(
                            game_season_id, game_season_label
                        )

        row.update(
            {
                "Season": game_season_label,
                "season_id": game_season_id,
                "Team": team_name,
                "team_id": team_id,
                "Player": default_meta.get("Player", ""),
                "player_id": player_id,
                "gamelog_url": profile_url,
                "log_type": "pitching",
            }
        )

        out_rows.append(row)

    return out_rows


# --------------------------------------------------------------------
# Worker: fetch each player ONCE
# --------------------------------------------------------------------
def worker_fetch_logs(player_id: str) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Worker: fetch a single player's profile (once), return (bat_rows, pit_rows).

    We use players_primary_meta[player_id] only as default meta for name/team/etc.
    Game-season specifics are inferred per-row from opponent links + player_seasons map.
    """
    session = make_session()

    default_meta = players_primary_meta[player_id]
    # Use any season_id that we know for this player to load the profile page.
    # The game-log table on that page is career-wide anyway.
    sid_for_url = default_meta.get("season_id", "")
    profile_url = f"{BASE}/player.html?playerid={player_id}&seasonid={sid_for_url}"

    bat_out: List[Dict[str, str]] = []
    pit_out: List[Dict[str, str]] = []

    try:
        soup = fetch_html(session, profile_url)
    except Exception as e:
        print(f"  ! profile fetch error pid={player_id}: {e}", file=sys.stderr)
        return bat_out, pit_out

    # Batting Game Log
    try:
        bat_tbl = table_after_h4(soup, "Batting Game Log")
        if bat_tbl:
            bat_rows = parse_batting_log_rows(
                bat_tbl, player_id, default_meta, profile_url
            )
            bat_out.extend(bat_rows)
    except Exception as e:
        print(f"  ! batting log parse error pid={player_id}: {e}", file=sys.stderr)

    # Pitching Game Log
    try:
        pit_tbl = table_after_h4(soup, "Pitching Game Log")
        if pit_tbl:
            pit_rows = parse_pitching_log_rows(
                pit_tbl, player_id, default_meta, profile_url
            )
            pit_out.extend(pit_rows)
    except Exception as e:
        print(f"  ! pitching log parse error pid={player_id}: {e}", file=sys.stderr)

    time.sleep(0.05)
    return bat_out, pit_out


# --------------------------------------------------------------------
# CSV writer
# --------------------------------------------------------------------
def write_csv(path: str, rows: List[Dict[str, str]], leading_order: List[str]) -> None:
    if not rows:
        print(f"[!] No rows to write for {path}")
        return

    keys = set()
    for r in rows:
        keys.update(r.keys())
    tail = [k for k in sorted(keys) if k not in leading_order]
    fieldnames = leading_order + tail

    print(f"[+] Writing {len(rows)} rows -> {path}")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


# --------------------------------------------------------------------
# main()
# --------------------------------------------------------------------
def main():
    global player_seasons, players_primary_meta, season_id_to_label

    # 1) Load teams
    teams = read_team_rows(INPUT_TEAMS_CSV)
    if not teams:
        print(f"No team rows in {INPUT_TEAMS_CSV}.", file=sys.stderr)
        sys.exit(1)

    # Build season_id -> label map from team CSV
    season_id_to_label = {
        t["season_id"]: t["season"]
        for t in teams
        if t.get("season_id") and t.get("season")
    }

    base_session = make_session()

    # 2) Collect (player_id, season_id) combos
    print("[+] Collecting player-season combinations from team stats pages...")
    player_seasons = collect_player_seasons(base_session, teams)
    print(f"[+] Discovered {len(player_seasons)} (player_id, season_id) entries.")

    # 3) Build players_primary_meta: one default meta per player_id
    by_player: Dict[str, List[Dict[str, str]]] = {}
    for (pid, sid), meta in player_seasons.items():
        by_player.setdefault(pid, []).append(meta)

    players_primary_meta = {}
    for pid, metas in by_player.items():
        # Just pick the one with the max season_id as "primary" (doesn't matter much)
        metas_sorted = sorted(
            metas, key=lambda m: int(m.get("season_id", "0") or "0"), reverse=True
        )
        players_primary_meta[pid] = metas_sorted[0]

    print(f"[+] Total unique players: {len(players_primary_meta)}")

    # 4) Scrape each player ONCE
    batter_rows: List[Dict[str, str]] = []
    pitcher_rows: List[Dict[str, str]] = []

    pids = list(players_primary_meta.keys())
    print(f"[+] Fetching logs for {len(pids)} players with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(worker_fetch_logs, pid): pid for pid in pids}
        for idx, fut in enumerate(as_completed(futures), 1):
            pid = futures[fut]
            try:
                bat_part, pit_part = fut.result()
                if bat_part:
                    batter_rows.extend(bat_part)
                if pit_part:
                    pitcher_rows.extend(pit_part)
            except Exception as e:
                print(f"  ! worker error for pid={pid}: {e}", file=sys.stderr)

            if idx % 50 == 0 or idx == len(futures):
                print(f"  processed {idx}/{len(futures)} players...")

    # 5) Write CSVs
    if batter_rows:
        write_csv(
            OUT_BATTERS,
            batter_rows,
            leading_order=[
                "Season",
                "season_id",
                "Team",
                "team_id",
                "player_id",
                "Player",
                "log_type",
                "gamelog_url",
            ],
        )
    else:
        print("[!] No Batting Game Log rows found.", file=sys.stderr)

    if pitcher_rows:
        write_csv(
            OUT_PITCHERS,
            pitcher_rows,
            leading_order=[
                "Season",
                "season_id",
                "Team",
                "team_id",
                "player_id",
                "Player",
                "log_type",
                "gamelog_url",
            ],
        )
    else:
        print("[!] No Pitching Game Log rows found.", file=sys.stderr)


if __name__ == "__main__":
    main()
