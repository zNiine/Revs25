import pandas as pd

# Load and clean
df = pd.read_csv("data.csv", engine="python")
df.columns = df.columns.str.strip()

# Filter for McAvene vs YOR batters
filtered = df[
    (df["Pitcher"] == "Hillman, Juan") &
    (df["BatterTeam"] == "YOR")
].copy()

# Parse datetime for ordering
if "UTCDateTime" in filtered.columns:
    filtered["UTCDateTime"] = pd.to_datetime(filtered["UTCDateTime"], errors="coerce")

# Create unique PA key
filtered["PA_Key"] = (
    filtered["Batter"] + "_" +
    filtered["PAofInning"].astype(str) + "_" +
    filtered["Inning"].astype(str) + "_" +
    filtered["Top/Bottom"].astype(str) + "_" +
    filtered["GameID"].astype(str)
)

# Use last pitch of each PA
last_pitches = filtered.sort_values("UTCDateTime").groupby("PA_Key").tail(1)

# Slugging map (based on actual result)
slug_values = {
    "Single": 1,
    "Double": 2,
    "Triple": 3,
    "HomeRun": 4
}

results = []

for batter in last_pitches["Batter"].dropna().unique():
    batter_df = last_pitches[last_pitches["Batter"] == batter]
    pas = len(batter_df)

    # Walks and HBP
    bb = (batter_df["KorBB"] == "Walk").sum()
    hbp = (batter_df["PitchCall"] == "HitByPitch").sum()

    # Hits from PlayResult
    hits_df = batter_df[batter_df["PlayResult"].isin(slug_values.keys())]
    hits = len(hits_df)

    # At-bats: exclude BB, HBP, Sacrifice
    ab_df = batter_df[
        ~(batter_df["KorBB"].isin(["Walk", "IntentWalk"])) &
        ~(batter_df["PitchCall"] == "HitByPitch") &
        ~(batter_df["PlayResult"].isin(["Sacrifice", None, ""]))
    ]
    ab = len(ab_df)

    # OBP
    obp = (hits + bb + hbp) / pas if pas > 0 else 0

    # SLG
    total_bases = hits_df["PlayResult"].map(slug_values).sum()
    slg = total_bases / ab if ab > 0 else 0

    # AVG
    avg = hits / ab if ab > 0 else 0

    # EV, LA, Distance (only from successful hits)
    avg_ev = hits_df["ExitSpeed"].mean()
    avg_la = hits_df["Angle"].mean()
    avg_dist = hits_df["Distance"].mean()

    results.append({
        "Batter": batter,
        "PA": pas,
        "AB": ab,
        "H": hits,
        "BB": bb,
        "HBP": hbp,
        "AVG": round(avg, 3),
        "OBP": round(obp, 3),
        "SLG": round(slg, 3),
        "Avg Exit Velo": round(avg_ev, 1) if not pd.isna(avg_ev) else None,
        "Avg LA": round(avg_la, 1) if not pd.isna(avg_la) else None,
        "Avg Distance": round(avg_dist, 1) if not pd.isna(avg_dist) else None
    })

# Export
final_df = pd.DataFrame(results).sort_values(by="AVG", ascending=False)
final_df.to_csv("yor_vs_mcavene.csv", index=False)

print("[✅ Done] 'PlayResult'-based stats saved to 'yor_vs_mcavene.csv'")
