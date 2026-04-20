import pandas as pd
import re

# --- 1. Load data ---
df = pd.read_csv("batters.csv")

# --- 2. Columns that define "same stat line" ---
stat_cols = [
    "2B", "3B", "AB", "AVG", "BB", "CS", "DATE", "H", "HP", "HR",
    "OBP", "OPPONENT", "OPS", "R", "RBI", "RES", "SB", "SF", "SLG", "SO"
]

# We also want to tie it to the player
group_cols = ["player_id"] + stat_cols

# --- 3. Season priority logic ---
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

    # ALPB- 2025, ALPB-2023, etc.
    if re.match(r"^ALPB-\s*\d{4}$", s):
        return 3
    # Playoffs 2021, Playoffs 2019, etc.
    if s.startswith("Playoffs"):
        return 2
    # World Series 2021, etc.
    if s.startswith("World Series"):
        return 1

    return 0

df["season_priority"] = df["Season"].apply(season_priority)

# --- 4. For each duplicate stat line, keep only the best Season ---
# Sort so that the highest-priority season comes first in each group
df_sorted = df.sort_values("season_priority", ascending=False)

# Drop duplicates based on player + stat columns, keeping the first
df_clean = df_sorted.drop_duplicates(subset=group_cols, keep="first")

# Optionally drop the helper column
df_clean = df_clean.drop(columns=["season_priority"])

# --- 5. Save cleaned data ---
df_clean.to_csv("batters_cleaned.csv", index=False)
print("Done. Original rows:", len(df), "Cleaned rows:", len(df_clean))
