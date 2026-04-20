# steal.py

import re
import time
import csv
from datetime import datetime, timedelta
from typing import List, Dict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def _make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

# --- parse_game (unchanged from before) ---
def parse_game(driver: webdriver.Chrome, gameid: int) -> List[Dict]:
    url = f"https://baseball.pointstreak.com/boxscore.html?gameid={gameid}"
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # build half->team map
    half_to_team: Dict[str,str] = {}
    halves = soup.select("table.table .pbpinning")
    for pb in halves:
        header = pb.select_one("table tr")
        tds = header.find_all("td")
        half_text = tds[0].get_text(strip=True)
        team = tds[1].get_text(strip=True)
        m = re.match(r"(top|bottom) of (\d+)", half_text, re.I)
        if m:
            half_to_team[m.group(1).lower()] = team

    steals = []
    BALL_K = {"ball"}
    STRIKE_K = {"called strike","swinging strike","foul"}

    for pb in halves:
        half_txt = pb.select_one("table tr td").get_text(strip=True)
        half, inning = re.match(r"(top|bottom) of (\d+)", half_txt, re.I).groups()
        half = half.lower()
        inning = int(inning)
        outs = 0

        for tr in pb.select("table tr")[1:]:
            txt = tr.get_text(" ", strip=True)

            # Caught stealing
            for m_cs in re.finditer(
                r"\d+\s+([\w\s\.\'\-]+?)\s+putout\s*\(caught stealing:\s*CS\s*([\d\-]+)\)",
                txt, re.IGNORECASE
            ):
                player = m_cs.group(1).strip()
                code = m_cs.group(2)
                base = 3 if code.endswith("-5") else 2

                before = txt[:m_cs.start()]
                evs = [e.strip().lower() for e in before.split(",") if e.strip()]
                balls = sum(any(k in e for k in BALL_K) for e in evs)
                strikes = 0
                for e in evs:
                    if any(k in e for k in STRIKE_K):
                        strikes = min(strikes+1,2)

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

            # update outs
            m_o = re.search(r"for out number (\d+)", txt, re.IGNORECASE)
            if m_o:
                outs = int(m_o.group(1))

            # Stolen base
            for m_sb in re.finditer(
                r"\d+\s+([\w\s\.\'\-]+?) advances to (\d)(?:st|nd|rd)\s*\(stolen base\)",
                txt, re.IGNORECASE
            ):
                player = m_sb.group(1).strip()
                base = int(m_sb.group(2))

                before = txt[:m_sb.start()]
                evs = [e.strip().lower() for e in before.split(",") if e.strip()]
                balls = sum(any(k in e for k in BALL_K) for e in evs)
                strikes = 0
                for e in evs:
                    if any(k in e for k in STRIKE_K):
                        strikes = min(strikes+1,2)

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

# --- parse_game_info ---
def parse_game_info(driver: webdriver.Chrome, gameid: int) -> Dict:
    url = f"https://baseball.pointstreak.com/boxscore.html?gameid={gameid}"
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    info = {"gameid": gameid, "date": "", "start_time": "", "duration": "", "end_time": ""}
    ul = soup.select_one("ul.list-inline.list-unstyled")
    if ul:
        for li in ul.find_all("li"):
            text = li.get_text(strip=True)
            if text.startswith("Date:"):
                info["date"] = text.replace("Date:","").strip()
            elif text.startswith("Start Time:"):
                info["start_time"] = text.replace("Start Time:","").strip()
            elif text.startswith("Duration:"):
                info["duration"] = text.replace("Duration:","").strip()
            elif text.startswith("End Time:"):
                info["end_time"] = text.replace("End Time:","").strip()
    return info

# --- collect_gameids ---
def collect_gameids(driver: webdriver.Chrome, date_str: str) -> List[int]:
    url = f"https://baseball.pointstreak.com/scoreboard.html?leagueid=174&seasonid=34102&date={date_str}"
    driver.get(url)
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    ids = set()
    for a in soup.select("li.nova-links-list__item--btn a[href*='boxscoretext.html']"):
        m = re.search(r"gameid=(\d+)", a["href"])
        if m:
            ids.add(int(m.group(1)))
    return sorted(ids)

# --- main batch job ---
def scrape_date_range_to_csv(
    start: str, end: str,
    steals_csv: str, info_csv: str
):
    driver = _make_driver()

    steal_fields = [
        "gameid","inning","half","batting_team","defense_team",
        "player","base","result","balls","strikes","outs"
    ]
    info_fields = ["gameid","date","start_time","duration","end_time"]

    with open(steals_csv, "w", newline="", encoding="utf-8") as sf, \
         open(info_csv,   "w", newline="", encoding="utf-8") as jf:

        steal_writer = csv.DictWriter(sf, fieldnames=steal_fields)
        info_writer  = csv.DictWriter(jf, fieldnames=info_fields)

        steal_writer.writeheader()
        info_writer.writeheader()

        d0 = datetime.strptime(start, "%Y-%m-%d")
        d1 = datetime.strptime(end,   "%Y-%m-%d")
        delta = timedelta(days=1)

        all_gameids = set()
        cur = d0
        while cur <= d1:
            mmddyyyy = cur.strftime("%m/%d/%Y")
            print("Fetching games for", mmddyyyy)
            ids = collect_gameids(driver, mmddyyyy)
            all_gameids.update(ids)
            cur += delta

        all_gameids = sorted(all_gameids)
        print("Total unique games:", len(all_gameids))

        for gid in all_gameids:
            print("Scraping game", gid)
            # write game info
            info = parse_game_info(driver, gid)
            info_writer.writerow(info)
            # write steals/CS
            for row in parse_game(driver, gid):
                steal_writer.writerow(row)

    driver.quit()
    print(f"Wrote {steals_csv} and {info_csv}")

if __name__ == "__main__":
    scrape_date_range_to_csv(
        start="2025-08-11",
        end=  "2025-09-18",
        steals_csv="all_steals.csv",
        info_csv=  "game_info.csv"
    )
