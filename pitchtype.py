import pandas as pd
import numpy as np
import seaborn as sns # For heatmaps
import matplotlib.pyplot as plt # For plotting

# --- IMPORTANT: VERIFY YOUR SPIN EFFICIENCY CALCULATION ---
# The current calculation (SpinAxis / SpinRate) is highly suspect for a true "spin efficiency" metric.
# Spin efficiency is typically the ratio of transverse spin to total spin, or a related concept.
# If your SpinAxis is in degrees, this division is likely incorrect.
# If you have a direct 'SpinEfficiency' column from TrackMan, use that instead.
# If you don't have the correct formula or data, consider removing SpinEfficiency from your rules for now.
def calculate_spin_efficiency(row):
    # If a direct 'SpinEfficiency' column exists in your raw data, use it!
    # if 'SpinEfficiencyRaw' in row.index: # Example if you renamed it
    #     return row['SpinEfficiencyRaw']

    # Your current calculation, which is likely incorrect for a true spin efficiency
    # If SpinRate is 0, default to 1 to avoid division by zero.
    if row['SpinRate'] != 0:
        # Assuming SpinAxis is not directly 'useful spin' in RPM, this division is mathematically unusual for SE.
        # This is where you might need to insert the correct formula based on your data source's definition.
        # For typical TrackMan/Rapsodo data, SpinAxis is often a 'tilt' in degrees (0-360) or a vector component.
        # If SpinAxis is a degree measurement, you'd convert it to a vector and calculate transverse spin.
        # For now, keeping your original logic but flagging it.
        return row['SpinAxis'] / row['SpinRate']
    return 1 # Default if SpinRate is zero or data is missing

# Your pitch guessing logic - This is the core you'll be iterating on!
def guess_pitch_type(speed, spin, ivb, hb, spin_efficiency=1):
    # Ensure NaN handling is robust at the start
    if pd.isna(speed):
        return 'N/A'

    # --- Fastball Family - Prioritize higher velocity and distinct movement ---
    # Order matters. More specific rules should come before more general ones.

    # 4-Seam Fastball: Highest velocity, very high IVB, very low HB. High SpinRate, high SpinEfficiency.
    # Refined HB (abs(hb) < 3.5 for very straight) and IVB (>= 16)
    if speed >= 90 and spin >= 2200 and ivb >= 16 and abs(hb) < 3.5 and spin_efficiency > 0.8:
        return '4-Seam Fastball'
    if 87 <= speed < 90 and spin >= 2000 and ivb >= 14 and abs(hb) < 5 and spin_efficiency > 0.75:
        return '4-Seam Fastball'

    # Cutter: Fastball velocity, but with *cut* (negative HB for RH, positive for LH). Lower SE than 4-seam.
    # Placed before 2-seam/sinker as its speed range can overlap.
    if 84 <= speed < 90 and spin >= 2000 and ivb >= 5:
        if -10 <= hb < 0 and spin_efficiency < 0.75: # RH Cutter
            return 'Cutter'
        if 0 < hb <= 10 and spin_efficiency < 0.75: # LH Cutter (if your HB system flips for handedness)
            return 'Cutter'

    # 2-Seam Fastball: High velocity, good arm-side run (significant HB), positive IVB but less than 4-seam.
    # Differentiate from Sinker by higher IVB and less "drop".
    if speed >= 86 and ivb >= 8 and ivb < 14: # IVB range to distinguish from 4-seam and sinker
        if hb > 8: # RH 2-Seam
            return '2-Seam Fastball'
        if hb < -8: # LH 2-Seam
            return '2-Seam Fastball'

    # Sinker: High velocity, significant arm-side run, but pronounced "drop" (lower IVB, closer to 0 or even negative).
    # This rule is crucial for differentiating from 2-seam.
    if speed >= 84 and ivb < 8: # Lower IVB is key
        if hb > 10: # RH Sinker (more arm-side run than 2-seam often)
            return 'Sinker'
        if hb < -10: # LH Sinker
            return 'Sinker'


    # --- Breaking Ball Family ---

    # Curveball: Slower speed, high spin, significant "drop" (low/negative IVB), minimal/negative HB (12-6 or sweeping).
    # Prioritize tighter HB for 12-6 curves, then wider HB for sweeping types.
    if speed < 83 and spin >= 2300 and ivb < 5: # General curveball characteristics
        if abs(hb) < 2.5: # Very strict for 12-6 curve
            return 'Curveball'
        if (hb < -5 or hb > 5) and spin_efficiency < 0.6: # Sweeping curve, lower SE
            return 'Curveball'

    # Slider: Slower speed, high spin, significant glove-side break (negative HB for RH, positive for LH), lower IVB.
    # Crucial to distinguish from Curveball and Cutter.
    if speed < 87 and spin >= 2000 and ivb < 10: # General slider range
        if hb < -5: # RH Slider (distinct glove-side break)
            return 'Slider'
        if hb > 5: # LH Slider
            return 'Slider'


    # --- Offspeed Pitches ---

    # ChangeUp: Slower speed, often some arm-side fade (positive HB for RH), positive IVB but significantly less than FB, lower spin.
    # Broadened ranges slightly to catch more unclassified ChangeUps.
    if speed < 85 and spin < 2000 and ivb >= 3 and ivb < 12: # Added upper IVB bound
        if hb > 6: # RH ChangeUp
            return 'ChangeUp'
        if hb < -6: # LH ChangeUp
            return 'ChangeUp'

    # Splitter: Lowest speed, often very low or negative IVB (heavy drop), some HB, very low spin.
    # Still 0% accuracy, so broaden/re-evaluate its distinct characteristics.
    if speed < 82 and spin < 1700 and ivb < 5: # Broader IVB threshold
        if hb > 8: # RH Splitter
            return 'Splitter'
        if hb < -8: # LH Splitter
            return 'Splitter'


    # --- Fallback to Uncategorized ---
    # Removed the broad speed-based catch-alls. It's better to classify as 'Uncategorized Pitch'
    # if no specific rule is met. This clearly indicates where new rules are needed.
    return 'Uncategorized Pitch'


# --- Main Script ---

# Load your CSV file (ensure it is in the same folder or adjust path)
try:
    df = pd.read_csv('data.csv')
except FileNotFoundError:
    print("Error: 'data.csv' not found. Please ensure the CSV file is in the same directory as the script or provide the full path.")
    exit()

# --- IMPORTANT: Column Renaming & NaN Handling ---
column_mapping = {
    'RelSpeed': 'RelSpeed',
    'SpinRate': 'SpinRate',
    'InducedVertBreak': 'InducedVertBreak',
    'HorzBreak': 'HorzBreak',
    'AutoPitchType': 'AutoPitchType', # This should be the column with TrackMan's labels
    'SpinAxis': 'SpinAxis' # Needed for SpinEfficiency
}
df = df.rename(columns=column_mapping)

# Ensure essential columns exist after renaming
required_columns = ['RelSpeed', 'SpinRate', 'InducedVertBreak', 'HorzBreak', 'AutoPitchType']
for col in required_columns:
    if col not in df.columns:
        print(f"Error: Required column '{col}' not found after renaming. Please check your CSV column names and the 'column_mapping'.")
        exit()

# Handle NaNs in critical numerical columns by filling with median
# This is important for correlation calculations and to prevent errors if NaNs slip into guess_pitch_type
for col in ['RelSpeed', 'SpinRate', 'InducedVertBreak', 'HorzBreak']:
    df[col] = df[col].fillna(df[col].median())

# --- IMPORTANT: Standardize Pitch Names ---
# This is crucial for correct accuracy calculations.
# Map TrackMan's AutoPitchType names to your desired GuessedPitchType names.
# ALWAYS uncomment and run the print statement below to verify all unique names in your raw data.
print("Unique AutoPitchType values in your data:", df['AutoPitchType'].unique())

pitch_name_mapping = {
    'Four-Seam Fastball': '4-Seam Fastball',
    'Four-Seam': '4-Seam Fastball',
    'Two-Seam Fastball': '2-Seam Fastball',
    'Two-Seam': '2-Seam Fastball',
    'Sinker': 'Sinker',
    'Cutter': 'Cutter',
    'Slider': 'Slider',
    'Curveball': 'Curveball',
    'Changeup': 'ChangeUp',
    'Splitter': 'Splitter',
    'Knuckleball': 'Uncategorized Pitch', # Map to uncategorized if no rule for it
    'Other': 'Uncategorized Pitch', # Map 'Other' to uncategorized
    # Add any other AutoPitchType names from your data that show up in the unique list here:
    # Example: 'Fastball': '4-Seam Fastball',
    # Example: 'CH': 'ChangeUp',
}

df['AutoPitchType_Standardized'] = df['AutoPitchType'].map(pitch_name_mapping)
df['AutoPitchType_Standardized'] = df['AutoPitchType_Standardized'].fillna('UNKNOWN_AUTOPITCHTYPE')


# Compute Spin Efficiency
if 'SpinAxis' in df.columns and 'SpinRate' in df.columns:
    # >>>>>>>>>>>>>>>>>> VERIFY THIS CALCULATION <<<<<<<<<<<<<<<<<<<<
    # Your SpinAxis / SpinRate calculation is likely NOT for true Spin Efficiency.
    # If it results in values mostly between 0 and 1, your previous heatmap suggests it's not working as intended.
    # TrackMan / Rapsodo often provide a direct 'SpinEfficiency' column or 'ActiveSpin'.
    # If not, you might need a more complex formula based on 'SpinAxis' (tilt) and 'SpinRate'.
    # For now, I'm using the function but if your data doesn't support it, the values will be off.
    df['SpinEfficiency'] = df.apply(calculate_spin_efficiency, axis=1)
    df['SpinEfficiency'] = df['SpinEfficiency'].fillna(1).clip(0, 1) # Cap between 0 and 1
    # If you're confident SpinEfficiency is given directly in a column, use this:
    # if 'SpinEfficiencyRaw' in df.columns: # Replace 'SpinEfficiencyRaw' with your actual column name
    #    df['SpinEfficiency'] = df['SpinEfficiencyRaw'].fillna(1).clip(0,1)
    # else:
    #    print("Warning: SpinEfficiency column not found, falling back to calculation.")
else:
    print("Warning: 'SpinAxis' or 'SpinRate' not found. Spin Efficiency will be defaulted to 1. This may impact accuracy.")
    df['SpinEfficiency'] = 1

# Apply pitch guessing
df['GuessedPitchType'] = df.apply(lambda row: guess_pitch_type(
    row['RelSpeed'],
    row['SpinRate'],
    row['InducedVertBreak'],
    row['HorzBreak'],
    row['SpinEfficiency']
), axis=1)

# Compare with Standardized TrackMan's AutoPitchType
df['Correct'] = (df['GuessedPitchType'] == df['AutoPitchType_Standardized']) & \
                (df['AutoPitchType_Standardized'] != 'UNKNOWN_AUTOPITCHTYPE')


# --- Analysis Functions (No Change Needed Here) ---

def print_pitch_stats(df_subset, title="Pitch Statistics"):
    """Helper to print mean and std for key pitch metrics."""
    print(f"\n--- {title} ---")
    if df_subset.empty:
        print("No data for this subset.")
        return

    numeric_cols = ['RelSpeed', 'SpinRate', 'InducedVertBreak', 'HorzBreak', 'SpinEfficiency']
    existing_numeric_cols = [col for col in numeric_cols if col in df_subset.columns]
    stats = df_subset[existing_numeric_cols].agg(['mean', 'std'])
    print(stats.to_string())


def analyze_misclassification(df, auto_pitch_type, guessed_pitch_type):
    """
    Analyzes the statistics for a specific misclassification type,
    and compares it to the correctly identified pitches of both types.

    Args:
        df (pd.DataFrame): The DataFrame containing pitch data.
        auto_pitch_type (str): The actual (TrackMan) pitch type (standardized).
        guessed_pitch_type (str): The pitch type your algorithm guessed.
    """
    print(f"\n--- Analysis for AutoPitchType: '{auto_pitch_type}' misclassified as '{guessed_pitch_type}' ---")

    # 1. Misclassified pitches
    misclassified_df = df[
        (df['AutoPitchType_Standardized'] == auto_pitch_type) &
        (df['GuessedPitchType'] == guessed_pitch_type)
    ]
    print_pitch_stats(misclassified_df, f"Metrics for '{auto_pitch_type}' MISCLASSIFIED as '{guessed_pitch_type}' (Count: {len(misclassified_df)})")

    # 2. Correctly identified pitches of the 'AutoPitchType'
    correct_actual_df = df[
        (df['AutoPitchType_Standardized'] == auto_pitch_type) &
        (df['GuessedPitchType'] == auto_pitch_type)
    ]
    print_pitch_stats(correct_actual_df, f"Metrics for '{auto_pitch_type}' CORRECTLY Classified (Count: {len(correct_actual_df)})")

    # 3. Correctly identified pitches of the 'GuessedPitchType'
    correct_guessed_df = df[
        (df['AutoPitchType_Standardized'] == guessed_pitch_type) &
        (df['GuessedPitchType'] == guessed_pitch_type)
    ]
    print_pitch_stats(correct_guessed_df, f"Metrics for '{guessed_pitch_type}' CORRECTLY Classified (Count: {len(correct_guessed_df)})")

    print("\n--------------------------------------------------")


# --- Output and Next Steps ---

# Accuracy summary (using standardized names)
accuracy_by_pitch = df.groupby('AutoPitchType_Standardized')['Correct'].mean().sort_values(ascending=False)
print("\n=== Accuracy by AutoPitchType (Standardized) ===")
print(accuracy_by_pitch)

# Misclassification summary (using standardized names for AutoPitchType)
misclassifications = (
    df[(df['Correct'] == False) & (df['AutoPitchType_Standardized'] != 'UNKNOWN_AUTOPITCHTYPE')]
    .groupby(['AutoPitchType_Standardized', 'GuessedPitchType'])
    .size()
    .sort_values(ascending=False)
)
print("\n=== Top Misclassifications (Actual Pitch -> Guessed Pitch) ===")
print(misclassifications.head(20))

# Optional: Save to CSV for deeper review
df.to_csv('pitch_guess_results.csv', index=False)
print("\nResults saved to pitch_guess_results.csv for deeper analysis.")


# --- Correlation Heatmap Analysis ---
print("\n\n=== Correlation Heatmap Analysis (After current rule adjustments) ===")

# Prepare data for correlation heatmap
correlation_data = df[['RelSpeed', 'SpinRate', 'InducedVertBreak', 'HorzBreak', 'SpinEfficiency']].copy()
pitch_type_dummies = pd.get_dummies(df['AutoPitchType_Standardized'], prefix='Is')
full_correlation_df = pd.concat([correlation_data, pitch_type_dummies], axis=1)
correlation_matrix = full_correlation_df.corr()

# Exclude 'Is_UNKNOWN_AUTOPITCHTYPE' from the heatmap columns
heatmap_cols = [col for col in pitch_type_dummies.columns if col != 'Is_UNKNOWN_AUTOPITCHTYPE']

# If 'Is_Uncategorized Pitch' exists and is always 0.00 accuracy, it's also not useful in the heatmap
if 'Is_Uncategorized Pitch' in heatmap_cols:
    heatmap_cols.remove('Is_Uncategorized Pitch')

feature_pitch_corr = correlation_matrix.loc[
    ['RelSpeed', 'SpinRate', 'InducedVertBreak', 'HorzBreak', 'SpinEfficiency'],
    heatmap_cols
]

plt.figure(figsize=(12, 8))
sns.heatmap(feature_pitch_corr, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5)
plt.title('Correlation Heatmap: Pitch Metrics vs. Standardized Pitch Types')
plt.xlabel('Standardized Pitch Type (Is_PitchName)')
plt.ylabel('Pitch Metric')
plt.show()

print("\nInterpretation of Heatmap:")
print("- **Positive correlation (red/warm colors):** As the metric increases, the likelihood of that pitch type increases.")
print("- **Negative correlation (blue/cool colors):** As the metric increases, the likelihood of that pitch type decreases.")
print("- **Closer to 0 (white/light colors):** Weak or no linear relationship.")
print("- **Look for strong correlations (close to 1 or -1):** These variables are highly influential for that pitch type.")
print("This heatmap should now reflect the correlations based on your (hopefully fixed) SpinEfficiency and other data.")


print("\n\n--- CRITICAL NEXT STEPS ---")
print("1.  **SPIN EFFICIENCY VERIFICATION IS PARAMOUNT.**")
print("    The heatmap indicated a problem with SpinEfficiency. Before anything else:")
print("    - **Confirm the `calculate_spin_efficiency` function is correct for your data.** If you have a direct `SpinEfficiency` column from TrackMan, use that instead (uncomment the relevant line in the code). If your `SpinAxis` is in degrees, a direct division by `SpinRate` is NOT how spin efficiency is calculated. This is likely the cause of its odd correlations.")
print("    - **If you cannot verify the calculation, set `df['SpinEfficiency'] = 1` or remove `spin_efficiency` from `guess_pitch_type` arguments and rules for now.** A bad feature will derail your efforts.")

print("\n2.  **Verify `pitch_name_mapping` exhaustively.**")
print("    - Make sure `UNKNOWN_AUTOPITCHTYPE` count in accuracy summary is zero or minimal. The `print(df['AutoPitchType'].unique())` output is essential for this.")

print("\n3.  **Run the script and re-examine the *new* heatmap.**")
print("    - If SpinEfficiency is fixed, its correlations, especially for 4-Seam Fastballs, should become highly positive.")

print("\n4.  **Use `analyze_misclassification` to target top issues, as before:**")
print("    - Start with `4-Seam Fastball -> 2-Seam Fastball`.")
print("    - Then `Slider -> Curveball` and `Slider -> Uncategorized Pitch`.")
print("    - Then `ChangeUp -> Uncategorized Pitch` and `Sinker -> 2-Seam Fastball`.")
print("    - And don't forget `Splitter` if it's still 0% accurate.")

print("\n5.  **Adjust `guess_pitch_type` rules based on the stats from `analyze_misclassification` and the validated heatmap insights.**")
print("    - Remember to consider both positive and negative HB for RH/LH movement where appropriate (e.g., cutter, slider, 2-seam, sinker, splitter).")
print("    - Pay close attention to the order of `if` statements. More distinct/specific pitches should be checked first.")

print("\n6.  **Iterate, iterate, iterate!** This process of analysis, adjustment, and re-evaluation is key.")