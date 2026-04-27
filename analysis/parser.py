"""
Excel and CSV parser for Anton Paar / TA Instruments rheometer data files.
Ported from interface.py (Gabriel David, 2025).
Made robust to various export formats and user modifications.
"""
import io
import re
import pandas as pd

# Columns that indicate each test type
_TEST_TYPE_SIGNATURES = {
    "creep_recovery": ["Creep Compliance", "Shear Strain"],
    "amplitude_sweep": ["Storage Modulus", "Loss Modulus", "Shear Strain"],
    "frequency_sweep": ["Storage Modulus", "Loss Modulus", "Angular Frequency"],
    "stress_relaxation": ["Shear Stress", "Time"],
    "temperature_sweep": ["Temperature", "Storage Modulus"],
}

# Common column name variations across rheometer brands / export versions
_COLUMN_ALIASES = {
    "Angular Frequency": ["Angular Frequency", "Angular frequency", "angular frequency",
                          "Ang. Frequency", "omega", "ω", "Frequency (rad/s)"],
    "Frequency":         ["Frequency", "frequency", "Freq.", "f (Hz)"],
    "Storage Modulus":   ["Storage Modulus", "Storage modulus", "G'", "G′", "G'(Pa)", "G' (Pa)"],
    "Loss Modulus":      ["Loss Modulus", "Loss modulus", "G''", "G″", "G''(Pa)", "G'' (Pa)"],
    "Shear Stress":      ["Shear Stress", "Shear stress", "Stress", "τ", "Stress (Pa)"],
    "Shear Strain":      ["Shear Strain", "Shear strain", "Strain", "γ", "Strain (%)", "Strain(%)"],
    "Creep Compliance":  ["Creep Compliance", "Creep compliance", "J(t)", "Compliance"],
    "Complex Viscosity": ["Complex Viscosity", "Complex viscosity", "|η*|", "Eta* (Pa.s)"],
    "Temperature":       ["Temperature", "temperature", "Temp", "T (°C)", "T(°C)"],
    "Time":              ["Time", "time", "t (s)", "t(s)", "Time (s)"],
    "Phase Angle":       ["Phase Angle", "Phase angle", "delta", "δ", "tan(δ)"],
}

# Reverse lookup: raw name → canonical name
_ALIAS_MAP: dict[str, str] = {}
for canonical, aliases in _COLUMN_ALIASES.items():
    for alias in aliases:
        _ALIAS_MAP[alias] = canonical


def _canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to canonical names where aliases are known."""
    rename = {}
    for col in df.columns:
        if col in _ALIAS_MAP and col not in _COLUMN_ALIASES:
            rename[col] = _ALIAS_MAP[col]
    if rename:
        df = df.rename(columns=rename)
    return df


def _find_header_row(df_raw: pd.DataFrame) -> int | None:
    """Find the row index that contains column headers."""
    # Strategy 1: explicit "Interval data:" marker
    col0 = df_raw.iloc[:, 0].astype(str)
    mask = col0.str.contains("Interval data:", na=False)
    if mask.any():
        return int(mask[mask].index[0])

    # Strategy 2: known names
    known = set(_ALIAS_MAP.keys()) | set(_COLUMN_ALIASES.keys())
    for i in range(min(30, len(df_raw))):
        row_vals = set(str(v).strip() for v in df_raw.iloc[i] if pd.notna(v))
        if len(row_vals & known) >= 2:
            return i
    return None


def _find_data_start(df_raw: pd.DataFrame, header_row: int) -> int:
    """Find the first row of numeric data after the header row."""
    for i in range(header_row + 1, min(header_row + 5, len(df_raw))):
        row = df_raw.iloc[i]
        n_numeric = sum(1 for v in row if pd.api.types.is_number(v) and pd.notna(v))
        if n_numeric >= 2:
            return i
    return header_row + 2  # Fallback


def _extract_units_row(df_raw, header_row, data_start, headers):
    """Extract units from the row(s) between header and data."""
    units = {}
    for i in range(header_row + 1, data_start):
        row = df_raw.iloc[i]
        for col_idx, h in enumerate(headers):
            if col_idx >= len(row): continue
            u = str(row.iloc[col_idx]).strip()
            if u and '[' in u:
                units[h] = re.sub(r'[\[\]\s]', '', u)
    return units


def extract_sheet_data(source, filename: str = None) -> dict[str, pd.DataFrame]:
    """Dispatch to Excel or CSV parser."""
    if filename and filename.lower().endswith('.csv'):
        return extract_csv_data(source)
    if isinstance(source, (bytes, bytearray)) and source.startswith(b'\xff\xfe'):
        return extract_csv_data(source)
    
    try:
        return extract_excel_data(source)
    except Exception:
        try:
            return extract_csv_data(source)
        except Exception:
            raise


def extract_csv_data(source) -> dict[str, pd.DataFrame]:
    """Parse Anton Paar CSV (UTF-16LE). Supports Project:::Test hierarchy."""
    if isinstance(source, (bytes, bytearray)):
        content = source.decode('utf-16le', errors='replace')
    elif isinstance(source, io.IOBase):
        content = source.read()
        if isinstance(content, bytes):
            content = content.decode('utf-16le', errors='replace')
    else:
        with open(source, 'r', encoding='utf-16le', errors='replace') as f:
            content = f.read()

    # Clean BOM and normalise line endings
    content = content.replace('\ufeff', '').replace('\r\n', '\n')

    # Split into Projects. The pattern matches 'Project:' at the start of a line.
    # We use a lookahead or just find all matches.
    project_matches = list(re.finditer(r'^Project:\t(.*)$', content, re.MULTILINE))
    
    results = {}
    
    # If no Project: tag found, treat whole file as one unnamed project
    if not project_matches:
        p_blocks = [("Default Project", content)]
    else:
        p_blocks = []
        for i, m in enumerate(project_matches):
            p_name = m.group(1).strip()
            start = m.end()
            end = project_matches[i+1].start() if i+1 < len(project_matches) else len(content)
            p_blocks.append((p_name, content[start:end]))

    for project_name, p_content in p_blocks:
        # Split Project into Tests
        test_matches = list(re.finditer(r'^Test:\t(.*)$', p_content, re.MULTILINE))
        
        if not test_matches:
            t_blocks = [("Default Test", p_content)]
        else:
            t_blocks = []
            for i, m in enumerate(test_matches):
                t_name = m.group(1).strip()
                start = m.end()
                end = test_matches[i+1].start() if i+1 < len(test_matches) else len(p_content)
                t_blocks.append((t_name, p_content[start:end]))

        for test_name, t_content in t_blocks:
            t_lines = t_content.splitlines()
            
            res_type = ""
            for line in t_lines:
                if line.startswith("Result:"):
                    res_type = line.split('\t')[-1].strip()
                    break
            
            display_name = f"{project_name}:::{test_name}"
            if res_type: display_name += f" ({res_type})"
            
            # Find intervals
            idx_list = [i for i, l in enumerate(t_lines) if "Interval data:" in l]
            if not idx_list: continue
            
            all_dfs = []
            test_units = {}
            for i, start_idx in enumerate(idx_list):
                tokens = t_lines[start_idx].split('\t')
                col_offset = 1 if tokens[0].strip().startswith("Interval data:") else 0
                headers = [h.strip() for h in tokens[col_offset:] if h.strip()]
                
                # Units
                units = {}
                data_start = start_idx + 1
                for j in range(start_idx + 1, min(start_idx + 6, len(t_lines))):
                    if '[' in t_lines[j]:
                        u_tokens = t_lines[j].split('\t')
                        for k, h in enumerate(headers):
                            if (col_offset + k) < len(u_tokens):
                                u = u_tokens[col_offset+k].strip()
                                if u: units[h] = re.sub(r'[\[\]\s]', '', u)
                        data_start = j + 1
                        break
                test_units.update(units)
                
                # Data
                end_limit = idx_list[i+1] if i+1 < len(idx_list) else len(t_lines)
                rows = []
                for r in range(data_start, end_limit):
                    line = t_lines[r].strip()
                    if not line or any(line.startswith(m) for m in ["Interval and", "Result:", "Test:", "Project:"]):
                        continue
                    tokens = t_lines[r].split('\t')
                    row = [tokens[col_offset+k].strip() if (col_offset+k)<len(tokens) else "" for k in range(len(headers))]
                    if any(row): rows.append(row)
                
                if rows:
                    df_iv = pd.DataFrame(rows, columns=headers)
                    for col in df_iv.columns:
                        df_iv[col] = pd.to_numeric(df_iv[col], errors='coerce')
                    df_iv.dropna(how='all', inplace=True)
                    if not df_iv.empty:
                        df_iv["_segment_index_"] = i  # Mark interval boundary for split_intervals
                        all_dfs.append(df_iv)

            if not all_dfs: continue
            full_df = pd.concat(all_dfs, ignore_index=True)
            units_row = pd.DataFrame([[test_units.get(h, '') for h in full_df.columns]], columns=full_df.columns)
            final_df = pd.concat([units_row, full_df], ignore_index=True)
            final_df = _canonicalize_columns(final_df)
            
            canon_units = {(_ALIAS_MAP.get(h, h)): u for h, u in test_units.items()}
            final_df.attrs["units"] = canon_units
            
            # Disambiguate key
            k = display_name
            c = 1
            while k in results:
                c += 1
                k = f"{display_name} ({c})"
            results[k] = final_df
            
    return results


def extract_excel_data(source) -> dict[str, pd.DataFrame]:
    """Parse rheometer Excel file."""
    if isinstance(source, (bytes, bytearray)): source = io.BytesIO(source)
    xls = pd.ExcelFile(source)
    sheets_dict = {}

    for sheet_name in xls.sheet_names:
        try:
            df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        except Exception: continue
        if df_raw.empty or df_raw.shape[1] < 2: continue

        header_row_idx = _find_header_row(df_raw)
        if header_row_idx is None: continue
        
        # Determine offset
        first_cell = str(df_raw.iloc[header_row_idx, 0]).strip()
        col_start = 1 if first_cell.startswith("Interval data:") else 0
        
        row_vals = df_raw.iloc[header_row_idx, col_start:].tolist()
        headers = [str(v).strip() for v in row_vals if pd.notna(v) and str(v).strip()]
        if not headers: continue

        data_start_idx = _find_data_start(df_raw, header_row_idx)
        units = _extract_units_row(df_raw, header_row_idx, data_start_idx, headers)

        data = df_raw.iloc[data_start_idx:, col_start:col_start+len(headers)].copy()
        data.columns = headers
        for col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
        data.dropna(how='all', inplace=True)
        data.dropna(thresh=2, inplace=True)

        if len(data) < 2: continue
        
        # Create units row
        u_row = pd.DataFrame([[units.get(h, '') for h in headers]], columns=headers)
        
        # Mark as segment 0 if no other info. 
        # (Extension would be to repeat the header search throughout the sheet)
        data["_segment_index_"] = 0
        
        final_df = pd.concat([u_row, data], ignore_index=True)
        final_df = _canonicalize_columns(final_df)
        
        canon_units = {(_ALIAS_MAP.get(h, h)): u for h, u in units.items()}
        final_df.attrs["units"] = canon_units
        sheets_dict[sheet_name] = final_df

    return sheets_dict


def _is_column_header(s: str) -> bool:
    """True if the string looks like a column header (not a row marker)."""
    if not s:
        return False
    known = set(_ALIAS_MAP.keys()) | set(_COLUMN_ALIASES.keys())
    return s in known or any(k.lower() in s.lower() for k in known)


def detect_test_type(df: pd.DataFrame) -> str:
    """
    Auto-detect test type from column names.

    Returns one of: 'creep_recovery', 'amplitude_sweep', 'frequency_sweep',
    'stress_relaxation', 'temperature_sweep', 'unknown'
    """
    cols = set(df.columns)

    # Angular Frequency is unambiguous — must come first.
    if ("Angular Frequency" in cols or "Frequency" in cols) and "Storage Modulus" in cols:
        return "frequency_sweep"
    # Amplitude sweep: Shear Strain is the swept variable.
    # Check before temperature_sweep because amplitude-sweep files often carry a
    # constant Temperature column that would otherwise trigger a false match.
    if "Storage Modulus" in cols and "Shear Strain" in cols:
        return "amplitude_sweep"
    # Temperature sweep: Temperature must actually vary (not just be a constant setpoint).
    if "Temperature" in cols and "Storage Modulus" in cols:
        temp_vals = pd.to_numeric(df["Temperature"], errors="coerce").dropna()
        if len(temp_vals) >= 3 and (temp_vals.max() - temp_vals.min()) > 2.0:
            return "temperature_sweep"
    if "Creep Compliance" in cols:
        return "creep_recovery"
    if "Shear Stress" in cols and "Time" in cols:
        if "Shear Strain" not in cols:
            return "stress_relaxation"
        # Both Shear Stress and Shear Strain present: check whether strain is nearly constant.
        # In stress relaxation the strain is the controlled variable (fixed), so its coefficient
        # of variation should be very small after the initial loading transient.
        # The first 20 points are skipped because the loading ramp can show large variations
        # that would otherwise inflate the CV and mask a true stress-relaxation experiment.
        strain_vals = pd.to_numeric(df["Shear Strain"], errors="coerce").dropna()
        stable = strain_vals.iloc[20:] if len(strain_vals) > 20 else strain_vals
        if len(stable) >= 3:
            mean_abs = abs(float(stable.mean()))
            cv = float(stable.std()) / mean_abs if mean_abs > 1e-12 else float("inf")
            if cv < 0.05:
                return "stress_relaxation"
    if "Shear Strain" in cols and "Time" in cols:
        return "creep_recovery"
    return "unknown"


def get_data_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return the data part (rows 1+) of a sheet DataFrame."""
    return df.iloc[1:].copy()


def get_units(df: pd.DataFrame) -> dict[str, str]:
    """Return the units mapping from row 0 of a sheet DataFrame."""
    if hasattr(df, "attrs") and "units" in df.attrs:
        return df.attrs["units"]
    headers = df.columns
    units_row = df.iloc[0]
    return {h: str(u) for h, u in zip(headers, units_row) if pd.notna(u)}


def detect_test_type(df: pd.DataFrame) -> str:
    """Detect test type based on column availability."""
    cols = set(df.columns)
    for tt, sig in _TEST_TYPE_SIGNATURES.items():
        if all(col in cols for col in sig):
            return tt
    return "unknown"


def split_intervals(df: pd.DataFrame, split_on_gaps: bool = False) -> list[pd.DataFrame]:
    """
    Split a continuous DataFrame into segments.
    Two strategies:
      1. Time reset (Time goes back to near-zero)
      2. Large gap (Time jump > 5s, if split_on_gaps=True)
    """
    # Strategy 0: Explicit segment indices from parser
    if "_segment_index_" in df.columns:
        seg_ids = df["_segment_index_"].values
        splits = [0]
        for i in range(1, len(seg_ids)):
            if seg_ids[i] != seg_ids[i-1]:
                splits.append(i)
        splits.append(len(df))
        intervals = []
        for i in range(len(splits) - 1):
            iv = df.iloc[splits[i]:splits[i + 1]].copy()
            # Drop the helper column
            iv = iv.drop(columns=["_segment_index_"])
            if not iv.empty:
                intervals.append(iv)
        return intervals

    # Strategy 1 & 2: Time-based heuristics (fallback)
    times = pd.to_numeric(df["Time"], errors='coerce').fillna(0).values
    if len(times) < 2:
        return [df]

    splits = [0]
    for i in range(1, len(times)):
        # Reset detection
        if times[i] < times[i - 1] - 0.5:
            splits.append(i)
        # Gap detection
        elif split_on_gaps and (times[i] > times[i - 1] + 5.0):
            splits.append(i)

    splits.append(len(df))
    intervals = []
    for i in range(len(splits) - 1):
        iv = df.iloc[splits[i]:splits[i + 1]].copy()
        if not iv.empty:
            intervals.append(iv)
    return intervals


def get_interval_info(df: pd.DataFrame, split_on_gaps: bool = False) -> list[dict]:
    """Summarize intervals for the UI."""
    intervals = split_intervals(df, split_on_gaps=split_on_gaps)
    info = []
    for i, iv in enumerate(intervals):
        t = pd.to_numeric(iv["Time"], errors='coerce')
        info.append({
            "index": i,
            "n_rows": len(iv),
            "t_start": round(float(t.min()), 1) if not t.empty else 0,
            "t_end": round(float(t.max()), 1) if not t.empty else 0,
        })
    return info
