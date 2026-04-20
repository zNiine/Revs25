import requests
from bs4 import BeautifulSoup
import csv

# Define your dictionary of team IDs.
team_ids = {
    "Hagerstown": 163525,
    "Lancaster": 3613,
    "Long Island": 3609,
    "State Island": 163526,
    "York": 3614,
    "Charleston": 163527,
    "Gastonia": 163528,
    "High Point": 163529,
    "Lexington": 163530,
    "Southern Maryland": 3608
}





# Base URL format with placeholders for teamid and seasonid.
base_url = "https://baseball.pointstreak.com/print.html?teamid={teamid}&seasonid=34102&print=1"

# This list will hold all our roster data.
roster_data = []

# Loop through each team.
for team_name, teamid in team_ids.items():
    url = base_url.format(teamid=teamid)
    print(f"Scraping {team_name} from URL: {url}")
    response = requests.get(url)
    
    # Check if the page was retrieved successfully.
    if response.status_code != 200:
        print(f"Failed to retrieve data for {team_name} (teamid: {teamid})")
        continue

    soup = BeautifulSoup(response.text, "html.parser")

    # Find all tables with the class that holds the stats.
    tables = soup.find_all("table", class_="psbb_stats_table")
    
    # Loop over each table found.
    for table in tables:
        # Use the header row to filter out non-player tables (like Staff).
        header = table.find("tr")
        if header:
            headers = [th.get_text(strip=True) for th in header.find_all("th")]
            # Only process tables with a "Player" header.
            if "Player" not in headers:
                continue

        # Iterate over the rows, skipping the header.
        rows = table.find_all("tr")[1:]
        for row in rows:
            cells = row.find_all("td")
            # Ensure there are enough cells (we expect at least 5: #, Player, Position, B/T, Ht).
            if len(cells) < 5:
                continue
            # Extract the needed data.
            player_name = cells[1].get_text(strip=True)
            position = cells[2].get_text(strip=True)
            bt = cells[3].get_text(strip=True)
            ht = cells[4].get_text(strip=True)
            
            # Create new columns from B/T:
            # B: first letter of B/T, T: last letter of B/T
            b_val = bt[0] if bt else ""
            t_val = bt[-1] if bt else ""
            
            # Append the extracted information along with the team name.
            roster_data.append({
                "Team": team_name,
                "Player": player_name,
                "Position": position,
                "Ht": ht,
                "B": b_val,
                "T": t_val
            })

# Write the collected data to a CSV file.
with open("rosters_25.csv", "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["Team", "Player", "Position", "B/T", "Ht", "B", "T"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    
    writer.writeheader()
    for entry in roster_data:
        writer.writerow(entry)

print("Data exported to rosters.csv")
