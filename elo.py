# fastest_pitches.py
import pandas as pd

# Path to your CSV
csv_path = "data.csv"

# Columns we’ll use
usecols = [
    "Pitcher", "RelSpeed", "Date", "PitchCall", "SpinRate", "Batter"
]

# Read CSV
df = pd.read_csv(csv_path, dtype=str)

# Convert numeric columns
for col in ["RelSpeed", "SpinRate"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# Keep only columns that exist in file
existing_cols = [c for c in usecols if c in df.columns]
df = df[existing_cols].copy()

# Drop rows missing pitcher or RelSpeed
df = df.dropna(subset=["Pitcher", "RelSpeed"])

# Get each pitcher's single fastest pitch
fastest_per_pitcher = df.loc[df.groupby("Pitcher")["RelSpeed"].idxmax()]

# Sort by speed and take top 20
top20 = fastest_per_pitcher.sort_values("RelSpeed", ascending=False).head(20)

# Reorder output columns
out_cols = ["Pitcher", "RelSpeed", "Date", "PitchCall", "SpinRate", "Batter"]
out_cols = [c for c in out_cols if c in top20.columns]
top20 = top20[out_cols]

# Print to console
pd.set_option("display.max_rows", None)
print("\nTop 20 fastest pitches (one per pitcher):\n")
print(top20.to_string(index=False))

# Save to CSV
out_path = "top20_fastest_by_pitcher.csv"
top20.to_csv(out_path, index=False)
print(f"\nSaved results to: {out_path}")
