import sys
import os
import pandas as pd
from analysis.parser import extract_sheet_data, get_interval_info, split_intervals

csv_path = "/Users/pokaaa/Library/CloudStorage/ETH GDrive/My Drive/10 Research/11 Projects/Agarose-Dextran Rheology/Rheology_Raw/creep.csv"

# Mock Anton Paar CSV with multiple intervals
mock_csv = """Project:\tDemo
Test:\tT1
Interval data:\tTime\tStrain
0.1\t0.5
1.0\t1.0
Interval data:\tTime\tStrain
1.1\t2.0
2.0\t3.0
"""

# Test split logic
print("--- Testing split_intervals with mocked data ---")
# Manually build DF with segment indices
df1 = pd.DataFrame({'Time': [0.1, 1.0], 'Strain': [0.5, 1.0], '_segment_index_': [0, 0]})
df2 = pd.DataFrame({'Time': [1.1, 2.0], 'Strain': [2.0, 3.0], '_segment_index_': [1, 1]})
df_combined = pd.concat([df1, df2])

ivs = split_intervals(df_combined)
print(f"Found {len(ivs)} intervals (Expected 2)")
for i, iv in enumerate(ivs):
    print(f"Iv {i}: {len(iv)} rows, columns: {iv.columns.tolist()}")

print("\n--- Testing get_interval_info with creep.csv ---")
sheets = extract_sheet_data(csv_path, filename="creep.csv")
for name, df in sheets.items():
    info = get_interval_info(df)
    print(f"Sheet: {name}")
    print(f"Detected {len(info)} intervals")
    for iv in info:
        print(f"  Iv {iv['index']}: {iv['t_start']} - {iv['t_end']} s ({iv['n_rows']} pts)")
