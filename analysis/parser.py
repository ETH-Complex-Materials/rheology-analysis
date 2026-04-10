"""
Excel parser for Anton Paar / TA Instruments rheometer data files.
Ported from interface.py (Gabriel David, 2025).
Made robust to various export formats and user modifications.
"""
import io
import re
import numpy as np
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
    """
    Find the row index that contains column headers.
    Strategy (in order):
      1. Row containing "Interval data:" in first column
      2. Row containing known rheology column names
      3. First row where many string cells appear before numeric rows
    Returns the row index of the header, or None if not found.
    """
    # Strategy 1: explicit "Interval data:" marker (Anton Paar format)
    col0 = df_raw.iloc[:, 0].astype(str)
    mask = col0.str.contains("Interval data:", na=False)
    if mask.any():
        return int(mask[mask].index[0])

    # Strategy 2: row containing known rheology column names
    known = set(_ALIAS_MAP.keys()) | set(_COLUMN_ALIASES.keys())
    for i in range(min(30, len(df_raw))):
        row_vals = set(str(v).strip() for v in df_raw.iloc[i] if pd.notna(v))
        if len(row_vals & known) >= 2:
            return i

    # Strategy 3: first row that looks like headers (mostly strings, followed by numeric rows)
    for i in range(min(20, len(df_raw) - 3)):
        row = df_raw.iloc[i]
        n_str = sum(1 for v in row if isinstance(v, str) and v.strip())
        n_num_after = sum(
            1 for v in df_raw.iloc[i + 2] if pd.api.types.is_number(v) and pd.notna(v)
        )
        if n_str >= 3 and n_num_after >= 3:
            return i

    return None


def _find_data_start(df_raw: pd.DataFrame, header_row: int) -> int:
    """
    Find the first row of numeric data after the header row.
    Skips one optional units row.
    """
    for i in range(header_row + 1, min(header_row + 5, len(df_raw))):
        row = df_raw.iloc[i]
        n_numeric = sum(
            1 for v in row
            if pd.api.types.is_number(v) and pd.notna(v)
        )
        if n_numeric >= 2:
            return i
    return header_row + 2  # fallback


def _extract_units_row(df_raw: pd.DataFrame, header_row: int, data_start: int,
                        headers: list) -> dict[str, str]:
    """Extract units from the row between header and data (if it exists)."""
    units: dict[str, str] = {}
    units_row_idx = data_start - 1
    if units_row_idx <= header_row:
        return units
    units_row = df_raw.iloc[units_row_idx]
    # Align to headers (header row starts at col 0 or col 1 depending on format)
    # Try to figure out offset
    header_row_data = df_raw.iloc[header_row]
    offset = 0
    for j, v in enumerate(header_row_data):
        if str(v).strip() == str(headers[0]).strip():
            offset = j
            break
    for k, h in enumerate(headers):
        col_idx = offset + k
        if col_idx < len(units_row):
            u = units_row.iloc[col_idx]
            if pd.notna(u) and str(u).strip():
                unit_str = re.sub(r'[\[\]\s]', '', str(u))
                units[h] = unit_str
    return units


def extract_sheet_data(source) -> dict[str, pd.DataFrame]:
    """
    Parse a rheometer Excel file (Anton Paar, TA Instruments, or similar).

    Parameters
    ----------
    source : str | bytes | BytesIO
        File path or raw bytes of the .xlsx file.

    Returns
    -------
    dict[sheet_name -> DataFrame]
        Each DataFrame has a first row containing unit strings,
        followed by numeric data rows.
        df.attrs["units"] = {column_name: unit_string}
    """
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)

    xls = pd.ExcelFile(source)
    sheets_dict: dict[str, pd.DataFrame] = {}

    for sheet_name in xls.sheet_names:
        try:
            df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        except Exception:
            continue

        if df_raw.empty or df_raw.shape[1] < 2:
            continue

        header_row_index = _find_header_row(df_raw)
        if header_row_index is None:
            continue

        # Determine column offset (Anton Paar uses col index 1+; others start at 0)
        first_cell = str(df_raw.iloc[header_row_index, 0]).strip()
        uses_offset = first_cell.startswith("Interval data:") or not _is_column_header(first_cell)
        col_start = 1 if uses_offset else 0

        headers = [
            v for v in df_raw.iloc[header_row_index, col_start:].tolist()
            if pd.notna(v) and str(v).strip()
        ]
        if not headers:
            continue

        data_start_index = _find_data_start(df_raw, header_row_index)

        # Extract units row (between header and data)
        raw_units = _extract_units_row(df_raw, header_row_index, data_start_index, headers)

        # Slice data
        data = df_raw.iloc[data_start_index:, col_start:col_start + len(headers)].copy()
        data.columns = headers

        # Keep only rows where at least one numeric value is present
        for col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
        data.dropna(how='all', inplace=True)
        data.dropna(thresh=2, inplace=True)

        if len(data) < 3:
            continue

        # Build units row as first row of final df
        units_df = pd.DataFrame(
            [[raw_units.get(h, '') for h in headers]],
            columns=headers
        )
        final_df = pd.concat([units_df, data], ignore_index=True)
        final_df.dropna(axis=1, how='all', inplace=True)

        # Canonicalize column names
        final_df = _canonicalize_columns(final_df)

        # Re-sync units dict after canonicalization
        canon_units = {}
        for raw_name, unit in raw_units.items():
            canon = _ALIAS_MAP.get(raw_name, raw_name)
            canon_units[canon] = unit
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

    if "Temperature" in cols and "Storage Modulus" in cols:
        return "temperature_sweep"
    if ("Angular Frequency" in cols or "Frequency" in cols) and "Storage Modulus" in cols:
        return "frequency_sweep"
    if "Storage Modulus" in cols and "Shear Strain" in cols:
        return "amplitude_sweep"
    if "Creep Compliance" in cols:
        return "creep_recovery"
    if "Shear Stress" in cols and "Time" in cols and "Shear Strain" not in cols:
        return "stress_relaxation"
    if "Shear Strain" in cols and "Time" in cols:
        return "creep_recovery"
    return "unknown"


def get_data_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return numeric-only rows (skip the units row at index 0)."""
    data = df.iloc[1:].copy()
    data = data.apply(pd.to_numeric, errors='coerce')
    data.dropna(how='all', inplace=True)
    return data


def get_units(df: pd.DataFrame) -> dict[str, str]:
    """Extract units dict from DataFrame (stored in attrs or first row)."""
    if "units" in df.attrs:
        return df.attrs["units"]
    units_row = df.iloc[0]
    return {col: re.sub(r'[\[\]\s]', '', str(val)) for col, val in units_row.items()
            if pd.notna(val)}


def get_interval_info(df: pd.DataFrame) -> list[dict]:
    """Return metadata for each interval (time range, n_rows, detected test type)."""
    intervals = split_intervals(df)
    result = []
    for i, iv in enumerate(intervals):
        if "Time" in iv.columns:
            t = pd.to_numeric(iv["Time"], errors='coerce').dropna()
            t_start = round(float(t.iloc[0]), 2) if len(t) > 0 else None
            t_end   = round(float(t.iloc[-1]), 2) if len(t) > 0 else None
        else:
            t_start = t_end = None
        result.append({
            "index":     i,
            "n_rows":    len(iv),
            "t_start":   t_start,
            "t_end":     t_end,
            "test_type": detect_test_type(iv),
        })
    return result


def split_intervals(df: pd.DataFrame, time_col: str = "Time") -> list[pd.DataFrame]:
    """
    Split a DataFrame into separate intervals when time resets (decreases)
    OR when there is a large time gap between consecutive rows.
    Returns a list of DataFrames, one per interval.
    """
    if time_col not in df.columns:
        return [df]

    t = pd.to_numeric(df[time_col], errors='coerce').fillna(0).values
    diffs = np.diff(t)

    # Estimate typical dt from positive increments
    pos_diffs = diffs[diffs > 0]
    typical_dt = float(np.median(pos_diffs)) if len(pos_diffs) >= 5 else 1.0
    gap_threshold = max(15.0 * typical_dt, 20.0)

    split_mask = (diffs < 0) | (diffs > gap_threshold)
    split_points = [0] + list(np.where(split_mask)[0] + 1) + [len(t)]

    intervals = []
    for i in range(len(split_points) - 1):
        chunk = df.iloc[split_points[i]:split_points[i+1]].copy().reset_index(drop=True)
        if len(chunk) >= 5:
            intervals.append(chunk)
    return intervals if intervals else [df]


def check_time_consistency(df_dict: dict) -> bool | None:
    """Check if all sheets share the same time axis."""
    ref_series = None
    for sheet_name, df in df_dict.items():
        data = get_data_df(df)
        if "Time" not in data.columns:
            return None
        time_vals = pd.to_numeric(data["Time"], errors="coerce").dropna().reset_index(drop=True)
        if ref_series is None:
            ref_series = time_vals
            continue
        if len(time_vals) != len(ref_series):
            return False
        if not np.allclose(time_vals.values, ref_series.values, atol=1e-12, rtol=0):
            return False
    return True
