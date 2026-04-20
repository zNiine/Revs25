import csv
import time
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://baseball.pointstreak.com/schedule.html"
LEAGUE_ID = "200"
START_SEASON_ID = "34089"  # any season that exists; just to load the page with the <select>

OUTPUT_CSV = "ftl_schedule_all_seasons.csv"


def get_soup(url, params=None, session=None):
    if session is None:
        session = requests.Session()
    resp = session.get(url, params=params)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_all_season_options(session):
    """
    Load one schedule page and parse the <select id="redirectLeagueSeason">
    to get all season options.
    Returns list of dicts: {"label": text, "query": value}
    where value looks like 'leagueid=174&seasonid=34182'.
    """
    params = {"leagueid": LEAGUE_ID, "seasonid": START_SEASON_ID}
    soup = get_soup(BASE_URL, params=params, session=session)

    select = soup.find("select", id="redirectLeagueSeason")
    if not select:
        raise RuntimeError("Could not find <select id='redirectLeagueSeason'> on page")

    seasons = []
    for opt in select.find_all("option"):
        value = opt.get("value", "").strip()
        label = opt.get_text(strip=True)
        # Skip the "- All Seasons -" or any option without a seasonid
        if "seasonid=" not in value:
            continue
        seasons.append({"label": label, "query": value})
    return seasons


def parse_game_row(tr):
    tds = tr.find_all("td")
    if len(tds) < 8:
        return None

    # Column index reference:
    # 0 = #
    # 1 = Date (two-line)
    # 2 = Away
    # 3 = Home
    # 4 = Result
    # 5 = W Pitcher
    # 6 = L Pitcher
    # 7 = Boxscore

    # --- FIX DATE ---
    date_html = tds[1]
    date_text_lines = list(date_html.stripped_strings)  # ['Oct 12', '1:05 AM']
    date = " ".join(date_text_lines)                    # 'Oct 12 1:05 AM'

    away = tds[2].get_text(" ", strip=True)
    home = tds[3].get_text(" ", strip=True)
    result = tds[4].get_text(" ", strip=True)
    w_pitcher = tds[5].get_text(" ", strip=True)
    l_pitcher = tds[6].get_text(" ", strip=True)

    # --- GameID Parsing ---
    box_td = tds[7]
    gameid = ""
    for a in box_td.find_all("a", href=True):
        if "boxscore.html" in a["href"] and "gameid" in a["href"]:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(a["href"])
            query = parse_qs(parsed.query)
            gameid = query.get("gameid", [""])[0]
            break

    return {
        "Date": date,
        "Away": away,
        "Home": home,
        "Result": result,
        "W.Pitcher": w_pitcher,
        "L.Pitcher": l_pitcher,
        "gameid": gameid,
    }


def scrape_season(season_query, season_label, session):
    """
    season_query is something like 'leagueid=174&seasonid=34182'
    season_label is the visible text ('ALPB- 2018', 'Playoffs 2017', etc.)
    Returns list of row dicts with SeasonLabel included.
    """
    # Convert 'leagueid=174&seasonid=34182' into params dict
    params = {}
    for part in season_query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v

    soup = get_soup(BASE_URL, params=params, session=session)

    # Find the schedule table
    table = soup.find("table", class_="nova-stats-table")
    if not table:
        print(f"[WARN] No schedule table found for {season_label} ({season_query})")
        return []

    body = table.find("tbody") or table
    rows = []
    for tr in body.find_all("tr"):
        # skip header-ish rows that might have <th> or no <td>
        if not tr.find_all("td"):
            continue
        parsed = parse_game_row(tr)
        if not parsed:
            continue
        parsed["SeasonLabel"] = season_label
        rows.append(parsed)

    return rows


def main():
    session = requests.Session()
    # polite headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ALPB-Scraper/1.0; +https://example.com)"
    })

    print("[+] Fetching season options...")
    seasons = get_all_season_options(session)
    print(f"Found {len(seasons)} seasons.")

    all_rows = []

    for idx, season in enumerate(seasons, 1):
        label = season["label"]
        query = season["query"]
        print(f"[{idx}/{len(seasons)}] Scraping season: {label} ({query})")
        season_rows = scrape_season(query, label, session)
        print(f"  -> {len(season_rows)} games found.")
        all_rows.extend(season_rows)
        # Be nice to the server
        time.sleep(1.0)

    if not all_rows:
        print("No games scraped. Exiting.")
        return

    fieldnames = [
        "SeasonLabel",
        "Date",
        "Away",
        "Home",
        "Result",
        "W.Pitcher",
        "L.Pitcher",
        "gameid",  # this is your BoxScore column replaced by just the gameid
    ]

    print(f"[+] Writing {len(all_rows)} rows to {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print("[+] Done.")


if __name__ == "__main__":
    main()
