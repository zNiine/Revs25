# steal_scraper.py

import re
import time
import csv
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def _make_driver() -> webdriver.Chrome:
    chrome_opts = Options()
    chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_opts)

def parse_game(driver: webdriver.Chrome, gameid: int) -> List[Dict]:
    url = f"https://baseball.pointstreak.com/boxscore.html?gameid={gameid}"
    driver.get(url)
    time.sleep(2)  # wait for JS-rendered play-by-play
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # 1) Build half_inning → team name map
    half_to_team: Dict[str,str] = {}
    pb_list = soup.select("table.table .pbpinning")
    for pb in pb_list:
        header = pb.select_one("table tr")
        cells = header.find_all("td")
        half_text = cells[0].get_text(strip=True)    # e.g. "Bottom of 6th"
        team_name = cells[1].get_text(strip=True)     # e.g. "York Revolution"
        m = re.match(r"(top|bottom) of (\d+)", half_text, re.I)
        if m:
            half = m.group(1).lower()
            half_to_team[half] = team_name

    # 2) Scan for SB and CS
    steals: List[Dict] = []
    BALL_KEYWORDS   = {"ball"}
    STRIKE_KEYWORDS = {"swinging strike", "called strike", "foul"}

    for pb in pb_list:
        header = pb.select_one("table tr")
        half_text = header.select_one("td").get_text(strip=True)
        half, inning = re.match(r"(top|bottom) of (\d+)", half_text, re.I).groups()
        half = half.lower()
        inning = int(inning)

        outs = 0
        for tr in pb.select("table tr")[1:]:
            txt = tr.get_text(" ", strip=True)

            # --- CAUGHT STEALING first (use outs BEFORE increment) ---
            for m_cs in re.finditer(
                r"\d+\s+([\w\s\.\'\-]+?)\s+putout\s*\(caught stealing:\s*CS\s*([\d\-]+)\)",
                txt, re.IGNORECASE
            ):
                player = m_cs.group(1).strip()
                cs_code = m_cs.group(2).strip()    # e.g. "1-5" or "1-4"
                # infer base: codes ending in -5 → 3rd, -4 or -6 → 2nd
                if cs_code.endswith("-5"):
                    base = 3
                else:
                    base = 2

                # count balls/strikes before this event
                before = txt[:m_cs.start()]
                events = [p.strip().lower() for p in before.split(",") if p.strip()]
                balls = sum(1 for e in events if any(k in e for k in BALL_KEYWORDS))
                strikes = 0
                for e in events:
                    if any(k in e for k in STRIKE_KEYWORDS):
                        strikes = min(strikes + 1, 2)

                steals.append({
                    "gameid":       gameid,
                    "inning":       inning,
                    "half":         half,
                    "batting_team": half_to_team[half],
                    "defense_team": half_to_team["bottom" if half=="top" else "top"],
                    "player":       player,
                    "base":         base,
                    "result":       "CS",
                    "balls":        balls,
                    "strikes":      strikes,
                    "outs":         outs
                })

            # --- update outs from "for out number N" if present ---
            m_out = re.search(r"for out number (\d+)", txt, re.IGNORECASE)
            if m_out:
                outs = int(m_out.group(1))

            # --- STOLEN BASES ---
            for m_sb in re.finditer(
                r"\d+\s+([\w\s\.\'\-]+?) advances to (\d)(?:st|nd|rd)\s*\((stolen base)\)",
                txt, re.IGNORECASE
            ):
                player = m_sb.group(1).strip()
                base = int(m_sb.group(2))
                # count balls/strikes before this event
                before = txt[:m_sb.start()]
                events = [p.strip().lower() for p in before.split(",") if p.strip()]
                balls = sum(1 for e in events if any(k in e for k in BALL_KEYWORDS))
                strikes = 0
                for e in events:
                    if any(k in e for k in STRIKE_KEYWORDS):
                        strikes = min(strikes + 1, 2)

                steals.append({
                    "gameid":       gameid,
                    "inning":       inning,
                    "half":         half,
                    "batting_team": half_to_team[half],
                    "defense_team": half_to_team["bottom" if half=="top" else "top"],
                    "player":       player,
                    "base":         base,
                    "result":       "SB",
                    "balls":        balls,
                    "strikes":      strikes,
                    "outs":         outs
                })

    return steals

def scrape_games_to_csv(gameids: List[int], csv_path: str):
    driver = _make_driver()
    fieldnames = [
        "gameid","inning","half","batting_team","defense_team",
        "player","base","result","balls","strikes","outs"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        try:
            for gid in gameids:
                rows = parse_game(driver, gid)
                for row in rows:
                    writer.writerow(row)
        finally:
            driver.quit()

if __name__ == "__main__":
    games = [624485, 628664]  # your gameid list
    scrape_games_to_csv(games, "steals.csv")
    print("Wrote steals.csv")
