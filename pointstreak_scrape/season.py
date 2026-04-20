#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pointstreak ALPB team scraper
- Scrapes ALL seasons from the dropdown (regular, playoffs, preseason, all-star, etc.)
- Visits each season's team list and extracts Division, Team, teamid, seasonid
- Saves CSV: pointstreak_alpb_teams.csv
"""

import csv
import re
import time
from typing import List, Dict, Tuple
import sys

import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

BASE = "https://baseball.pointstreak.com"
LEAGUE_ID = "174"
# Any valid season page will contain the full dropdown; use a current page as a seed.
SEED_SEASON_ID = "34102"  # ALPB- 2025 (adjust if needed)

OUT_CSV = "pointstreak_alpb_teams.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

SEASON_ID_RE = re.compile(r"seasonid=(\d+)")
TEAM_ID_RE = re.compile(r"teamid=(\d+)")
# Team anchors look like: team_home.html?teamid=3614&seasonid=34130


def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(HEADERS)
    return s


def fetch_html(session: requests.Session, url: str) -> BeautifulSoup:
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def should_include_season(label: str) -> bool:
    """
    Return True for all options that have a valid seasonid.
    No filtering — includes Playoffs, Preseason, All-Star, etc.
    """
    return True


def parse_seasons_from_dropdown(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    """
    Returns list of (season_text, season_id) for every available season.
    """
    select = soup.find("select", id="redirectLeagueSeason")
    if not select:
        raise RuntimeError("Could not find season dropdown (select#redirectLeagueSeason).")

    out = []
    for opt in select.find_all("option"):
        label = opt.get_text(strip=True)
        value = (opt.get("value") or "").replace("&amp;", "&")
        m = SEASON_ID_RE.search(value)
        season_id = m.group(1) if m else None
        if not season_id:
            # Some options (e.g., "- All Seasons -") lack a seasonid
            continue

        if should_include_season(label):
            out.append((label, season_id))
    return out


def parse_teamlist_for_season(soup: BeautifulSoup, season_id: str, season_label: str) -> List[Dict]:
    """
    Extract rows of {season_label, season_id, division, team, teamid, team_url}
    """
    rows = []
    # Each division block looks like: <ul class="ps_teamlist list-unstyled"> with
    # first <li class="nova-list-header">Division Name</li>
    for ul in soup.select("ul.ps_teamlist"):
        header_li = ul.find("li", class_="nova-list-header")
        division = header_li.get_text(strip=True) if header_li else ""

        for li in ul.find_all("li"):
            # skip the header li itself
            if "nova-list-header" in (li.get("class") or []):
                continue
            a = li.find("a", href=True)
            if not a:
                continue
            team_name = a.get_text(strip=True)
            href = a["href"].replace("&amp;", "&")
            m_team = TEAM_ID_RE.search(href)
            team_id = m_team.group(1) if m_team else ""

            # Prefer seasonid found in the link (if present)
            m_season = SEASON_ID_RE.search(href)
            href_season = m_season.group(1) if m_season else season_id

            # Normalize team URL absolute
            team_url = href if href.startswith("http") else f"{BASE}/{href.lstrip('/')}"
            rows.append({
                "season": season_label,
                "season_id": href_season,
                "division": division,
                "team": team_name,
                "team_id": team_id,
                "team_url": team_url
            })
    return rows


def main():
    session = make_session()
    # Use seed page that contains the dropdown
    seed_url = f"{BASE}/teamlist.html?leagueid={LEAGUE_ID}&seasonid={SEED_SEASON_ID}"
    print(f"[seed] {seed_url}")

    try:
        seed_soup = fetch_html(session, seed_url)
    except Exception as e:
        print(f"Failed to load seed page: {e}", file=sys.stderr)
        sys.exit(1)

    seasons = parse_seasons_from_dropdown(seed_soup)
    if not seasons:
        print("No seasons found in the dropdown. Exiting.", file=sys.stderr)
        sys.exit(2)

    print(f"Found {len(seasons)} seasons to scrape (no filtering).")
    all_rows: List[Dict] = []

    for i, (season_label, season_id) in enumerate(seasons, 1):
        url = f"{BASE}/teamlist.html?leagueid={LEAGUE_ID}&seasonid={season_id}"
        print(f"[{i}/{len(seasons)}] {season_label} (seasonid={season_id}) -> {url}")
        try:
            soup = fetch_html(session, url)
        except Exception as e:
            print(f"  ! Error loading season {season_id}: {e}", file=sys.stderr)
            continue

        rows = parse_teamlist_for_season(soup, season_id, season_label)
        print(f"  + {len(rows)} teams")
        all_rows.extend(rows)

        # Be polite
        time.sleep(0.5)

    if not all_rows:
        print("No team rows extracted.", file=sys.stderr)
        sys.exit(3)

    # Deduplicate rows (some pages might repeat across divisions in rare layouts)
    uniq = {}
    for r in all_rows:
        key = (r["season_id"], r["team_id"] or r["team"], r["division"])
        if key not in uniq:
            uniq[key] = r
    final_rows = list(uniq.values())

    # Sort for stable CSV (by season_id desc, then division, then team)
    def season_sort_key(sid: str) -> int:
        try:
            return int(sid)
        except Exception:
            return -1

    final_rows.sort(key=lambda r: (-season_sort_key(r["season_id"]), r["division"], r["team"]))

    # Write CSV
    fieldnames = ["season", "season_id", "division", "team", "team_id", "team_url"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(final_rows)

    print(f"Saved {len(final_rows)} rows to {OUT_CSV}")


if __name__ == "__main__":
    main()
