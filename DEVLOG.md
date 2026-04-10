# Development Log — Rheology Analysis Interface

Tracks design decisions, bugs fixed, and work remaining across sessions.

---

## Architecture summary

**Backend:** FastAPI (`app.py`) — all analysis runs server-side in Python.
**Frontend:** Single-page app (`static/app.js` + `index.html` + `style.css`) using Bootstrap 5 + Plotly.js + noUiSlider. No build step; all dependencies loaded from CDN.
**Analysis modules:** `analysis/parser.py`, `creep.py`, `amplitude.py`, `relaxation.py`, `frequency.py`, `temperature.py`.

Data flow:
```
Upload .xlsx  →  POST /api/parse  →  sheet metadata + segment info
Run Analysis  →  POST /api/analyze  →  Plotly figure JSON  →  Plotly.newPlot()
```

---

## Session 1 — Initial build

**Completed:**
- Ported `extract_sheet_data()` from the Marimo notebook `interface.py`
- Implemented all five analysis modules (creep, amplitude, relaxation, frequency, temperature)
- Built the single-page app with drag-drop upload, sheet selector, parameter panels, Plotly tabs
- Added Bootstrap 5 layout, custom CSS, noUiSlider for range sliders
- Dockerfile and `requirements.txt`
- Virtual environment: `../rheology-env-modern` (Python 3.13)

---

## Session 2 — UI refinements and bug fixes

### Changes made

**Sheet selection — 3-level hierarchy**
- `parseSheetName(name)` splits `<Material>_<Replicate>` sheet names (e.g. `Agarose5_S1`).
- `renderSheetList()` completely rewritten: material group (grey header) → replicate (sheet-cb) → segment (iv-cb).
- Cascade checkbox propagation with indeterminate states at all three levels.
- Expand/collapse chevrons at material and replicate level.

**Segment labels**
- `segPhaseLabel(testType, segIndex)` returns "Creep phase" / "Recovery phase" for `creep_recovery`, "Segment N" otherwise.

**Fitting window sliders (noUiSlider)**
- Per-segment **start prune** slider (0 → t_start + 5 s range): cuts data from segment beginning.
- Per-segment **end prune** slider (t_end − 5 s → t_end range): cuts data from segment end.
- **Transition-zone slider** (double-ended, ±40 s around the gap): excludes the oscillation spike around t_release.
- `collectFitWindow()` reads all sliders and builds `exclude_ranges` list sent to backend.
- `PRUNE_WIN_S = 5`, `TZ_WIN = 40`, `TZ_DEF = 5` constants.

**Auto-rerun**
- `state.hasRun` flag set after first successful analysis.
- Any change to parameters, sliders, or sheet selection calls `scheduleRerun()` (700 ms debounce).

**Creep recovery**
- `_auto_detect_t_release`: added strain-peak fallback (Strategy 2) when no explicit value given.
- `evaluate_recovery_components`: now uses per-sample `t_release`.
- Removed "combine segments" checkbox — always combined (set `combine_segments: true` in `collectParams()`).

**Lazy Plotly rendering**
- `renderPlots()` marks each tab panel with `data-rendered`.
- Tabs render their Plotly charts only when first clicked (fixes blank charts in hidden tabs, including Recovery Components bar chart).

**NaN serialisation**
- `_sanitize()` recursive function in `app.py` replaces all `NaN`/`Inf` (Python and numpy) with `null` before JSON serialisation.

**Cache-busting**
- Static assets versioned with `?v=N` query strings (`app.js?v=6`, `style.css?v=4`).

**Removed**
- `<option value="auto">` from test type selector — user must explicitly select test type.

---

## Session 3 — Segment detection fix (last session)

### Root cause identified

User's creep/recovery data (`Ag_Dex_Creep.xlsx`) stores creep and recovery phases as a **continuous time series within each sheet** — time goes 0 → 285 s, then jumps to 330 → 900 s (a ~45 s gap, no time reset). The old `split_intervals()` only split on `np.diff(t) < 0` (time decrease), so each sheet was returned as **one segment of ~276 points** instead of two.

### Fixes applied

**`analysis/parser.py` — `split_intervals()`** (line ~290)

Added gap detection alongside the existing reset detection:

```python
diffs = np.diff(t)
pos_diffs = diffs[diffs > 0]
typical_dt = float(np.median(pos_diffs)) if len(pos_diffs) >= 5 else 1.0
gap_threshold = max(15.0 * typical_dt, 20.0)
split_mask = (diffs < 0) | (diffs > gap_threshold)
```

**`app.py` — `_combine_intervals()`** (line ~165)

For gap-based splits the segment times are already absolute, so the offset must NOT be added:

```python
t_first = float(t_valid.iloc[0])
if t_first > time_offset + 1.0:
    # Gap split — absolute times, no offset
    time_offset = float(t_valid.max())
else:
    # Reset split — add cumulative offset
    df_c['Time'] = t + time_offset
    time_offset += float(t_valid.max())
```

**`static/app.js` — `getSelectedSegments()`** (line ~479)

Mirrors the same logic on the frontend to compute per-segment slider ranges:

```javascript
if (rawStart > offset + 1.0) {
    // Gap split: times absolute
    t_start = rawStart; t_end = rawEnd; offset = rawEnd;
} else {
    // Reset split: add offset
    t_start = rawStart + offset; t_end = rawEnd + offset; offset += rawEnd;
}
```

**Expected result after this fix:**
- Each sheet shows **2 segments** (Creep phase / Recovery phase) in the sheet selector.
- The transition-zone slider appears between them.
- Burgers model fitting should produce meaningful R² values (the -1.4 observed before was caused by fitting a combined blob with no t_release boundary).

---

## Known issues / to-do next session

### High priority

1. **Verify the segment fix works end-to-end**
   - Upload `Ag_Dex_Creep.xlsx`, confirm each replicate shows 2 segments.
   - Confirm Burgers fit R² is positive and plausible (typically > 0.9 for agarose gels).
   - Confirm Recovery Components bar chart appears (lazy-render was implemented but not confirmed with real data).

2. **Recovery components bar chart**
   - Implemented lazy-render in `renderPlots()` using `data-rendered` attribute.
   - If still blank: check that `build_recovery_component_figures()` in `creep.py` returns a non-empty figure (needs at least one sample with `f_elastic + f_viscoelastic + f_plastic` summing to ~1, i.e. values between 0 and 1, not 0–5000%).
   - The fraction axis scale was previously showing 5000% — check that `evaluate_recovery_components()` returns fractions (0–1) not percentages.

### Medium priority

3. **Overlay mode for replicates**
   - When "Overlay all samples" is ticked and multiple replicates are selected, all fit curves should appear on one set of axes with a shared legend. Verify this works with 3 replicates.

4. **Segment slider range when only one segment selected**
   - If the user deselects "Recovery phase" and keeps only "Creep phase", `getSelectedSegments()` should return just one segment with t_start=0, t_end≈285 s, and no transition-zone slider should appear.

5. **Download button includes recovery components**
   - Currently the Excel download writes `Creep_Recovery` and `Recovery_Components` sheets. Verify the component fractions appear correctly in the downloaded file.

### Low priority / future features

6. **Mean ± SD across replicates** — add a summary row/plot showing mean and standard deviation of Burgers parameters (E1, E2, η1, η2) across all selected replicates.

7. **Multi-file upload** — allow loading several `.xlsx` files at once and merging the sheet lists.

8. **Responsive mobile layout** — the sidebar collapses on small screens but the plot height should also adapt.

9. **Export plots as SVG/PNG** — add a "Save figure" button that calls `Plotly.downloadImage()`.

---

## File version index

| File | Version / notes |
|------|----------------|
| `static/app.js` | `?v=6` — segment gap fix in `getSelectedSegments()` |
| `static/style.css` | `?v=4` — material-group + noUiSlider custom theme |
| `static/index.html` | Cache-busts `app.js?v=6`, `style.css?v=4`; no auto test type option |
| `analysis/parser.py` | Gap detection in `split_intervals()` added session 3 |
| `app.py` | `_combine_intervals()` gap-aware logic added session 3 |

---

## Environment

| Item | Value |
|------|-------|
| Python | 3.13 |
| Virtual env | `../rheology-env-modern` (one level above `rheology-webapp/`) |
| Run command | `"$VENV/bin/uvicorn" app:app --port 2719` |
| Key packages | fastapi, uvicorn, pandas, numpy, scipy, plotly, openpyxl |
