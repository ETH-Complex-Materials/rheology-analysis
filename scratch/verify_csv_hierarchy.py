import sys
import os
import pandas as pd
from analysis.parser import extract_sheet_data, get_data_df, split_intervals

csv_path = "/Users/pokaaa/Library/CloudStorage/ETH GDrive/My Drive/10 Research/11 Projects/Agarose-Dextran Rheology/Rheology_Raw/creep.csv"

with open(csv_path, 'rb') as f:
    raw = f.read()

sheets = extract_sheet_data(raw, filename="creep.csv")

print(f"Detected {len(sheets)} sheets:")
for name in sheets.keys():
    print(f" - {name}")
    df = get_data_df(sheets[name])
    ivs = split_intervals(df, split_on_gaps=False)
    print(f"   Rows: {len(df)}, Intervals: {len(ivs)}")
    for i, iv in enumerate(ivs):
        print(f"     Iv {i}: {len(iv)} rows, Time range: {iv['Time'].min()} to {iv['Time'].max()}")

# Verify if hierarchy separator is correct
for name in sheets:
    if ":::" not in name:
        print(f"FAILURE: Hierarchy separator missing in name '{name}'")
        sys.exit(1)

print("\nSUCCESS: CSV Hierarchy parsing verified.")
