import pandas as pd
import re

# --- 1. Load data ---
df = pd.read_csv("pitchers.csv")

# --- 2. Columns that define "same stat line" for pitchers ---
stat_cols = [
    "BB", "BF", "DATE", "DEC", "ER", "ERA", "H", "IP",
    "OAVG", "OOBP", "OPPONENT", "OSLG", "R", "RES",
    "SO", "SV", "WHP"
]

# tie to player_id as well
group_cols = ["player_id"] + stat_cols

# --- 3. Season priority logic (same as before) ---
def season_priority(season: str) -> int:
    """
    Higher number = row we prefer to keep.
    3 = ALPB- YEAR
    2 = Playoffs YEAR
    1 = World Series YEAR
    0 = everything else
    """
    if not isinstance(season, str):
        return 0
    s = season.strip()

    if re.match(r"^ALPB-\s*\d{4}$", s):
        return 3
    if s.startswith("Playoffs"):
        return 2
    if s.startswith("World Series"):
        return 1
    return 0

df["season_priority"] = df["Season"].apply(season_priority)

# --- 4. For each duplicate stat line, keep only the best Season ---
df_sorted = df.sort_values("season_priority", ascending=False)
df_clean = df_sorted.drop_duplicates(subset=group_cols, keep="first")

# --- 5. Drop helper and save ---
df_clean = df_clean.drop(columns=["season_priority"])
df_clean.to_csv("pitchers_cleaned.csv", index=False)

print("Done. Original rows:", len(df), "Cleaned rows:", len(df_clean))
