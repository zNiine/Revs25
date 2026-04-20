#!/usr/bin/env python3
import math
import re
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

# =========================
# CONFIG — edit if needed
# =========================
INPUT_CSV = "data.csv"
TEAM_FILTER = "YOR"            # BatterTeam to include (e.g., "YOR")
OUTDIR = "out"                 # Output root folder

# Your pitcher list (must match CSV "Pitcher" column format: "Last, First")
PITCHERS = [
    "Gilliam, Ryley",
    "Engler, Scott",
    "Rees, Jackson",
    "Diehl, Phillip",
    "Sullivan, Billy",
    "Johnson, Kyle",
    "McAvene, Michael",
    "White, Brendan",
    "Swarmer, Matt",
    "Bell, Brock",
]

# Table rows per PDF page
ROWS_PER_PAGE = 30


# =========================
# Helpers
# =========================
def safe_name(s: str) -> str:
    """File/dir safe name."""
    s = (s or "").strip().replace(" ", "_")
    return re.sub(r"[^a-zA-Z0-9._-]", "", s) or "unknown"


def compute_last_pitches(df: pd.DataFrame) -> pd.DataFrame:
    """Return last pitch of each PA using UTCDateTime if available."""
    df = df.copy()

    # Ensure string types for key parts
    for col in ["PAofInning", "Inning", "Top/Bottom", "GameID", "Batter"]:
        if col not in df.columns:
            raise ValueError(f"CSV missing required column: {col}")
        df[col] = df[col].astype(str)

    # PA key to identify a single plate appearance
    df["PA_Key"] = (
        df["Batter"] + "_" +
        df["PAofInning"] + "_" +
        df["Inning"] + "_" +
        df["Top/Bottom"] + "_" +
        df["GameID"]
    )

    # Sort by time if available
    if "UTCDateTime" in df.columns:
        df["UTCDateTime"] = pd.to_datetime(df["UTCDateTime"], errors="coerce")
        ordered = df.sort_values("UTCDateTime")
    else:
        # Fall back to stable original order
        ordered = df.reset_index().rename(columns={"index": "_idx"}).sort_values("_idx")

    last_pitches = ordered.groupby("PA_Key", as_index=False).tail(1)
    return last_pitches


def batter_summary(last_pitches: pd.DataFrame) -> pd.DataFrame:
    """Compute PA/AB/H/BB/HBP/AVG/OBP/SLG and EV/LA/Distance per Batter."""
    slug_values = {"Single": 1, "Double": 2, "Triple": 3, "HomeRun": 4}
    rows = []

    # Defensive accessors
    get = last_pitches.get

    for batter, bdf in last_pitches.groupby("Batter"):
        pas = len(bdf)

        korbb = get("KorBB", pd.Series(index=bdf.index, dtype=object))
        pitchcall = get("PitchCall", pd.Series(index=bdf.index, dtype=object))
        playresult = get("PlayResult", pd.Series(index=bdf.index, dtype=object))

        bb = (korbb == "Walk").sum()
        ibb = (korbb == "IntentWalk").sum()
        hbp = (pitchcall == "HitByPitch").sum()

        hits_df = bdf[playresult.isin(slug_values.keys())]
        hits = len(hits_df)

        # At-bats exclude BB, IBB, HBP, Sacrifice, empty PlayResult
        ab_mask = (
            ~korbb.isin(["Walk", "IntentWalk"]) &
            ~(pitchcall == "HitByPitch") &
            ~playresult.isin(["Sacrifice", None, ""])
        )
        ab = int(ab_mask.sum())

        # Rate stats
        obp = (hits + bb + hbp) / pas if pas > 0 else 0.0
        total_bases = hits_df["PlayResult"].map(slug_values).sum() if not hits_df.empty else 0
        slg = (total_bases / ab) if ab > 0 else 0.0
        avg = (hits / ab) if ab > 0 else 0.0

        # Batted ball avgs (hits only)
        avg_ev = hits_df["ExitSpeed"].mean() if "ExitSpeed" in hits_df.columns else np.nan
        avg_la = hits_df["Angle"].mean() if "Angle" in hits_df.columns else np.nan
        avg_dist = hits_df["Distance"].mean() if "Distance" in hits_df.columns else np.nan

        rows.append({
            "Batter": batter,
            "PA": pas,
            "AB": ab,
            "H": hits,
            "BB": int(bb),
            "IBB": int(ibb),
            "HBP": int(hbp),
            "AVG": round(avg, 3),
            "OBP": round(obp, 3),
            "SLG": round(slg, 3),
            "Avg Exit Velo": None if (avg_ev is None or (isinstance(avg_ev, float) and math.isnan(avg_ev))) else round(float(avg_ev), 1),
            "Avg LA": None if (avg_la is None or (isinstance(avg_la, float) and math.isnan(avg_la))) else round(float(avg_la), 1),
            "Avg Distance": None if (avg_dist is None or (isinstance(avg_dist, float) and math.isnan(avg_dist))) else round(float(avg_dist), 1),
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(by=["AVG", "OBP", "PA"], ascending=[False, False, False]).reset_index(drop=True)
    return out


def save_table_pdf(df: pd.DataFrame, title: str, pdf_path: Path, rows_per_page: int = ROWS_PER_PAGE):
    """Render a DataFrame as paginated tables into a landscape Letter PDF."""
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(pdf_path) as pdf:
        num_pages = max(1, int(np.ceil(len(df) / rows_per_page))) if not df.empty else 1

        for page in range(num_pages):
            fig, ax = plt.subplots(figsize=(11, 8.5))  # landscape letter
            ax.axis("off")

            if df.empty:
                ax.set_title(title, pad=20)
                ax.text(0.5, 0.55, "No data", ha="center", va="center", fontsize=16)
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
                continue

            start, end = page * rows_per_page, min((page + 1) * rows_per_page, len(df))
            chunk = df.iloc[start:end]

            ax.set_title(f"{title} (Rows {start + 1}–{end} of {len(df)})", pad=20)

            table = ax.table(cellText=chunk.values.tolist(),
                             colLabels=list(chunk.columns),
                             loc="center")
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 1.2)

            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)


# =========================
# Main workflow
# =========================
def main():
    src = Path(INPUT_CSV)
    if not src.exists():
        raise FileNotFoundError(f"Cannot find input CSV at: {src.resolve()}")

    df = pd.read_csv(src, engine="python")
    df.columns = df.columns.str.strip()

    # Basic column checks
    required = {"BatterTeam", "Pitcher", "Batter", "PAofInning", "Inning", "Top/Bottom", "GameID"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # Filter by team
    team_df = df[df["BatterTeam"] == TEAM_FILTER].copy()
    if team_df.empty:
        print(f"[WARN] No rows with BatterTeam == {TEAM_FILTER}. Nothing to do.")
        return

    out_root = Path(OUTDIR)
    out_root.mkdir(parents=True, exist_ok=True)

    all_rows = []
    combined_pdf_path = out_root / "all_pitchers_combined.pdf"
    combined_pdf = PdfPages(combined_pdf_path)

    # Iterate pitchers (only run for those that exist in data)
    available_pitchers = set(team_df["Pitcher"].dropna().unique().tolist())
    for p in PITCHERS:
        if p not in available_pitchers:
            print(f"[INFO] Skipping {p}: no rows vs team {TEAM_FILTER}.")
            continue

        p_df = team_df[team_df["Pitcher"] == p].copy()
        last = compute_last_pitches(p_df)
        summary = batter_summary(last)

        # Save per-pitcher CSV/PDF
        pitcher_dir = out_root / safe_name(p)
        pitcher_dir.mkdir(parents=True, exist_ok=True)

        csv_path = pitcher_dir / f"results_{safe_name(p)}.csv"
        summary.to_csv(csv_path, index=False)

        pdf_path = pitcher_dir / f"results_{safe_name(p)}.pdf"
        title = f"{p} vs {TEAM_FILTER} – Batter Results (Last pitch of each PA)"
        save_table_pdf(summary, title, pdf_path)

        # Also add a page for this pitcher into combined PDF
        # (render here to the already-open PdfPages)
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        if summary.empty:
            ax.set_title(title, pad=20)
            ax.text(0.5, 0.55, "No data", ha="center", va="center", fontsize=16)
            combined_pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
        else:
            # paginate within combined PDF too
            num_pages = max(1, int(np.ceil(len(summary) / ROWS_PER_PAGE)))
            for page in range(num_pages):
                if page > 0:
                    fig, ax = plt.subplots(figsize=(11, 8.5))
                    ax.axis("off")
                start, end = page * ROWS_PER_PAGE, min((page + 1) * ROWS_PER_PAGE, len(summary))
                chunk = summary.iloc[start:end]
                ax.set_title(f"{title} (Rows {start + 1}–{end} of {len(summary)})", pad=20)
                table = ax.table(cellText=chunk.values.tolist(),
                                 colLabels=list(chunk.columns),
                                 loc="center")
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1, 1.2)
                combined_pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)

        # Accumulate for combined CSV
        if not summary.empty:
            tmp = summary.copy()
            tmp.insert(0, "Pitcher", p)
            all_rows.append(tmp)

        print(f"[✓] {p}: wrote {csv_path.name} and {pdf_path.name}")

    # Finish combined outputs
    combined_pdf.close()
    print(f"[✓] Wrote combined PDF: {combined_pdf_path}")

    if all_rows:
        combined_csv = pd.concat(all_rows, ignore_index=True)
        combined_csv_path = out_root / "all_pitchers_combined.csv"
        combined_csv.to_csv(combined_csv_path, index=False)
        print(f"[✓] Wrote combined CSV: {combined_csv_path}")
    else:
        print("[INFO] No per-pitcher summaries were generated (nothing to combine).")


if __name__ == "__main__":
    main()
