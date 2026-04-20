import sys
import os
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.append(os.path.abspath('.'))

from analysis.parser import extract_csv_data, extract_excel_data

CSV_DIR = "/Users/pokaaa/Library/CloudStorage/ETH GDrive/My Drive/10 Research/11 Projects/Agarose-Dextran Rheology/Rheology_Raw"

def compare_files(base_name):
    csv_path = os.path.join(CSV_DIR, f"{base_name}.csv")
    xlsx_path = os.path.join(CSV_DIR, f"{base_name}.xlsx")

    print(f"\n--- Comparing {base_name} ---")
    
    if not os.path.exists(csv_path) or not os.path.exists(xlsx_path):
        print(f"Skipping {base_name}: files missing.")
        return

    csv_results = extract_csv_data(csv_path)
    xlsx_results = extract_excel_data(xlsx_path)

    print(f"CSV Blocks found: {list(csv_results.keys())}")
    print(f"XLSX Sheets found: {list(xlsx_results.keys())}")

    # Check if we have at least one common block
    # Note: Excel sheet names might be truncated or different, but data should align.
    for name in csv_results:
        # Try to find a matches in xlsx
        found_match = False
        for sheet_name in xlsx_results:
            # Simple heuristic: names start with same prefix or are same
            if name.startswith(sheet_name) or sheet_name.startswith(name):
                print(f"  Matching CSV '{name}' with XLSX '{sheet_name}'")
                df_csv = csv_results[name]
                df_xlsx = xlsx_results[sheet_name]
                
                # Compare columns (canonicalized)
                cols_csv = set(df_csv.columns)
                cols_xlsx = set(df_xlsx.columns)
                common_cols = cols_csv & cols_xlsx
                
                print(f"    Common columns: {len(common_cols)}")
                if len(common_cols) < 2:
                    print(f"    WARNING: Very few common columns! CSV: {cols_csv}, XLSX: {cols_xlsx}")
                    continue
                
                # Compare numeric data (skip unit row at 0)
                data_csv = df_csv.iloc[1:].apply(pd.to_numeric, errors='coerce').dropna(how='all')
                data_xlsx = df_xlsx.iloc[1:].apply(pd.to_numeric, errors='coerce').dropna(how='all')
                
                print(f"    CSV rows: {len(data_csv)}, XLSX rows: {len(data_xlsx)}")
                
                # Alignment check on first few rows of a shared column
                if "Time" in common_cols:
                    t_csv = data_csv["Time"].values[:5]
                    t_xlsx = data_xlsx["Time"].values[:5]
                    if len(t_csv) == len(t_xlsx) and np.allclose(t_csv, t_xlsx, atol=1e-3):
                        print("    SUCCESS: Time axes match.")
                    else:
                        print(f"    MISMATCH: Time axes differ.\n      CSV: {t_csv}\n      XLSX: {t_xlsx}")
                
                found_match = True
                break
        
        if not found_match:
            print(f"  No match found for CSV block '{name}' in Excel sheets.")

if __name__ == "__main__":
    compare_files("amplitude_sweep")
    compare_files("creep")
    compare_files("stress_relaxation")
