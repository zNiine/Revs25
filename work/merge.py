import pandas as pd

# 1) Load CSVs, parsing the datetime columns by name
df_g = pd.read_csv('04-27_@_Gastonia_.csv', parse_dates=['Pitch Time'])
df_h = pd.read_csv('hitting.csv',       parse_dates=['Hit Time'])

# 2) Localize each to its correct timezone
df_g['Pitch Time'] = df_g['Pitch Time'].dt.tz_localize('UTC')
df_h['Hit Time']   = df_h['Hit Time'].dt.tz_localize('America/New_York')

# 3) Convert both to UTC and strip tz for a common key
df_g['time_utc'] = (
    df_g['Pitch Time']
      .dt.tz_convert('UTC')
      .dt.tz_localize(None)
)
df_h['time_utc'] = (
    df_h['Hit Time']
      .dt.tz_convert('UTC')
      .dt.tz_localize(None)
)

# 4) Select only the hitting columns you want to add
#    (keep all except the original 'Hit Time' and helper key)
h_cols = [c for c in df_h.columns if c not in ['Hit Time', 'time_utc']]
df_h_small = df_h[['time_utc'] + h_cols]

# 5) Left-merge into the Gastonia DataFrame
merged = pd.merge(
    df_g,
    df_h_small,
    on='time_utc',
    how='left',
    suffixes=('', '_hit')
)

# 6) Drop the helper column if you don’t need it
merged.drop(columns=['time_utc'], inplace=True)

# 7) Export to a new CSV
merged.to_csv('gastonia_enriched.csv', index=False)

print("Wrote merged file to gastonia_enriched.csv")
