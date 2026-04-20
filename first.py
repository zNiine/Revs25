import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# --------- CONFIG ---------
CSV_PATH = "data.csv"  # <- change to your csv path
PITCHER_NAME = "Bonta-Smith, Fin Del"

# heatmap grid (in feet). Adjust if your data’s range differs.
XMIN, XMAX = -2.0, 2.0          # PlateLocSide (negative = inside to RHH)
YMIN, YMAX =  0.0, 5.0          # PlateLocHeight (0 = ground)
XBINS, YBINS = 80, 80

# strike zone overlay (simple fixed zone; adjust if you prefer player-specific)
ZONE_XMIN, ZONE_XMAX = -0.83, 0.83
ZONE_YMIN, ZONE_YMAX = 1.50, 3.50

# output
OUTDIR = Path("heatmaps_out")
OUTDIR.mkdir(exist_ok=True)

# --------- HELPERS ---------
def plot_heatmap(df, title, outfile):
    """Plot a 2D density heatmap for PlateLocSide (x) vs PlateLocHeight (y)."""
    # Drop NaNs
    xy = df[["PlateLocSide", "PlateLocHeight"]].dropna()
    if xy.empty:
        print(f"[WARN] No data for: {title}")
        return

    # 2D histogram
    H, xedges, yedges = np.histogram2d(
        xy["PlateLocSide"], xy["PlateLocHeight"],
        bins=[XBINS, YBINS],
        range=[[XMIN, XMAX], [YMIN, YMAX]]
    )

    # Transpose for imshow (so y increases upward)
    H = H.T

    fig, ax = plt.subplots(figsize=(6, 7), dpi=150)
    im = ax.imshow(
        H,
        origin='lower',
        extent=[XMIN, XMAX, YMIN, YMAX],
        aspect='auto',
        cmap="magma"  # change colormap if you prefer
    )

    # strike zone
    ax.add_patch(plt.Rectangle(
        (ZONE_XMIN, ZONE_YMIN),
        ZONE_XMAX - ZONE_XMIN,
        ZONE_YMAX - ZONE_YMIN,
        fill=False, linewidth=2, color='white', alpha=0.9
    ))

    # labels & cosmetics
    ax.set_title(title)
    ax.set_xlabel("PlateLocSide (ft)  [− = in to RHH, + = away to RHH]")
    ax.set_ylabel("PlateLocHeight (ft)")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Pitch density")

    # helpful tick lines
    ax.axvline(0.0, color='white', lw=0.5, alpha=0.5)  # middle of plate
    ax.set_xlim(XMIN, XMAX)
    ax.set_ylim(YMIN, YMAX)

    fig.tight_layout()
    fig.savefig(OUTDIR / outfile)
    plt.close(fig)
    print(f"[OK] Saved {outfile} with {len(xy)} pitches.")

# --------- LOAD & FILTER ---------
df = pd.read_csv(CSV_PATH)

# Ensure expected columns exist
required_cols = {
    "Pitcher","PitchofPA","Balls","Strikes",
    "PlateLocSide","PlateLocHeight"
}
missing = required_cols - set(df.columns)
if missing:
    raise ValueError(f"Missing required columns: {missing}")

# Filter pitcher
df_p = df[df["Pitcher"] == PITCHER_NAME].copy()

# --------- QUERIES ---------
# 1) First pitch of each PA
q1 = df_p[df_p["PitchofPA"] == 1]

# 2) Second pitch where Balls == 1 (i.e., started 1–0 after pitch 1)
q2 = df_p[(df_p["PitchofPA"] == 2) & (df_p["Balls"] == 1)]

# 3) Second pitch where Strikes == 1 (i.e., started 0–1 after pitch 1)
q3 = df_p[(df_p["PitchofPA"] == 2) & (df_p["Strikes"] == 1)]

# --------- PLOT ---------
plot_heatmap(q1, f"{PITCHER_NAME} — First Pitch of PA (Pitch #1)", "bonta_smith_first_pitch.png")
plot_heatmap(q2, f"{PITCHER_NAME} — Second Pitch (count 1–0)", "bonta_smith_second_pitch_1-0.png")
plot_heatmap(q3, f"{PITCHER_NAME} — Second Pitch (count 0–1)", "bonta_smith_second_pitch_0-1.png")
