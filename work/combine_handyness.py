import pandas as pd

# Set folder path and file names
 # Replace with your folder path
lhb_file = 'lhb.csv'
rhb_file = 'rhb.csv'

# Load the LHB (left-handed batter) data and add the Handedness column
lhb_df = pd.read_csv(lhb_file, encoding='ISO-8859-1')
lhb_df['Handedness'] = 'L'  # Left-handed batter

# Load the RHB (right-handed batter) data and add the Handedness column
rhb_df = pd.read_csv(rhb_file, encoding='ISO-8859-1')
rhb_df['Handedness'] = 'R'  # Right-handed batter

# Combine the two dataframes
combined_df = pd.concat([lhb_df, rhb_df], ignore_index=True)

# Optional: Save the combined dataframe to a new CSV file
combined_df.to_csv("combined_data.csv", index=False)

# Show the first few rows of the combined dataframe
print(combined_df.head())
