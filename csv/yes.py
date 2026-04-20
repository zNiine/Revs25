import pandas as pd

# Load your full TrackMan dataset
df = pd.read_csv('../data.csv')  # <-- replace with your actual filename

# Filter for rows where the pitcher team is "HP"
pitching_df = df[df['PitcherTeam'] == 'YOR']

# Filter for rows where the batter team is "YOR"
batting_df = df[df['BatterTeam'] == 'STA_YAN']

# Save each filtered DataFrame to CSV
pitching_df.to_csv('pitching_YOR.csv', index=False)
batting_df.to_csv('batting_STAN.csv', index=False)

print("✅ Done! Files saved as 'pitching_HP.csv' and 'batting_YOR.csv'")
