import pandas as pd

# Load and clean
# Corrected file path
df = pd.read_csv("../data.csv", engine="python")
df.columns = df.columns.str.strip()

# Filter for YOR batters
filtered = df[
    (df["BatterTeam"] == "HP")
].copy()

# Check for the existence of 'UTCDateTime' before trying to sort
if "UTCDateTime" in filtered.columns:
    # Parse datetime for ordering
    filtered["UTCDateTime"] = pd.to_datetime(filtered["UTCDateTime"], errors="coerce")
else:
    # If 'UTCDateTime' doesn't exist, create a fallback column for sorting
    # This uses a combination of date and time to create a sortable key
    filtered["UTCDateTime"] = pd.to_datetime(filtered["Date"] + " " + filtered["Time"], errors="coerce")

# Create unique PA key
filtered["PA_Key"] = (
    filtered["Batter"] + "_" +
    filtered["PAofInning"].astype(str) + "_" +
    filtered["Inning"].astype(str) + "_" +
    filtered["Top/Bottom"].astype(str) + "_" +
    filtered["GameUID"].astype(str)
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

# Group by Batter and PitcherThrows to get lefty/righty splits
grouped_data = last_pitches.groupby(["Batter", "PitcherThrows"])

for (batter, pitcher_throws), batter_df in grouped_data:
    pas = len(batter_df)

    # Walks and HBP
    bb = (batter_df["KorBB"] == "Walk").sum()
    hbp = (batter_df["PitchCall"] == "HitByPitch").sum()

    # Hits from PlayResult
    hits_df = batter_df[batter_df["PlayResult"].isin(slug_values.keys())]
    hits = len(hits_df)

    # At-bats: exclude BB, HBP, Sacrifice, etc.
    ab_df = batter_df[
        ~(batter_df["KorBB"].isin(["Walk", "IntentWalk", "Strikeout"])) &
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

    # New stats
    strikeouts = (batter_df["KorBB"] == "Strikeout").sum()
    k_percent = (strikeouts / pas) * 100 if pas > 0 else 0

    # Balls in play (exclude walks, strikeouts, HBP)
    balls_in_play_df = batter_df[
        ~(batter_df["KorBB"].isin(["Walk", "IntentWalk", "Strikeout"])) &
        ~(batter_df["PitchCall"] == "HitByPitch") &
        (batter_df["PlayResult"].isin(["Single", "Double", "Triple", "HomeRun", "Out", "FieldersChoice"]))
    ]
    balls_in_play = len(balls_in_play_df)
    bip_percent = (balls_in_play / pas) * 100 if pas > 0 else 0

    # Batted ball type percentages for outs
    # Assuming 'PlayResult' of "Out" corresponds to a successful batted ball
    # and 'TaggedHitType' contains the batted ball type
    outs_df = balls_in_play_df[balls_in_play_df["PlayResult"] == "Out"]
    ground_outs = (outs_df["TaggedHitType"] == "GroundBall").sum()
    fly_outs = (outs_df["TaggedHitType"] == "FlyBall").sum()
    
    # Calculate percentages of all outs
    total_outs = len(outs_df)
    ground_out_percent = (ground_outs / total_outs) * 100 if total_outs > 0 else 0
    fly_out_percent = (fly_outs / total_outs) * 100 if total_outs > 0 else 0

    # EV, LA, Distance (only from successful hits)
    avg_ev = hits_df["ExitSpeed"].mean()
    avg_la = hits_df["Angle"].mean()
    avg_dist = hits_df["Distance"].mean()

    results.append({
        "Batter": batter,
        "PitcherHand": pitcher_throws,
        "PA": pas,
        "AB": ab,
        "H": hits,
        "BB": bb,
        "HBP": hbp,
        "AVG": round(avg, 3),
        "OBP": round(obp, 3),
        "SLG": round(slg, 3),
        "K%": round(k_percent, 1),
        "BIP%": round(bip_percent, 1),
        "Ground Out %": round(ground_out_percent, 1),
        "Fly Out %": round(fly_out_percent, 1),
        "Avg Exit Velo": round(avg_ev, 1) if not pd.isna(avg_ev) else None,
        "Avg LA": round(avg_la, 1) if not pd.isna(avg_la) else None,
        "Avg Distance": round(avg_dist, 1) if not pd.isna(avg_dist) else None
    })

# Export
final_df = pd.DataFrame(results).sort_values(by=["Batter", "PitcherHand"])
final_df.to_csv("yor_splits.csv", index=False)

print("[✅ Done] 'PlayResult'-based splits saved to 'yor_splits.csv'")