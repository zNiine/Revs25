import csv
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlunparse, urljoin

import requests
from bs4 import BeautifulSoup

INPUT_TEAMS_CSV = "pointstreak_alpb_teams.csv"
OUTPUT_PLAYERS_CSV = "./pointstreak_alpb_player_profiles.csv"
PHOTOS_DIR = Path("player_photos")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PointstreakScraper/1.0)"
}

# Make sure photos directory exists
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update(HEADERS)


def build_roster_url(team_url: str) -> str:
    """
    Take a URL like
    https://baseball.pointstreak.com/team_home.html?teamid=3613&seasonid=34182
    and convert to
    https://baseball.pointstreak.com/team_roster.html?teamid=3613&seasonid=34182
    """
    parsed = urlparse(team_url)
    # Replace only the last part of the path if it matches team_home
    path = parsed.path
    if "team_home" in path:
        path = path.replace("team_home", "team_roster")
    elif "team_roster" not in path:
        # Fallback: just force team_roster.html
        path = "/team_roster.html"

    return urlunparse(parsed._replace(path=path))


def get_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"[!] Error fetching {url}: {e}")
        return None


def download_photo(photo_url: str, player_id: str | None) -> str:
    """
    Download photo to PHOTOS_DIR and return local filename (relative).
    If already exists, skip downloading.
    """
    parsed = urlparse(photo_url)
    filename = os.path.basename(parsed.path)

    # If we have a player_id, prefix filename to avoid collisions
    if player_id:
        filename = f"{player_id}_{filename}"

    dest = PHOTOS_DIR / filename

    if dest.exists():
        return str(dest)

    try:
        r = session.get(photo_url, timeout=20)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"    [img] Saved photo {dest}")
    except Exception as e:
        print(f"    [!] Failed to download photo {photo_url}: {e}")
        return ""

    return str(dest)


def parse_profile_page(player_url: str) -> dict:
    """
    Scrape the player profile / bio section:
    - jersey + name from nova-title
    - team & league from nova-sub-text
    - all <li> fields from the list-unstyled UL
    - profile photo (download)
    """
    print(f"  [+] Fetching profile {player_url}")
    soup = get_soup(player_url)
    if soup is None:
        return {}

    data = {
        "profile_jersey": "",
        "profile_name": "",
        "profile_team": "",
        "profile_league": "",
        "profile_position": "",
        "profile_birthday": "",
        "profile_hometown": "",
        "profile_country": "",
        "profile_bats_throws": "",
        "profile_height": "",
        "profile_weight": "",
        "profile_photo_url": "",
        "profile_photo_path": "",
    }

    # Player ID from URL
    parsed = urlparse(player_url)
    qs = parse_qs(parsed.query)
    player_id = qs.get("playerid", [""])[0]

    # Title with "#47 Aaron Fletcher"
    title_span = soup.select_one(".nova-content-header__title .nova-title")
    if title_span:
        title_text = " ".join(title_span.get_text(strip=True).split())
        # Try to split "#47 Name"
        m = re.match(r"#(\d+)\s+(.*)", title_text)
        if m:
            data["profile_jersey"] = m.group(1)
            data["profile_name"] = m.group(2)
        else:
            data["profile_name"] = title_text

    # Team / League
    sub_text_span = soup.select_one(".nova-content-header__title .nova-sub-text")
    if sub_text_span:
        # Team is first <a>, League is second <a>
        links = sub_text_span.find_all("a")
        if len(links) >= 1:
            data["profile_team"] = links[0].get_text(strip=True)
        if len(links) >= 2:
            data["profile_league"] = links[1].get_text(strip=True)

    # Photo
    img = soup.select_one("img.profile-photo")
    if img and img.get("src"):
        photo_url = urljoin(player_url, img["src"])
        data["profile_photo_url"] = photo_url
        local_path = download_photo(photo_url, player_id)
        data["profile_photo_path"] = local_path

    # Info list
    info_map = {}
    for li in soup.select("ul.list-unstyled li"):
        strong = li.find("strong")
        if not strong:
            continue
        label = strong.get_text(strip=True).rstrip(":")
        strong.extract()  # remove label from li so only value remains
        value = li.get_text(strip=True)
        info_map[label] = value

    # Normalize keys
    data["profile_position"] = info_map.get("Position", "")
    data["profile_birthday"] = info_map.get("Birthday", "")
    data["profile_hometown"] = info_map.get("Hometown", "")
    data["profile_country"] = info_map.get("Country", "")
    data["profile_bats_throws"] = info_map.get("Bats/Throws", "")
    data["profile_height"] = info_map.get("Height", "")
    data["profile_weight"] = info_map.get("Weight", "")

    return data


def scrape_roster(team_row: dict, player_cache: dict, writer: csv.DictWriter):
    team_url = team_row["team_url"].strip()
    roster_url = build_roster_url(team_url)

    print(f"[+] Team {team_row.get('team')} ({team_row.get('season')})")
    print(f"    Roster URL: {roster_url}")

    soup = get_soup(roster_url)
    if soup is None:
        return

    # Loop through each <h4> section (Pitchers, Catchers, etc.)
    for h4 in soup.select("h4"):
        category = h4.get_text(strip=True)
        table = h4.find_next("table", class_="nova-stats-table")
        if not table:
            continue

        tbody = table.find("tbody")
        if not tbody:
            continue

        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            jersey = tds[0].get_text(strip=True)
            player_link = tds[1].find("a")
            if not player_link or not player_link.get("href"):
                continue

            player_name = player_link.get_text(strip=True)
            player_url = urljoin(roster_url, player_link["href"])

            pos_short = tds[2].get_text(strip=True) if len(tds) > 2 else ""
            bats_throws_roster = tds[3].get_text(strip=True) if len(tds) > 3 else ""
            height_roster = tds[4].get_text(strip=True) if len(tds) > 4 else ""
            weight_roster = tds[5].get_text(strip=True) if len(tds) > 5 else ""

            # Use full player_url as cache key
            if player_url not in player_cache:
                profile_data = parse_profile_page(player_url)
                player_cache[player_url] = profile_data
                # polite delay
                time.sleep(0.7)
            else:
                profile_data = player_cache[player_url]

            # Build output row
            row_out = {
                # From team CSV
                "season": team_row.get("season", ""),
                "season_id": team_row.get("season_id", ""),
                "division": team_row.get("division", ""),
                "team": team_row.get("team", ""),
                "team_id": team_row.get("team_id", ""),
                "team_url": team_row.get("team_url", ""),

                # From roster page
                "roster_category": category,   # Pitchers / Catchers / etc.
                "roster_jersey": jersey,
                "roster_player_name": player_name,
                "roster_position": pos_short,
                "roster_bats_throws": bats_throws_roster,
                "roster_height": height_roster,
                "roster_weight": weight_roster,
                "player_url": player_url,

                # From profile page
                **profile_data,
            }

            writer.writerow(row_out)


def main():
    # Read input CSV to get fieldnames
    with open(INPUT_TEAMS_CSV, newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        team_rows = list(reader)

    # Define output fieldnames
    fieldnames = [
        # team CSV
        "season",
        "season_id",
        "division",
        "team",
        "team_id",
        "team_url",

        # roster-level info
        "roster_category",
        "roster_jersey",
        "roster_player_name",
        "roster_position",
        "roster_bats_throws",
        "roster_height",
        "roster_weight",
        "player_url",

        # profile-level info
        "profile_jersey",
        "profile_name",
        "profile_team",
        "profile_league",
        "profile_position",
        "profile_birthday",
        "profile_hometown",
        "profile_country",
        "profile_bats_throws",
        "profile_height",
        "profile_weight",
        "profile_photo_url",
        "profile_photo_path",
    ]

    with open(OUTPUT_PLAYERS_CSV, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        player_cache: dict[str, dict] = {}

        for team_row in team_rows:
            scrape_roster(team_row, player_cache, writer)

    print(f"\nDone. Player profiles written to {OUTPUT_PLAYERS_CSV}")
    print(f"Photos saved to {PHOTOS_DIR.resolve()}")


if __name__ == "__main__":
    main()
