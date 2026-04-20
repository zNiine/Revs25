import requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

# 1) Fetch the page
url = "https://baseball.pointstreak.com/schedule.html?leagueid=174&seasonid=34102"
resp = requests.get(url)
resp.raise_for_status()

# 2) Parse it
soup = BeautifulSoup(resp.text, "html.parser")
table = soup.find(
    "table",
    {"class": "table table-hover table-striped nova-stats-table"}
)

# 3) Extract headers
headers = [th.get_text(strip=True) for th in table.thead.find_all("th")]

# 4) Extract all rows
rows = []
for row in table.tbody.find_all("tr"):
    cells = [td.get_text(strip=True) for td in row.find_all("td")]
    rows.append(cells)

# 5) Create DataFrame
df = pd.DataFrame(rows, columns=headers)

# --- BEGIN first‐half logic ---

FIRST_HALF = 63
SIMS       = 5000

NORTH = {"Long Island", "York", "Lancaster", "Staten Island", "Hagerstown"}
SOUTH = {"High Point", "Southern Maryland", "Charleston", "Lexington", "Gastonia"}

# ensure we have a numeric index '#' if not present
if "#" not in df.columns:
    df.insert(0, "#", np.arange(1, len(df)+1))
else:
    df["#"] = pd.to_numeric(df["#"], errors="coerce")

# normalize Result and split out-away/home columns
df["Result"] = df["Result"].replace("", np.nan)
df = df.sort_values("#").reset_index(drop=True)

# --- assign per-team game numbers ---
away_no = dict.fromkeys(set(df["Away"]), 0)
home_no = dict.fromkeys(set(df["Home"]), 0)

away_seq = []
home_seq = []

for _, r in df.iterrows():
    a, h = r["Away"], r["Home"]
    away_no[a] += 1
    home_no[h] += 1
    away_seq.append(away_no[a])
    home_seq.append(home_no[h])

df["AwayGameNo"] = away_seq
df["HomeGameNo"] = home_seq

# 6) Identify played vs. remaining first‐half games
played_mask    = df["Result"].notna() & (df["AwayGameNo"]<=FIRST_HALF) & (df["HomeGameNo"]<=FIRST_HALF)
remaining_mask = df["Result"].isna()    & (df["AwayGameNo"]<=FIRST_HALF) & (df["HomeGameNo"]<=FIRST_HALF)

played    = df[played_mask].copy()
remaining = df[remaining_mask].copy()

print(f"Played games counted in records:    {len(played)}")
print(f"Remaining first-half games to sim:   {len(remaining)}")

# 7) Build current records from played
scores = played["Result"].str.split("-", expand=True)
played["AwayScore"] = pd.to_numeric(scores[0], errors="coerce")
played["HomeScore"] = pd.to_numeric(scores[1], errors="coerce")

teams = set(played["Away"]) | set(played["Home"])
records = {t:{"W":0,"L":0} for t in teams}

for _, r in played.iterrows():
    if r["AwayScore"] > r["HomeScore"]:
        records[r["Away"]]["W"] += 1
        records[r["Home"]]["L"] += 1
    elif r["HomeScore"] > r["AwayScore"]:
        records[r["Home"]]["W"] += 1
        records[r["Away"]]["L"] += 1

# 8) Compute strengths = win pct in those first-half games
strength = {
    t: rec["W"]/(rec["W"]+rec["L"]) if (rec["W"]+rec["L"])>0 else 0.5
    for t,rec in records.items()
}

# pre-list the remaining matchups
matchups = list(zip(remaining["Away"], remaining["Home"]))

def simulate_one():
    nw = {t: records.get(t,{"W":0})["W"] for t in NORTH}
    sw = {t: records.get(t,{"W":0})["W"] for t in SOUTH}
    for a,h in matchups:
        sa, sb = strength.get(a,0.5), strength.get(h,0.5)
        p_away = sa/(sa+sb) if (sa+sb)>0 else 0.5
        if np.random.rand() < p_away:
            if a in nw: nw[a] += 1
            if a in sw: sw[a] += 1
        else:
            if h in nw: nw[h] += 1
            if h in sw: sw[h] += 1
    return max(nw, key=nw.get), max(sw, key=sw.get)

# 9) Monte Carlo
north_wins = dict.fromkeys(NORTH, 0)
south_wins = dict.fromkeys(SOUTH, 0)

for i in range(1, SIMS+1):
    n,s = simulate_one()
    north_wins[n] += 1
    south_wins[s] += 1
    if i%500==0: print(".", end="", flush=True)
print()

north_prob = {t: north_wins[t]/SIMS for t in NORTH}
south_prob = {t: south_wins[t]/SIMS for t in SOUTH}

# 10) Map back to every row
df["away_prob"] = df["Away"].map(lambda t: north_prob.get(t, south_prob.get(t, np.nan)))
df["home_prob"] = df["Home"].map(lambda t: north_prob.get(t, south_prob.get(t, np.nan)))

# 11) Save
df.to_csv("schedule_with_probs.csv", index=False)
print("✅ Done — schedule_with_probs.csv written with away_prob & home_prob")

