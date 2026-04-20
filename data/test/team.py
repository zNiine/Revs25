import pandas as pd

# 1. Read your combined CSV
df = pd.read_csv("combined.csv")

# 2. Define your abbreviation → full name mapping
team_names = {
    "GAS": "Gastonia Ghost Peppers",
    "YOR": "York Revolution",
    "HAG_FLY": "Hagerstown Flying Boxcars",
    "STA_YAN": "Staten Island Ferry Hawks",
    "SMD": "South Maryland Blue Crabs",
    "HP": "High Point Rockers",
    "LI": "Long Island Ducks",
    "LAN": "Lancaster Stormers",
    "LEX_LEG": "Lexington Legends",
    "WES_POW": "Charleston Dirty Birds"
    # add the rest of your mappings here...
}

# 3. Create the two new columns by mapping the abbreviations
df["HomeNameFull"] = df["HomeTeam"].map(team_names)
df["AwayNameFull"] = df["AwayTeam"].map(team_names)

# 4. (Optional) If you want a separate lookup table as a DataFrame:
mapping_table = (
    pd.DataFrame.from_dict(team_names, orient="index", columns=["FullName"])
      .reset_index()
      .rename(columns={"index": "Abbreviation"})
)

# 5. Write out your enriched CSV (and, if desired, the lookup)
df.to_csv("combined_with_full_names.csv", index=False)
mapping_table.to_csv("team_name_lookup.csv", index=False)

print("Done!  → combined_with_full_names.csv and team_name_lookup.csv created.")
