import glob
import os
import pandas as pd

# 1. Point this to the folder containing your CSVs
folder_path = "./"

# 2. Grab every .csv file
all_files = glob.glob(os.path.join(folder_path, "*.csv"))

# 3. Read & concatenate
df_list = [pd.read_csv(f) for f in all_files]
combined = pd.concat(df_list, ignore_index=True)

# 4. Write out
combined.to_csv("data.csv", index=False)

print(f"Merged {len(all_files)} files → combined.csv ({combined.shape[0]} rows)")
