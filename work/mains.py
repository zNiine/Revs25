
import time
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import traceback
# Shared utility functions
# --------------------------------------------------

def extract_batter_and_remaining(segment):
    segment = segment.lstrip("#").strip()
    tokens = segment.split()
    if not tokens:
        return "", ""
    tokens = tokens[1:]
    batter_tokens = []
    start_index = len(tokens)
    pitch_keywords = ("ball", "called", "swinging", "foul", "advances", "scores", "pickoff")
    for i, token in enumerate(tokens):
        if i >= 1 and (any(token.lower().startswith(k) for k in pitch_keywords) or re.search(r"\d", token)):
            start_index = i
            break
        batter_tokens.append(token)
    batter = " ".join(batter_tokens)
    remaining = " ".join(tokens[start_index:]) if start_index < len(tokens) else ""
    return batter, remaining


def update_count(count, token):
    balls, strikes = count
    t = token.lower().strip()
    if t == "ball":
        return balls + 1, strikes
    if t in ("called strike", "swinging strike"):
        return balls, strikes + 1
    if t == "foul":
        return balls, min(strikes + 1, 2)
    return balls, strikes


def process_advancement_token(token, state):
    tl = token.lower()
    result = None
    m1 = re.search(r"^(?:\d+\s+)?([A-Za-z\.\- ]+)\s+advances to 1st", token, re.I)
    if m1:
        name = m1.group(1).strip()
        state['baserunners']['1B'] = name
        if "fielder's choice" in tl:
            result = "fielders choice"
        elif "walk" in tl:
            result = "walk"
        elif "hit by pitch" in tl:
            result = "hbp"
        else:
            result = "single"
    m2 = re.search(r"^(?:\d+\s+)?([A-Za-z\.\- ]+)\s+advances to 2nd", token, re.I)
    if m2:
        name = m2.group(1).strip()
        if state['baserunners'].get('1B') == name:
            state['baserunners']['1B'] = None
        state['baserunners']['2B'] = name
        result = "double"
    m3 = re.search(r"^(?:\d+\s+)?([A-Za-z\.\- ]+)\s+advances to 3rd", token, re.I)
    if m3:
        name = m3.group(1).strip()
        for b in ('1B', '2B'):
            if state['baserunners'].get(b) == name:
                state['baserunners'][b] = None
        state['baserunners']['3B'] = name
        result = "triple"
    m4 = re.search(r"^(?:\d+\s+)?([A-Za-z\.\- ]+)\s+scores", token, re.I)
    if m4:
        name = m4.group(1).strip()
        for b in ('1B', '2B', '3B'):
            if state['baserunners'].get(b) == name:
                state['baserunners'][b] = None
        if "home run" in tl:
            result = "home run"
        else:
            result = "scores"
    return result


def update_baserunners(token, state):
    if "advances to" in token.lower() or re.search(r"\bscores", token, re.I):
        process_advancement_token(token, state)
    return state['baserunners']


def process_plate_appearance(tokens, state):
    data = []
    count = (0, 0)
    for token in tokens:
        if "pickoff attempt" in token.lower():
            continue
        row = {
            'inning': state['inning'],
            'half': state['half'],
            'batter': state.get('current_batter'),
            'balls': count[0],
            'strikes': count[1],
            'pitch': None,
            'result': None,
            'outs': state['outs'],
            '1B': bool(state['baserunners']['1B']),
            '2B': bool(state['baserunners']['2B']),
            '3B': bool(state['baserunners']['3B']),
            'score': f"{state['away_score']}-{state['home_score']}"
        }
        if re.search(r"\bscores", token, re.I):
            r = process_advancement_token(token, state)
            row['result'] = r
            if state['half'] == 'Top':
                state['away_score'] += 1
            else:
                state['home_score'] += 1
        elif "putout" in token.lower():
            row['result'] = 'out'
            state['outs'] += 1
        elif "advances to" in token.lower():
            row['result'] = process_advancement_token(token, state)
        else:
            row['pitch'] = token
            count = update_count(count, token)
        update_baserunners(token, state)
        data.append(row)
    return data


def get_pitcher_for_row(half, inning, subs):
    pitcher = None
    for inn, new, old in sorted(subs, key=lambda x: x[0]):
        if inning >= inn:
            pitcher = new
    return pitcher

# --------------------------------------------------
# Boxscore scraper (/boxscore.html)
# --------------------------------------------------

def process_game(url):
    opts = Options()
    opts.add_argument("--headless")
    driver = webdriver.Firefox(options=opts)
    driver.get(url)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Top of')]"))
    )
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    tables = soup.find_all("table", class_="pbpinning")
    if not tables:
        tables = [t for t in soup.find_all("table") if "Top of" in t.get_text()]

    state = {
        'inning': 0, 'half': None, 'outs': 0,
        'baserunners': {'1B':None,'2B':None,'3B':None},
        'away_score': 0, 'home_score': 0,
        'sub_top': [], 'sub_bot': [],
        'current_batter': None
    }
    all_rows = []
    for table in tables:
        for tr in table.find_all('tr'):
            text = tr.get_text(strip=True)
            m = re.match(r"(Top|Bottom) of (\d+)", text)
            if m:
                state['half'], state['inning'] = m.group(1), int(m.group(2))
                state['outs'] = 0
                state['baserunners'] = {'1B':None,'2B':None,'3B':None}
                continue
            if text.startswith('#'):
                segments = [seg.strip() for seg in text.split(',')]
                batter, first_tok = extract_batter_and_remaining(segments[0])
                state['current_batter'] = batter
                tokens = [first_tok] + segments[1:]
                all_rows.extend(process_plate_appearance(tokens, state))
    return pd.DataFrame(all_rows)

# --------------------------------------------------
# Live page scraper (/gamelive/)
# --------------------------------------------------

def process_live_game(url):
    opts = Options()
    opts.add_argument("--headless")
    driver = webdriver.Firefox(options=opts)
    driver.get(url)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#play-by-play"))
    )
    time.sleep(10)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    pbp_div = soup.find('div', id='play-by-play')
    table = pbp_div.find('table') if pbp_div else None
    rows = table.find_all('tr') if table else []

    state = {'inning':0,'half':None,'outs':0,
             'baserunners':{'1B':None,'2B':None,'3B':None},
             'away_score':0,'home_score':0,'current_batter':None}
    subs_top, subs_bot = [], []
    data = []
    for tr in rows:
        cls = tr.get('class', [])
        if 'play-headings' in cls and any(c.startswith('inning_') for c in cls):
            text = tr.get_text(strip=True)
            m = re.match(r"(Top|Bottom) of the (\d+)", text)
            if m:
                state['half'], state['inning'] = m.group(1), int(m.group(2))
                state['outs'] = 0
                state['baserunners'] = {'1B':None,'2B':None,'3B':None}
            continue
        if any(c.startswith(f"inning_{state['inning']}") and 'pbp-bottom-border' in c for c in cls):
            cells = tr.find_all('td')
            batter = cells[1].find('strong').get_text(strip=True)
            state['current_batter'] = batter
            raw = cells[1].get_text(separator="\n").split("\n",1)[1]
            tokens = [t.strip() for t in raw.split(',') if t.strip()]
            data.extend(process_plate_appearance(tokens, state))
    return pd.DataFrame(data)

# --------------------------------------------------
# Main entry
# --------------------------------------------------
def main():
    # Example boxscore
    df_box = process_game("https://baseball.pointstreak.com/boxscore.html?gameid=627448")
    df_box.to_csv('boxscore.csv', index=False)

    # Example live
    df_live = process_live_game("https://baseball.pointstreak.com/gamelive/?gameid=627448&v=1745910000")
    df_live.to_csv('live.csv', index=False)

if __name__ == '__main__':
    main()

