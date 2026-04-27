import pandas as pd
from analysis.amplitude import analyze_lver

file_path = "/Users/pokaaa/Library/CloudStorage/ETH GDrive/My Drive/10 Research/11 Projects/Agarose-Dextran Rheology/Rheology_Raw/amplitude_sweep.csv"
from analysis.parser import parse_antonpaar_csv

with open(file_path, "rb") as f:
    raw = f.read()

sheets = parse_antonpaar_csv(raw)

for name, df in sheets.items():
    print(f"Sheet: {name}")
    print(df.head())
    res = analyze_lver([(name, df)], plateau_points=3, deviation=0.1)
    print(res)
    break
