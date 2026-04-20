#!/usr/bin/env python3
import pandas as pd

# ---- columns to drop (deduped later just in case) ----
cols_to_drop = [
    "Level","League","System","HomeTeamForeignID","AwayTeamForeignID","CatcherId",
    "PitcherSet","DetectedShift","PitcherId","BatterId","ZoneTime","CatcherThrows",
    "GameForeignID","Notes","PitchLastMeasuredX","PitchLastMeasuredY","PitchLastMeasuredZ",
    "TaggedPitchType",
    "Stadium",	"GameID",
    "1B_PositionAtReleaseX","1B_PositionAtReleaseZ",
    "2B_PositionAtReleaseX","2B_PositionAtReleaseZ",
    "3B_PositionAtReleaseX","3B_PositionAtReleaseZ",
    "SS_PositionAtReleaseX","SS_PositionAtReleaseZ",
    "PitchTrajectoryXc0","PitchTrajectoryXc1","PitchTrajectoryXc2",
    "PitchTrajectoryYc0","PitchTrajectoryYc1","PitchTrajectoryYc2",
    "PitchTrajectoryZc0","PitchTrajectoryZc1","PitchTrajectoryZc2",
    "UTCDate","UTCTime","LocalDateTime","UTCDateTime",
    "LF_PositionAtReleaseX","LF_PositionAtReleaseZ",
    "CF_PositionAtReleaseX","CF_PositionAtReleaseZ",
    "RF_PositionAtReleaseX","RF_PositionAtReleaseZ",
    "HitTrajectoryXc0","HitTrajectoryXc1","HitTrajectoryXc2","HitTrajectoryXc3","HitTrajectoryXc4",
    "HitTrajectoryXc5","HitTrajectoryXc6","HitTrajectoryXc7","HitTrajectoryXc8",
    "HitTrajectoryYc0","HitTrajectoryYc1","HitTrajectoryYc2","HitTrajectoryYc3","HitTrajectoryYc4",
    "HitTrajectoryYc5","HitTrajectoryYc6","HitTrajectoryYc7","HitTrajectoryYc8",
    "HitTrajectoryZc0","HitTrajectoryZc1","HitTrajectoryZc2","HitTrajectoryZc3","HitTrajectoryZc4",
    "HitTrajectoryZc5","HitTrajectoryZc6","HitTrajectoryZc7","HitTrajectoryZc8",
    "pfxx","pfxz","x0","y0","z0","vx0","vy0","vz0","ax0","ay0","az0",
    "1B_Name","1B_Id","2B_Name","2B_Id","3B_Name","3B_Id","SS_Name","SS_Id",
    "LF_Name","LF_Id","CF_Name","CF_Id","RF_Name","RF_Id",
    "FHC",
    "PitchReleaseConfidence","PitchLocationConfidence","PitchMovementConfidence",
    "HitLaunchConfidence","HitLandingConfidence",
    "CatcherThrowCatchConfidence","CatcherThrowReleaseConfidence","CatcherThrowLocationConfidence",
    "ThrowTrajectoryXc0","ThrowTrajectoryXc1","ThrowTrajectoryXc2",
    "ThrowTrajectoryYc0","ThrowTrajectoryYc1","ThrowTrajectoryYc2",
    "ThrowTrajectoryZc0","ThrowTrajectoryZc1","ThrowTrajectoryZc2",
    "ZoneSpeed","HitSpinRate","PositionAt110X","PositionAt110Y","PositionAt110Z",
    "LastTrackedDistance"
]

# ---- columns to coerce to whole numbers (nullable Int64 keeps NaN) ----
int_cols = [
    "PAofInning","PitchofPA","Inning","Outs","Balls","Strikes","OutsOnPlay","RunsScored"
]

# ---- columns to round to 4 decimal places ----
round4_cols = [
    "EffectiveVelo","MaxHeight","MeasuredDuration","SpeedDrop","ContactPositionX","ContactPositionY","ContactPositionZ",
"HitSpinAxis","ThrowSpeed","PopTime","ExchangeTime","TimeToBase","CatchPositionX","CatchPositionY","CatchPositionZ","ThrowPositionX","ThrowPositionY","ThrowPositionZ","BasePositionX","BasePositionY","BasePositionZ",

    "RelSpeed","VertRelAngle","HorzRelAngle","SpinRate","SpinAxis","Tilt","RelHeight","RelSide",
    "Extension","VertBreak","InducedVertBreak","HorzBreak","PlateLocHeight","PlateLocSide",
    "VertApprAngle","HorzApprAngle","ExitSpeed","Angle","Direction","Distance","Bearing","HangTime"
]

# ---- load ----
df = pd.read_csv("data.csv")

# ---- drop unwanted columns ----
df = df.drop(columns=list(dict.fromkeys(cols_to_drop)), errors='ignore')  # dedupe + ignore missing

# ---- coerce integer-like columns to whole numbers ----
for c in int_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").round(0).astype("Int64")

# ---- round select float columns to 4 decimal places ----
for c in round4_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").round(3)

# ---- save ----
df.to_csv("data_clean.csv", index=False)
print("Saved cleaned CSV to data_clean.csv")
