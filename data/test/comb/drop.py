# save as filter_teams.py and run:  python filter_teams.py
import pandas as pd
from pathlib import Path

INPUT = "data_clean.csv"
OUTPUT = "data_clean.csv"

# Values that count as "missing"
BAD = {"", "na", "n/a", "nan", "none", "null"}

def find_col(cols, target):
    """Return the actual column name matching target (case-insensitive, trims spaces)."""
    target = target.strip().lower()
    for c in cols:
        if c.strip().lower() == target:
            return c
    raise KeyError(f"Column '{target}' not found in CSV header. Got: {cols}")

def is_bad(series):
    s = series.astype(str).str.strip()
    return s.eq("") | s.str.lower().isin(BAD)

def main():
    if not Path(INPUT).exists():
        raise FileNotFoundError(f"Couldn't find {INPUT} in this folder.")

    # Read as strings to avoid type surprises; keep_default_na=False so blanks stay as ""
    df = pd.read_csv(INPUT, dtype=str, keep_default_na=False)

    # Normalize header whitespace for matching but keep original names
    df.columns = [c.strip() for c in df.columns]

    # Find columns even if the case varies, e.g., 'AwaynameFull'
    home_col = find_col(df.columns, "HomeNameFull")
    away_col = find_col(df.columns, "AwayNameFull")

    # Build keep mask: both HomeNameFull and AwayNameFull must be present (not BAD)
    home_bad = is_bad(df[home_col])
    away_bad = is_bad(df[away_col])
    keep_mask = ~(home_bad | away_bad)

    kept = keep_mask.sum()
    removed = len(df) - kept

    df_clean = df.loc[keep_mask].copy()
    df_clean.to_csv(OUTPUT, index=False)

    print(f"Input rows: {len(df):,}")
    print(f"Removed rows (missing team names): {removed:,}")
    print(f"Wrote: {OUTPUT} with {kept:,} rows")

if __name__ == "__main__":
    main()
