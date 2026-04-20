import pandas as pd

# --- Settings ---
PATH = "data.csv"          # your file path
PITCH_COL = "AutoPitchType"
PITCHER_COL = "Pitcher"
SPIN_COL = "SpinRate"
IVB_COL = "InducedVertBreak"
TOP_N = 20

# If you want to require a minimum number of pitches per pitcher/pitch type, set >1
MIN_PITCHES = 10

# --- Load ---
df = pd.read_csv(PATH)

# --- Basic validation ---
needed = {PITCHER_COL, PITCH_COL, SPIN_COL, IVB_COL}
missing = needed - set(df.columns)
if missing:
    raise ValueError(f"Missing required column(s): {', '.join(sorted(missing))}")

# Clean numeric columns (in case any are strings)
df[SPIN_COL] = pd.to_numeric(df[SPIN_COL], errors="coerce")
df[IVB_COL] = pd.to_numeric(df[IVB_COL], errors="coerce")

# Helper: top mean(metric) by pitcher for a given pitch type
def top_by_metric_for_pitch(pitch_type: str, metric_col: str, ascending: bool, top_n: int = TOP_N):
    sub = df[df[PITCH_COL] == pitch_type].dropna(subset=[metric_col])
    # Count pitches per pitcher to optionally filter by MIN_PITCHES
    counts = sub.groupby(PITCHER_COL).size().rename("PitchCount")
    agg = (
        sub.groupby(PITCHER_COL)[metric_col]
           .mean()
           .to_frame(name=metric_col)
           .join(counts)
    )
    if MIN_PITCHES > 1:
        agg = agg[agg["PitchCount"] >= MIN_PITCHES]

    out = agg.sort_values(metric_col, ascending=ascending).head(top_n).reset_index()
    return out

# --- Spin rate leaderboards (descending) ---
top_cutters_spin   = top_by_metric_for_pitch("Cutter",    SPIN_COL, ascending=False)
top_fourseam_spin  = top_by_metric_for_pitch("Four-Seam", SPIN_COL, ascending=False)
top_sinkers_spin   = top_by_metric_for_pitch("Sinker",    SPIN_COL, ascending=False)

# --- IVB lists ---
# Sinker: least -> greatest (i.e., ascending)
best_ivb_sinker    = top_by_metric_for_pitch("Sinker",    IVB_COL,  ascending=True)

# Four-seam: greatest -> least (i.e., descending)
best_ivb_fourseam  = top_by_metric_for_pitch("Four-Seam", IVB_COL,  ascending=False)

# --- Print to console ---
pd.set_option("display.max_rows", 200)
print("\n=== Top Cutter Spin Rates (mean) ===")
print(top_cutters_spin)

print("\n=== Top Four-Seam Spin Rates (mean) ===")
print(top_fourseam_spin)

print("\n=== Top Sinker Spin Rates (mean) ===")
print(top_sinkers_spin)

print("\n=== Best IVB for Sinkers (least → greatest) ===")
print(best_ivb_sinker)

print("\n=== Best IVB for Four-Seamers (greatest → least) ===")
print(best_ivb_fourseam)

# --- Save to CSVs ---
top_cutters_spin.to_csv("top_cutter_spin.csv", index=False)
top_fourseam_spin.to_csv("top_fourseam_spin.csv", index=False)
top_sinkers_spin.to_csv("top_sinker_spin.csv", index=False)
best_ivb_sinker.to_csv("best_ivb_sinker_least_to_greatest.csv", index=False)
best_ivb_fourseam.to_csv("best_ivb_fourseam_greatest_to_least.csv", index=False)
