/**
 * Rheology Analysis Web App — frontend logic
 */

// ===== Analysis descriptions (HTML + LaTeX via MathJax) =====
const DESCRIPTIONS = {
  creep_recovery: {
    'Creep/Recovery Fits': `
      <p>The <strong>four-element Burgers model</strong> decomposes deformation into three additive contributions.</p>
      <p><strong>Creep phase</strong> ($t \\le t_\\text{release}$):</p>
      $$\\varepsilon(t) = \\underbrace{\\frac{\\sigma_0}{G_1}}_{\\text{elastic}} + \\underbrace{\\frac{\\sigma_0}{\\eta_1}\\,t}_{\\text{viscous flow}} + \\underbrace{\\frac{\\sigma_0}{G_2}\\!\\left(1-e^{-t/\\tau_2}\\right)}_{\\text{retarded elastic}}$$
      <p><strong>Recovery phase</strong> ($t > t_\\text{release}$):</p>
      $$\\varepsilon(t) = \\frac{\\sigma_0 t_\\text{rel}}{\\eta_1} + \\frac{\\sigma_0}{G_2}\\!\\left(1-e^{-t_\\text{rel}/\\tau_2}\\right)e^{-(t-t_\\text{rel})/\\tau_2}$$
      <p>where $\\tau_2 = \\eta_2/G_2$ is the retardation time. The transition window around $t_\\text{release}$ is pruned automatically to remove instrument oscillation artefacts. Use <em>Exclude time ranges</em> in the Parameters panel to remove additional non-equilibrium data (e.g. the initial loading ramp).</p>`,

    'Regression Parameters': `<p>Fitted parameters from the Burgers (and optional Maxwell / Kelvin–Voigt) model. $R^2$ is evaluated on the data used for fitting (after pruning and exclusions).</p>`,
    
    'Recovery Components (Burgers)': `
      <p>Total deformation at $t = t_\\text{release}$ is partitioned into three fractions:</p>
      $$f_\\text{elastic} = \\frac{\\sigma_0/G_1}{\\varepsilon_\\text{total}}, \\quad
        f_\\text{viscoelastic} = \\frac{(\\sigma_0/G_2)(1-e^{-t_\\text{rel}/\\tau_2})}{\\varepsilon_\\text{total}}, \\quad
        f_\\text{plastic} = \\frac{\\sigma_0 t_\\text{rel}/\\eta_1}{\\varepsilon_\\text{total}}$$
      <p>The <strong>elastic</strong> ($f_\\text{el}$) and <strong>viscoelastic</strong> ($f_\\text{ve}$) components are recovered after stress release; the <strong>plastic</strong> component ($f_\\text{pl}$) is permanent deformation. A purely elastic material gives $f_\\text{el}=1$; an ideal viscous fluid gives $f_\\text{pl}=1$.</p>`,

    'Component Table':       `<p>Mean and standard deviation of elastic, viscoelastic, and plastic fractions across all selected replicates.</p>`,
  },

  amplitude_sweep: {
    'Amplitude Sweep': `
      <p>A strain amplitude sweep measures the storage modulus $G'$ (elastic, in-phase) and loss modulus $G''$ (viscous, out-of-phase) as a function of shear strain $\\gamma$.</p>
      <p>The <strong>linear viscoelastic region (LVER)</strong> is the strain range over which $G'$ remains within the set deviation threshold of its plateau value $G'_0$:</p>
      $$\\gamma_c : \\left|\\frac{G'(\\gamma_c) - G'_0}{G'_0}\\right| > \\delta$$
      <p>Below $\\gamma_c$ the microstructure is intact; above $\\gamma_c$ it begins to break down. The loss tangent $\\tan\\delta = G''/G'$ equals 1 at the sol–gel transition.</p>`,

    'LVER Results': `<p>Plateau modulus $G'_0$ (mean of the first <em>N</em> plateau points), critical strain $\\gamma_c$, and corresponding $G'(\\gamma_c)$ and $G''(\\gamma_c)$ for each sample.</p>`,
  },

  stress_relaxation: {
    'Stress Relaxation Fits': `
      <p>Under a constant imposed strain $\\varepsilon_0$, the stress decays as the material relaxes. The <strong>Burgers relaxation model</strong> solves the differential constitutive equation, yielding a bi-exponential response:</p>
      $$\\sigma(t) = \\varepsilon_0 \\left(A_1\\,e^{-t/\\tau_1} + A_2\\,e^{-t/\\tau_2}\\right)$$
      <p>where relaxation times $\\tau_{1,2} = 1/r_{1,2}$ are eigenvalues of the mechanical network ($r_{1,2} = (p_1 \\mp \\sqrt{p_1^2-4p_2})/(2p_2)$, $p_1 = \\eta_1/E_1 + \\eta_1/E_2 + \\eta_2/E_2$, $p_2 = \\eta_1\\eta_2/(E_1 E_2)$).</p>
      <p>The simpler <strong>Maxwell model</strong> predicts single-exponential decay: $\\sigma(t) = E\\varepsilon_0\\,e^{-t/\\tau}$, $\\;\\tau = \\eta/E$.</p>
      <p><strong>Tip:</strong> Data recorded during the initial strain ramp (before quasi-static conditions are reached) should be excluded using the <em>Exclude time ranges</em> filter in the Parameters panel.</p>`,

    'Regression Parameters': `<p>Fitted model parameters and $R^2$ for each sample, evaluated on the filtered dataset.</p>`,
  },

  frequency_sweep: {
    "G' and G''": `
      <p>A frequency sweep measures $G'(\\omega)$ and $G''(\\omega)$ over a range of angular frequencies $\\omega$, characterising the frequency-dependent viscoelastic behaviour.</p>
      <p><strong>Power-law (Winter–Chambon) fit:</strong> $G'(\\omega) = a\\,\\omega^n$</p>
      <ul>
        <li>$n \\to 0$: frequency-independent — ideal elastic gel</li>
        <li>$n = 1$: Maxwell-fluid behaviour ($G' \\propto \\omega^2$, $G'' \\propto \\omega$)</li>
        <li>$n = 0.5$: gel-point signature (loss tangent is frequency-independent)</li>
      </ul>
      <p>The <strong>gel point</strong> is identified as the frequency where $G'(\\omega^*) = G''(\\omega^*)$.</p>`,

    "tan(δ)": `<p>The loss tangent $\\tan\\delta = G''/G'$ indicates the ratio of energy dissipated to energy stored per cycle. $\\tan\\delta < 1$ indicates gel-like (elastic-dominant) behaviour; $\\tan\\delta > 1$ indicates liquid-like (viscous-dominant) behaviour.</p>`,
    "|η*|":   `<p>The complex viscosity $|\\eta^*| = |G^*|/\\omega = \\sqrt{G'^2+G''^2}/\\omega$ is related to steady-shear viscosity via the Cox–Merz rule: $\\eta(\\dot\\gamma) \\approx |\\eta^*(\\omega)|$ evaluated at $\\dot\\gamma = \\omega$.</p>`,
    'Cole-Cole': `<p>The Cole–Cole plot ($G''$ vs $G'$) reveals the distribution of relaxation times. A single Maxwell element produces a semicircle; a broadened arc indicates a wide relaxation spectrum characteristic of polymer networks.</p>`,
  },

  temperature_sweep: {
    "G' and G''": `
      <p>A temperature sweep tracks $G'(T)$ and $G''(T)$ during heating or cooling, capturing the <strong>sol–gel transition</strong>.</p>
      <p>The gel point $T_\\text{gel}$ is detected at the crossover:</p>
      $$G'(T_\\text{gel}) = G''(T_\\text{gel}) \\quad\\Longleftrightarrow\\quad \\tan\\delta(T_\\text{gel}) = 1$$
      <ul>
        <li>$T < T_\\text{gel}$ (sol): $G'' > G'$ — liquid-like, viscous-dominant</li>
        <li>$T > T_\\text{gel}$ (gel): $G' > G''$ — elastic-dominant, network formed</li>
      </ul>
      <p>$T_\\text{gel}$ is estimated by linear interpolation between the two points bracketing the crossover.</p>`,

    "tan(δ)": `<p>$\\tan\\delta = G''/G'$. The horizontal line at $\\tan\\delta = 1$ marks the gel point. A sharp drop from $>1$ to $<1$ indicates a well-defined gelation transition.</p>`,
  },
};

// Reverse-map display names → DESCRIPTIONS keys (used for "auto" mode labels)
const LABEL_TO_KEY = {
  'Creep Recovery': 'creep_recovery',
  'Amplitude Sweep': 'amplitude_sweep',
  'Stress Relaxation': 'stress_relaxation',
  'Frequency Sweep': 'frequency_sweep',
  'Temperature Sweep': 'temperature_sweep',
};

// ===== State =====
const state = {
  file: null,
  sheets: {},              // { sheetName: { columns, n_rows, intervals, test_type, units, sample_data } }
  selectedSheets: new Set(),
  intervalSelections: {},  // { sheetName: Set([0,1,2,...]) }
  sheetTestTypes: {},      // { sheetName: "frequency_sweep" }
  lastResponse: null,
  hasRun: false,           // true after first successful analysis run
  creepPreviewFig: null,   // saved rawplot figure for creep_recovery (persists across Run Analysis)
};

// Debounce timer for auto re-run after slider change
let _rerunTimer = null;
function scheduleRerun() {
  clearTimeout(_rerunTimer);
  _rerunTimer = setTimeout(() => runAnalysis(), 700);
}

// Debounce timer for fast raw-data preview update
let _previewTimer = null;
function schedulePreviewUpdate() {
  clearTimeout(_previewTimer);
  _previewTimer = setTimeout(() => autoRunCreepPreview(), 400);
}

// ===== Axis scale state =====
const axisScale = { x: 'linear', y: 'linear' };

// ===== DOM refs =====
const dropZone          = document.getElementById('drop-zone');
const fileInput         = document.getElementById('file-input');
const fileInfo          = document.getElementById('file-info');
const sheetCard         = document.getElementById('sheet-card');
const sheetList         = document.getElementById('sheet-list');
const testTypeSelect    = document.getElementById('test-type-select');
const paramsCard        = document.getElementById('params-card');
const paramsBody        = document.getElementById('params-body');
const runSection        = document.getElementById('run-section');
const runBtn            = document.getElementById('run-btn');
const previewBtn        = document.getElementById('preview-btn');
const dlExcelBtn        = document.getElementById('dl-excel-btn');
const dlCsvBtn          = document.getElementById('dl-csv-btn');
const welcomeState      = document.getElementById('welcome-state');
const loadingState      = document.getElementById('loading-state');
const loadingMsg        = document.getElementById('loading-msg');
const errorState        = document.getElementById('error-state');
const errorMsg          = document.getElementById('error-msg');
const previewState      = document.getElementById('preview-state');
const previewContent    = document.getElementById('preview-content');
const previewSheetSel   = document.getElementById('preview-sheet-select');
const plotSection       = document.getElementById('plot-section');
const plotTabs          = document.getElementById('plot-tabs');
const plotTabContent    = document.getElementById('plot-tab-content');
const customPlotCard    = document.getElementById('custom-plot-card');
const customPlotHeader  = document.getElementById('custom-plot-header');
const customPlotChevron = document.getElementById('custom-plot-chevron');
const customPlotBody    = document.getElementById('custom-plot-body');
const cpXCol            = document.getElementById('cp-x-col');
const cpYCols           = document.getElementById('cp-y-cols');
const cpMode            = document.getElementById('cp-mode');
const cpRunBtn          = document.getElementById('cp-run-btn');
const descAccordion        = document.getElementById('desc-accordion');
const descContent          = document.getElementById('desc-content');
const inferredParamsCard   = document.getElementById('inferred-params-card');
const inferredParamsBody   = document.getElementById('inferred-params-body');

// ===== Upload / Drag-Drop =====
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});
fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });

async function handleFile(f) {
  if (!f.name.toLowerCase().match(/\.(xlsx|csv)$/)) {
    showError('Only .xlsx and .csv files are supported.');
    return;
  }
  state.file = f;
  showLoading('Parsing file…');

  const fd = new FormData();
  fd.append('file', f);

  try {
    const res = await fetch('/api/parse', { method: 'POST', body: fd });
    if (!res.ok) {
      let msg = 'Parse failed';
      try { const err = await res.json(); msg = err.detail || msg; } catch {}
      throw new Error(msg);
    }
    const data = await res.json();
    state.sheets = data.sheets;
    state.selectedSheets.clear();
    state.intervalSelections = {};
    state.sheetTestTypes = {};
    Object.keys(state.sheets).forEach(n => state.selectedSheets.add(n));

    dropZone.classList.add('loaded');
    fileInfo.innerHTML = `<i class="bi bi-check-circle text-success me-1"></i>
      <strong>${escHtml(f.name)}</strong> · ${data.file_size_kb} KB · ${Object.keys(data.sheets).length} sheet(s)`;

    renderSheetList();
    autoDetectTestType();
    renderParams();
    initCustomPlot();

    sheetCard.classList.remove('d-none');
    paramsCard.classList.remove('d-none');
    runSection.classList.remove('d-none');
    customPlotCard.classList.remove('d-none');

    hideLoading();
    if (testTypeSelect.value === 'creep_recovery') {
      showPreviewState();          // show data table immediately
      autoRunCreepPreview();       // async: switches to plot section when ready
    } else {
      showPreviewState();
    }
  } catch (e) {
    showError(e.message);
  }
}

// ===== Sheet name parsing =====
function parseSheetName(name) {
  // If the backend provided Project:::Test
  const parts = name.split(':::');
  if (parts.length >= 2) {
    return { material: parts[0], replicate: parts[1] };
  }

  // Fallback heuristic: <material>_<replicate> where replicate = s1, s2, rep1, r1, etc.
  const m = name.match(/^(.+?)_((?:s|rep?)\d+)$/i);
  if (m) return { material: m[1], replicate: m[2] };
  return { material: name, replicate: null };
}

// ===== Sheet list (3-level: material → replicate → segment) =====
function renderSheetList() {
  sheetList.innerHTML = '';

  // Init interval selections
  Object.entries(state.sheets).forEach(([name, info]) => {
    if (!state.intervalSelections[name]) {
      state.intervalSelections[name] = new Set((info.intervals || []).map(iv => iv.index));
    }
  });

  // Group by material
  const matGroups = {}; // material → [name, ...]
  Object.keys(state.sheets).forEach(name => {
    const { material } = parseSheetName(name);
    (matGroups[material] = matGroups[material] || []).push(name);
  });

  const _setCheckedState = (cb, checked, indeterminate) => {
    cb.checked = checked;
    cb.indeterminate = indeterminate;
  };

  const _updateMatCb = (matCb, sheetNames) => {
    const sel = sheetNames.filter(n => state.selectedSheets.has(n)).length;
    _setCheckedState(matCb, sel > 0, sel > 0 && sel < sheetNames.length);
  };

  const _updateSheetCb = (sheetCb, name) => {
    const ivCbs = sheetList.querySelectorAll(`.iv-cb[data-sheet="${CSS.escape(name)}"]`);
    if (!ivCbs.length) return;
    const n = [...ivCbs].filter(c => c.checked).length;
    _setCheckedState(sheetCb, n > 0, n > 0 && n < ivCbs.length);
  };

  Object.entries(matGroups).forEach(([material, sheetNames]) => {
    const hasReplicates = sheetNames.length > 1 || parseSheetName(sheetNames[0]).replicate;
    const matDiv = document.createElement('div');
    matDiv.className = 'material-group';

    const matSheetsId = `mat-sheets-${material.replace(/[^a-z0-9]/gi,'_')}`;
    matDiv.innerHTML = `
      <div class="material-header">
        <input type="checkbox" class="form-check-input mat-cb" style="flex-shrink:0;">
        <span class="flex-grow-1 text-truncate" title="${escHtml(material)}">${escHtml(material)}</span>
        ${hasReplicates
          ? `<button class="btn-expand mat-expand" title="Expand"><i class="bi bi-chevron-right"></i></button>`
          : ''}
      </div>
      <div class="material-sheets d-none" id="${matSheetsId}">
        ${sheetNames.map(name => {
          const info = state.sheets[name];
          const { replicate } = parseSheetName(name);
          const intervals = info.intervals || [];
          const hasSegs = intervals.length > 1;
          const sheetLabel = replicate || escHtml(name);
          const sheetChecked = state.selectedSheets.has(name);
          return `
            <div class="sheet-item-group">
              <div class="sheet-item">
                <input type="checkbox" class="form-check-input sheet-cb" value="${escHtml(name)}"
                       ${sheetChecked ? 'checked' : ''}>
                <span class="flex-grow-1 small text-truncate" title="${escHtml(name)}">${escHtml(sheetLabel)}</span>
                <small class="text-muted" style="font-size:0.68rem;">${hasSegs ? intervals.length+' segments' : info.n_rows+' pts'}</small>
                ${hasSegs ? `<button class="btn-expand" title="Toggle intervals"><i class="bi bi-chevron-${hasSegs ? 'down' : 'right'}"></i></button>` : ''}
              </div>
              ${hasSegs ? `<div class="interval-list ${hasSegs ? '' : 'd-none'}">
                ${intervals.map(iv => {
                  const tLabel = iv.t_start != null ? `${iv.t_start}–${iv.t_end}s` : '';
                  const chk = state.intervalSelections[name].has(iv.index) ? 'checked' : '';
                  const phLabel = segPhaseLabel(info.test_type || testTypeSelect.value, iv.index, intervals.length);
                  return `<label class="interval-item">
                    <input type="checkbox" class="form-check-input iv-cb"
                           data-sheet="${escHtml(name)}" data-idx="${iv.index}" ${chk}>
                    <span>${escHtml(phLabel)}</span>
                    <span class="text-muted ms-auto" style="font-size:0.68rem; min-width:65px; text-align:right;">${tLabel}</span>
                  </label>`;
                }).join('')}
              </div>` : ''}
            </div>`;
        }).join('')}
      </div>`;

    sheetList.appendChild(matDiv);

    const matCb    = matDiv.querySelector('.mat-cb');
    const matPanel = matDiv.querySelector('.material-sheets');
    const matBtn   = matDiv.querySelector('.mat-expand');

    // Set initial mat checkbox state
    _updateMatCb(matCb, sheetNames);

    // Expand/collapse material group
    if (matBtn) {
      matBtn.addEventListener('click', () => {
        const open = !matPanel.classList.contains('d-none');
        matPanel.classList.toggle('d-none', open);
        matBtn.querySelector('i').className = open ? 'bi bi-chevron-right' : 'bi bi-chevron-down';
      });
      // Auto-expand if any replicate is selected
      if (sheetNames.some(n => state.selectedSheets.has(n))) {
        matPanel.classList.remove('d-none');
        matBtn.querySelector('i').className = 'bi bi-chevron-down';
      }
    } else {
      matPanel.classList.remove('d-none'); // single entry always visible
    }

    // mat-cb → all sheets + all ivs
    matCb.addEventListener('change', () => {
      sheetNames.forEach(name => {
        const info = state.sheets[name];
        const sheetCb = matDiv.querySelector(`.sheet-cb[value="${CSS.escape(name)}"]`);
        if (matCb.checked) {
          state.selectedSheets.add(name);
          const allIdxs = (info?.intervals || []).map(iv => iv.index);
          state.intervalSelections[name] = new Set(allIdxs);
          matDiv.querySelectorAll(`.iv-cb[data-sheet="${CSS.escape(name)}"]`).forEach(c => { c.checked = true; });
          if (sheetCb) _setCheckedState(sheetCb, true, false);
        } else {
          state.selectedSheets.delete(name);
          state.intervalSelections[name] = new Set();
          matDiv.querySelectorAll(`.iv-cb[data-sheet="${CSS.escape(name)}"]`).forEach(c => { c.checked = false; });
          if (sheetCb) _setCheckedState(sheetCb, false, false);
        }
      });
      _initSegmentSliders(); initCustomPlot(); renderInferredParams(); _updatePruneLabels();
      schedulePreviewUpdate();
      if (state.hasRun) scheduleRerun();
    });

    // sheet-cb → its ivs + update mat-cb
    matDiv.querySelectorAll('.sheet-cb').forEach(cb => {
      cb.addEventListener('change', () => {
        const name = cb.value;
        const info = state.sheets[name];
        if (cb.checked) {
          state.selectedSheets.add(name);
          const allIdxs = (info?.intervals || []).map(iv => iv.index);
          state.intervalSelections[name] = new Set(allIdxs);
          matDiv.querySelectorAll(`.iv-cb[data-sheet="${CSS.escape(name)}"]`).forEach(c => { c.checked = true; });
        } else {
          state.selectedSheets.delete(name);
          state.intervalSelections[name] = new Set();
          matDiv.querySelectorAll(`.iv-cb[data-sheet="${CSS.escape(name)}"]`).forEach(c => { c.checked = false; });
        }
        _updateMatCb(matCb, sheetNames);
        _initSegmentSliders(); initCustomPlot(); renderInferredParams(); _updatePruneLabels();
        schedulePreviewUpdate();
        if (state.hasRun) scheduleRerun();
      });
    });

    // iv-cb → update sheet-cb + mat-cb
    matDiv.querySelectorAll('.iv-cb').forEach(cb => {
      cb.addEventListener('change', () => {
        const name = cb.dataset.sheet;
        const idx  = parseInt(cb.dataset.idx);
        if (!state.intervalSelections[name]) state.intervalSelections[name] = new Set();
        if (cb.checked) state.intervalSelections[name].add(idx);
        else             state.intervalSelections[name].delete(idx);
        // Update whether sheet is "selected" (any iv checked)
        const anyIv = state.intervalSelections[name].size > 0;
        if (anyIv) state.selectedSheets.add(name);
        else        state.selectedSheets.delete(name);
        const sheetCb = matDiv.querySelector(`.sheet-cb[value="${CSS.escape(name)}"]`);
        if (sheetCb) _updateSheetCb(sheetCb, name);
        _updateMatCb(matCb, sheetNames);
        _initSegmentSliders(); renderInferredParams(); _updatePruneLabels();
        schedulePreviewUpdate();
        if (state.hasRun) scheduleRerun();
      });
    });

    // Expand/collapse individual replicate segments
    matDiv.querySelectorAll('.btn-expand:not(.mat-expand)').forEach(btn => {
      btn.addEventListener('click', () => {
        const ivList = btn.closest('.sheet-item-group').querySelector('.interval-list');
        if (!ivList) return;
        const open = !ivList.classList.contains('d-none');
        ivList.classList.toggle('d-none', open);
        btn.querySelector('i').className = open ? 'bi bi-chevron-right' : 'bi bi-chevron-down';
      });
    });
  });
}

// Label a segment as Creep / Recovery / Seg N
function segPhaseLabel(testType, segIndex, totalSegs = 0) {
  if (testType === 'creep_recovery') {
    if (totalSegs === 2) {
      if (segIndex === 0) return 'Creep phase';
      if (segIndex === 1) return 'Recovery phase';
    } else if (totalSegs > 2) {
      // Often Interval 1 is pre-conditioning, 2 is creep, 3 is recovery
      if (segIndex === 0) return 'Pre-conditioning';
      if (segIndex === 1) return 'Creep phase';
      if (segIndex === 2) return 'Recovery phase';
    }
  }
  return `Segment ${segIndex + 1}`;
}

function testTypeBadge(tt) {
  const map = {
    creep_recovery:    'bg-primary',
    amplitude_sweep:   'bg-success',
    stress_relaxation: 'bg-warning text-dark',
    frequency_sweep:   'bg-info text-dark',
    temperature_sweep: 'bg-danger',
    unknown:           'bg-secondary',
  };
  return map[tt] || 'bg-secondary';
}

function collectIntervalSelections() {
  const result = {};
  for (const [name, sel] of Object.entries(state.intervalSelections)) {
    result[name] = [...sel];
  }
  return result;
}

// ===== Auto-detect test type =====
function autoDetectTestType() {
  const types = Object.values(state.sheets).map(s => s.test_type).filter(t => t !== 'unknown');
  if (types.length === 0) return;
  // Pick the most common detected type
  const counts = {};
  types.forEach(t => { counts[t] = (counts[t] || 0) + 1; });
  const best = Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
  testTypeSelect.value = best;
}

testTypeSelect.addEventListener('change', () => {
  renderParams();
  if (state.hasRun) scheduleRerun();
});

// Compute data time range from selected sheets
function getSelectedTimeRange() {
  let t_min = Infinity, t_max = -Infinity;
  for (const name of state.selectedSheets) {
    const info = state.sheets[name];
    if (!info) continue;
    const selIvs = state.intervalSelections[name] ||
                   new Set((info.intervals || []).map(iv => iv.index));
    for (const iv of (info.intervals || [])) {
      if (!selIvs.has(iv.index)) continue;
      if (iv.t_start != null) t_min = Math.min(t_min, iv.t_start);
      if (iv.t_end   != null) t_max = Math.max(t_max, iv.t_end);
    }
  }
  return {
    t_min: isFinite(t_min) ? t_min : 0,
    t_max: isFinite(t_max) ? t_max : 300,
  };
}

// Get per-segment time info in combined time space
// (segments are always combined: t of seg N is offset by sum of max(t) of previous segs)
function getSelectedSegments() {
  const firstName = [...state.selectedSheets][0];
  const info = firstName ? state.sheets[firstName] : null;
  if (!info) {
    const { t_min, t_max } = getSelectedTimeRange();
    return [{ label: 'Data', id: 'slider_all', t_start: t_min, t_end: t_max }];
  }
  const allIvs = info.intervals || [];
  const selSet = state.intervalSelections[firstName] ||
                 new Set(allIvs.map(iv => iv.index));
  const selIvs = allIvs.filter(iv => selSet.has(iv.index));
  if (selIvs.length === 0) {
    const { t_min, t_max } = getSelectedTimeRange();
    return [{ label: firstName, id: 'slider_all', t_start: t_min, t_end: t_max }];
  }
  const segments = [];
  let offset = 0;
  for (const iv of selIvs) {
    const rawStart = iv.t_start ?? 0;
    const rawEnd   = iv.t_end   ?? rawStart + 300;
    let t_start, t_end;
    if (rawStart > offset + 1.0) {
      // Gap split: times are already absolute (no reset, just a time gap)
      t_start = rawStart;
      t_end   = rawEnd;
      offset  = rawEnd;
    } else {
      // Reset split: segments start near zero, add cumulative offset
      t_start = rawStart + offset;
      t_end   = rawEnd   + offset;
      offset += rawEnd;
    }
    const label = selIvs.length > 1
      ? segPhaseLabel(info.test_type || testTypeSelect.value, iv.index)
      : 'Data';
    const id = `slider_seg${iv.index}`;
    segments.push({ label, id, t_start, t_end });
  }
  return segments;
}

// Build fitting-window HTML (just containers — sliders are init'd after DOM insert)
function fitWindowUI(tt) {
  return `
    <div class="param-group border-top pt-2 mt-2" id="fit-window-group">
      <label class="fw-semibold d-block mb-1">
        <i class="bi bi-sliders me-1"></i>Fitting window
        <small class="text-muted fw-normal ms-1">drag handles to keep/exclude data</small>
      </label>
      <div id="segment-sliders-container"></div>
      <small class="text-muted mt-1 d-block">
        Shaded regions excluded from fit. Updates automatically.
      </small>
    </div>`;
}

// ===== Parameter panels =====
function renderParams() {
  const tt = testTypeSelect.value;
  paramsBody.innerHTML = '';

  if (tt === 'creep_recovery') {
    paramsBody.innerHTML = `
      <div class="param-group mb-2">
        <label>Stress release time t<sub>release</sub> (s)
          <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
             title="Time at which the applied stress is removed and recovery begins. Leave blank to auto-detect from the strain peak (maximum strain)."></i>
        </label>
        <div class="input-group input-group-sm">
          <input type="number" class="form-control" id="p-t-release" placeholder="auto" min="0" step="1">
          <span class="input-group-text text-muted" style="font-size:0.75rem;">blank = auto</span>
        </div>
      </div>

      <div class="param-group mb-2 border-top pt-2">
        <label class="fw-semibold d-block mb-2">
          <i class="bi bi-scissors me-1"></i>Pruning
          <small class="text-muted fw-normal ms-1">by data-point index</small>
        </label>

        <div class="mb-3">
          <label class="small mb-1 d-block">Zone 1 — Exclude initial points
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Number of data points to remove from the very start of the time series (initial loading transient). The label shows the time of the last excluded point in the reference sheet."></i>
          </label>
          <div class="d-flex align-items-center gap-2">
            <input type="range" class="form-range flex-grow-1" id="p-prune-start-n"
                   min="0" max="50" step="1" value="33">
            <span id="p-prune-start-label" class="text-muted small text-nowrap"
                  style="min-width:120px;font-variant-numeric:tabular-nums;"></span>
          </div>
        </div>

        <div>
          <label class="small mb-1 d-block">Zone 2 — Exclude points after t<sub>release</sub>
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Number of data points to remove right after stress release (oscillation artefact). The label shows the time of the last excluded point in the reference sheet."></i>
          </label>
          <div class="d-flex align-items-center gap-2">
            <input type="range" class="form-range flex-grow-1" id="p-prune-release-n"
                   min="0" max="150" step="1" value="65">
            <span id="p-prune-release-label" class="text-muted small text-nowrap"
                  style="min-width:120px;font-variant-numeric:tabular-nums;"></span>
          </div>
        </div>
      </div>

      <div class="param-group mb-2">
        <div class="form-check form-check-sm">
          <input class="form-check-input" type="checkbox" id="p-maxwell">
          <label class="form-check-label" for="p-maxwell">Include Maxwell model
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Fit a 2-element Maxwell model (spring + dashpot in series) in addition to Burgers. Single exponential creep; cannot describe retarded elastic response."></i>
          </label>
        </div>
        <div class="form-check form-check-sm mt-1">
          <input class="form-check-input" type="checkbox" id="p-kelvin">
          <label class="form-check-label" for="p-kelvin">Include Kelvin-Voigt model
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Fit a Kelvin-Voigt model (spring + dashpot in parallel). Predicts complete elastic recovery; no permanent (plastic) deformation."></i>
          </label>
        </div>
        <div class="form-check form-check-sm mt-1">
          <input class="form-check-input" type="checkbox" id="p-overlay">
          <label class="form-check-label" for="p-overlay">Overlay all samples in one plot
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Show all selected samples on the same axes for direct comparison, each in a distinct colour."></i>
          </label>
        </div>
      </div>`;
  } else if (tt === 'amplitude_sweep') {
    paramsBody.innerHTML = `
      <div class="param-group mb-2">
        <label>Plateau points (first N)
          <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
             title="Number of low-strain data points used to compute the plateau modulus G'₀. Should cover the flat linear region at small strains."></i>
        </label>
        <input type="number" class="form-control form-control-sm" id="p-plateau" value="5" min="2" step="1">
      </div>
      <div class="param-group">
        <label>Deviation threshold
          <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
             title="LVER ends when G' deviates from G'₀ by more than this percentage. Standard value: 5%. Higher values → wider LVER."></i>
        </label>
        <div class="input-group input-group-sm">
          <input type="number" class="form-control" id="p-deviation" value="5" min="1" max="50" step="1">
          <span class="input-group-text">%</span>
        </div>
      </div>`;
  } else if (tt === 'stress_relaxation') {
    paramsBody.innerHTML = `
      <div class="param-group mb-2">
        <div class="form-check form-check-sm">
          <input class="form-check-input" type="checkbox" id="p-maxwell">
          <label class="form-check-label" for="p-maxwell">Include Maxwell model
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Single-exponential decay: σ(t) = Eε₀ exp(−t/τ). Use as a reference for simple viscoelastic fluids."></i>
          </label>
        </div>
        <div class="form-check form-check-sm mt-1">
          <input class="form-check-input" type="checkbox" id="p-kelvin">
          <label class="form-check-label" for="p-kelvin">Include Kelvin-Voigt model
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Constant-stress prediction under strain control; acts as an elastic-only baseline."></i>
          </label>
        </div>
        <div class="form-check form-check-sm mt-1">
          <input class="form-check-input" type="checkbox" id="p-overlay">
          <label class="form-check-label" for="p-overlay">Overlay all samples in one plot
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Show all selected samples on the same axes for direct comparison."></i>
          </label>
        </div>
      </div>
      ${fitWindowUI(tt)}`;
  } else if (tt === 'frequency_sweep') {
    paramsBody.innerHTML = `
      <div class="param-group">
        <div class="form-check form-check-sm">
          <input class="form-check-input" type="checkbox" id="p-tan-delta" checked>
          <label class="form-check-label" for="p-tan-delta">Show tan(δ) plot
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Loss tangent tan δ = G''/G'. Values < 1 indicate gel-like behaviour; values > 1 indicate liquid-like behaviour."></i>
          </label>
        </div>
        <div class="form-check form-check-sm mt-1">
          <input class="form-check-input" type="checkbox" id="p-eta-star">
          <label class="form-check-label" for="p-eta-star">Show |η*| plot
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="Complex viscosity |η*| = |G*|/ω. Related to steady-shear viscosity via the Cox–Merz rule."></i>
          </label>
        </div>
        <div class="form-check form-check-sm mt-1">
          <input class="form-check-input" type="checkbox" id="p-cole-cole">
          <label class="form-check-label" for="p-cole-cole">Show Cole-Cole plot
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="G'' vs G' parametric plot. Reveals the distribution of relaxation times; a single Maxwell element gives a semicircle."></i>
          </label>
        </div>
      </div>`;
  } else if (tt === 'temperature_sweep') {
    paramsBody.innerHTML = `
      <div class="param-group">
        <div class="form-check form-check-sm">
          <input class="form-check-input" type="checkbox" id="p-tan-delta" checked>
          <label class="form-check-label" for="p-tan-delta">Show tan(δ) plot
            <i class="bi bi-info-circle text-muted ms-1" data-bs-toggle="tooltip"
               title="tan δ = G''/G'. Crosses 1 at the gel point T_gel where G' = G''."></i>
          </label>
        </div>
      </div>`;
  }

  // Show/hide inferred parameters for creep_recovery
  renderInferredParams();

  // Init point-based prune sliders (creep_recovery only)
  if (tt === 'creep_recovery') _initPruneSliders();

  // Wire up fitting-window sliders if present (stress_relaxation)
  _attachSliderListeners();

  // Bootstrap tooltips on info icons
  paramsBody.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
    new bootstrap.Tooltip(el, { trigger: 'hover', placement: 'right', html: false });
  });

  // Auto-rerun when any parameter control changes (after first run)
  paramsBody.querySelectorAll('input, select').forEach(el => {
    const evts = el.type === 'range' ? [] : ['change']; // sliders handled by noUiSlider
    evts.forEach(evt => el.addEventListener(evt, () => {
      if (state.hasRun) scheduleRerun();
    }));
  });
}

const PRUNE_WIN_S = 5; // seconds: slider covers only the first/last N seconds of each segment

function _initSegmentSliders() {
  const container = document.getElementById('segment-sliders-container');
  if (!container) return;

  // Destroy old noUiSlider instances
  container.querySelectorAll('[data-nouislider]').forEach(el => {
    if (el.noUiSlider) el.noUiSlider.destroy();
  });
  container.innerHTML = '';

  const segs = getSelectedSegments();
  for (const seg of segs) {
    const dur = seg.t_end - seg.t_start;
    if (dur <= 0) continue;
    const win = Math.min(PRUNE_WIN_S, dur / 2 - 0.05);

    const wrap = document.createElement('div');
    wrap.className = 'seg-slider-wrap mb-3';
    wrap.innerHTML = `
      <div class="seg-slider-label mb-1">${escHtml(seg.label)}</div>
      <div class="d-flex gap-3">
        <div class="flex-grow-1">
          <div class="d-flex justify-content-between" style="font-size:0.68rem;color:#6c757d;">
            <span>▶ Start prune</span>
            <span id="${seg.id}-s-disp" class="seg-slider-val">none</span>
          </div>
          <div id="${seg.id}-s" data-nouislider class="mt-1 mx-1"></div>
        </div>
        <div class="flex-grow-1">
          <div class="d-flex justify-content-between" style="font-size:0.68rem;color:#6c757d;">
            <span>End prune ◀</span>
            <span id="${seg.id}-e-disp" class="seg-slider-val">none</span>
          </div>
          <div id="${seg.id}-e" data-nouislider class="mt-1 mx-1"></div>
        </div>
      </div>`;
    container.appendChild(wrap);

    // Start-prune slider: moves right to cut more from the beginning
    const startEl = wrap.querySelector(`#${seg.id}-s`);
    noUiSlider.create(startEl, {
      start: seg.t_start,
      range: { min: seg.t_start, max: seg.t_start + win },
      step: 0.1,
      tooltips: { to: v => parseFloat(v).toFixed(1) + ' s', from: Number },
    });
    startEl.noUiSlider.on('update', values => {
      const trimmed = parseFloat(values[0]) - seg.t_start;
      document.getElementById(`${seg.id}-s-disp`).textContent =
        trimmed < 0.05 ? 'none' : `${trimmed.toFixed(1)} s`;
      updateFitPlotExclusionZones();
      if (state.hasRun) scheduleRerun();
    });

    // End-prune slider: moves left to cut more from the end
    const endEl = wrap.querySelector(`#${seg.id}-e`);
    noUiSlider.create(endEl, {
      start: seg.t_end,
      range: { min: seg.t_end - win, max: seg.t_end },
      step: 0.1,
      tooltips: { to: v => parseFloat(v).toFixed(1) + ' s', from: Number },
    });
    endEl.noUiSlider.on('update', values => {
      const trimmed = seg.t_end - parseFloat(values[0]);
      document.getElementById(`${seg.id}-e-disp`).textContent =
        trimmed < 0.05 ? 'none' : `${trimmed.toFixed(1)} s`;
      updateFitPlotExclusionZones();
      if (state.hasRun) scheduleRerun();
    });
  }

  // Transition-zone slider: one per consecutive segment pair
  // Lets user exclude the spike / oscillation artefacts around t_release
  const TZ_WIN = 40; // seconds of range on each side of the gap
  const TZ_DEF = 5;  // default exclusion on each side
  for (let i = 0; i < segs.length - 1; i++) {
    const s1 = segs[i], s2 = segs[i + 1];
    const rangeMin  = s1.t_end - TZ_WIN;
    const rangeMax  = s2.t_start + TZ_WIN;
    if (rangeMax <= rangeMin) continue;
    const defLo = Math.max(rangeMin, s1.t_end - TZ_DEF);
    const defHi = Math.min(rangeMax, s2.t_start + TZ_DEF);
    const tzId  = `slider_tz_${i}`;

    const div = document.createElement('div');
    div.className = 'seg-slider-wrap mb-3 pt-2';
    div.style.borderTop = '2px dashed #fd7e14';
    div.innerHTML = `
      <div class="seg-slider-label mb-1" style="color:#e85d04;">
        <i class="bi bi-lightning-charge-fill me-1"></i>
        Around t<sub>release</sub>
        <small class="fw-normal text-muted ms-1">(${s1.t_end.toFixed(0)}–${s2.t_start.toFixed(0)} s gap)</small>
      </div>
      <div class="d-flex justify-content-between" style="font-size:0.68rem;color:#6c757d;">
        <span>Excluded region</span>
        <span id="${tzId}-disp" class="seg-slider-val">${defLo.toFixed(1)} – ${defHi.toFixed(1)} s</span>
      </div>
      <div id="${tzId}" data-nouislider class="mt-1 mx-1"></div>`;
    container.appendChild(div);

    const tzEl = div.querySelector(`#${tzId}`);
    noUiSlider.create(tzEl, {
      start: [defLo, defHi],
      connect: [false, true, false],
      range: { min: rangeMin, max: rangeMax },
      step: 0.5,
      tooltips: [
        { to: v => parseFloat(v).toFixed(1) + ' s', from: Number },
        { to: v => parseFloat(v).toFixed(1) + ' s', from: Number },
      ],
    });
    tzEl.noUiSlider.on('update', values => {
      const lo = parseFloat(values[0]), hi = parseFloat(values[1]);
      document.getElementById(`${tzId}-disp`).textContent = `${lo.toFixed(1)} – ${hi.toFixed(1)} s`;
      updateFitPlotExclusionZones();
      if (state.hasRun) scheduleRerun();
    });
  }
}

function _attachSliderListeners() {
  _initSegmentSliders();
}

// Build exclude_ranges from per-segment and transition-zone sliders
function collectFitWindow() {
  const segs = getSelectedSegments();
  const ranges = [];

  // Per-segment start/end prune
  for (const seg of segs) {
    const startEl = document.getElementById(`${seg.id}-s`);
    const endEl   = document.getElementById(`${seg.id}-e`);
    if (startEl?.noUiSlider) {
      const lo = parseFloat(startEl.noUiSlider.get());
      if (lo > seg.t_start + 1e-4) ranges.push([seg.t_start, lo]);
    }
    if (endEl?.noUiSlider) {
      const hi = parseFloat(endEl.noUiSlider.get());
      if (hi < seg.t_end - 1e-4) ranges.push([hi, seg.t_end]);
    }
  }

  // Transition zone exclusion (around t_release)
  for (let i = 0; i < segs.length - 1; i++) {
    const tzEl = document.getElementById(`slider_tz_${i}`);
    if (tzEl?.noUiSlider) {
      const [lo, hi] = tzEl.noUiSlider.get().map(parseFloat);
      if (hi > lo + 0.1) ranges.push([lo, hi]);
    }
  }

  return ranges;
}

// Shade excluded zones on the fit plot
function updateFitPlotExclusionZones() {
  const el = document.getElementById('plot-div-fit-0');
  if (!el?._fullLayout) return;
  const ranges = collectFitWindow();
  const shapes = ranges.map(([lo, hi]) => ({
    type: 'rect', xref: 'x', yref: 'paper',
    x0: lo, x1: hi, y0: 0, y1: 1,
    fillcolor: 'rgba(120,120,120,0.15)', line: { width: 0 }, layer: 'below',
  }));
  Plotly.relayout(el, { shapes });
}

// ===== Collect params =====
function collectParams() {
  const tt = testTypeSelect.value;
  const p  = {};
  const val = id => { const el = document.getElementById(id); return el ? el.value : null; };
  const chk = id => { const el = document.getElementById(id); return el ? el.checked : false; };

  if (tt === 'creep_recovery') {
    const tRelRaw = val('p-t-release');
    p.t_release       = (tRelRaw && tRelRaw.trim() !== '') ? parseFloat(tRelRaw) : 'auto';
    p.prune_start_n   = parseInt(val('p-prune-start-n') || 0);
    p.prune_release_n = parseInt(val('p-prune-release-n') || 0);
    p.enable_maxwell  = chk('p-maxwell');
    p.enable_kelvin   = chk('p-kelvin');
    p.overlay         = chk('p-overlay');
    p.combine_segments = true;
  } else if (tt === 'amplitude_sweep') {
    p.plateau_points = parseInt(val('p-plateau') || 5);
    p.deviation      = parseFloat(val('p-deviation') || 5) / 100;
  } else if (tt === 'stress_relaxation') {
    p.enable_maxwell    = chk('p-maxwell');
    p.enable_kelvin     = chk('p-kelvin');
    p.overlay           = chk('p-overlay');
    p.combine_segments  = true;  // always combine segments
    p.exclude_ranges    = collectFitWindow();
  } else if (tt === 'frequency_sweep') {
    p.show_tan_delta = chk('p-tan-delta');
    p.show_eta_star  = chk('p-eta-star');
    p.show_cole_cole = chk('p-cole-cole');
  } else if (tt === 'temperature_sweep') {
    p.show_tan_delta = chk('p-tan-delta');
  }
  return p;
}

// ===== Data Preview =====
previewSheetSel.addEventListener('change', () => renderPreview(previewSheetSel.value));
previewBtn.addEventListener('click', showPreviewState);

function showPreviewState() {
  welcomeState.classList.add('d-none');
  errorState.classList.add('d-none');
  plotSection.classList.add('d-none');
  loadingState.classList.add('d-none');
  previewState.classList.remove('d-none');

  // Populate sheet selector
  previewSheetSel.innerHTML = Object.keys(state.sheets)
    .map(n => `<option value="${escHtml(n)}">${escHtml(n)}</option>`).join('');
  renderPreview(previewSheetSel.value);
}

/** Build the data-table HTML for a given sheet (shared between preview state and tab). */
function _buildPreviewHTML(sheetName) {
  const info = state.sheets[sheetName];
  if (!info) return '';

  const cols       = info.columns || [];
  const units      = info.units   || {};
  const sampleData = info.sample_data || [];
  const ivCount    = info.n_intervals || 1;

  const colPills = cols.map(c => {
    const u = units[c] ? ` <span class="text-muted">(${escHtml(units[c])})</span>` : '';
    return `<span class="badge bg-light text-dark border me-1 mb-1 fw-normal">${escHtml(c)}${u}</span>`;
  }).join('');

  const thCells  = cols.map(c => `<th class="text-nowrap small">${escHtml(c)}</th>`).join('');
  const unitRow  = `<tr class="table-secondary">${cols.map(c =>
    `<td class="text-muted small text-nowrap">${escHtml(units[c] || '—')}</td>`
  ).join('')}</tr>`;
  const dataRows = sampleData.map(row =>
    `<tr>${cols.map(c => {
      const v = row[c];
      if (v == null) return '<td class="text-muted">—</td>';
      const n = parseFloat(v);
      return `<td class="text-nowrap">${isNaN(n) ? escHtml(String(v)) : (Math.abs(n) >= 1000 || (Math.abs(n) < 0.01 && n !== 0) ? n.toExponential(3) : parseFloat(n.toPrecision(5)))}</td>`;
    }).join('')}</tr>`
  ).join('');

  return `
    <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
      <span class="badge ${testTypeBadge(info.test_type)} px-2 py-1">${escHtml(info.test_type.replace(/_/g,' '))}</span>
      <small class="text-muted">${info.n_rows} rows &middot; ${ivCount} segment(s) &middot; ${cols.length} columns</small>
    </div>
    <div class="mb-3 lh-lg">${colPills}</div>
    <div class="table-responsive preview-scroll">
      <table class="table table-sm table-bordered table-hover preview-table mb-1">
        <thead class="table-dark"><tr>${thCells}</tr></thead>
        <tbody class="table-group-divider">
          ${unitRow}
          ${dataRows}
        </tbody>
      </table>
    </div>
    <p class="text-muted small mt-1">
      <i class="bi bi-info-circle me-1"></i>${info.n_rows} row(s) · ${ivCount} segment(s).
    </p>`;
}

function renderPreview(sheetName) {
  previewContent.innerHTML = _buildPreviewHTML(sheetName);
}

// ===== Custom Plot =====
customPlotHeader.addEventListener('click', () => {
  const open = !customPlotBody.classList.contains('d-none');
  customPlotBody.classList.toggle('d-none', open);
  customPlotChevron.className = open ? 'bi bi-chevron-down' : 'bi bi-chevron-up';
});

cpRunBtn.addEventListener('click', runCustomPlot);

function initCustomPlot() {
  const selectedNames = [...state.selectedSheets];
  if (selectedNames.length === 0) return;

  // Gather union of all columns across selected sheets
  const allCols = [];
  const seen    = new Set();
  selectedNames.forEach(name => {
    (state.sheets[name]?.columns || []).forEach(c => {
      if (!seen.has(c)) { seen.add(c); allCols.push(c); }
    });
  });

  // X selector
  cpXCol.innerHTML = allCols
    .map(c => `<option value="${escHtml(c)}">${escHtml(c)}</option>`)
    .join('');

  // Y checkboxes — default-check all numeric-looking columns
  cpYCols.innerHTML = allCols.map((c, i) => `
    <label class="d-flex align-items-center gap-2 mb-1">
      <input type="checkbox" class="form-check-input cp-y-cb" value="${escHtml(c)}" ${i > 0 ? 'checked' : ''}>
      <span>${escHtml(c)}</span>
      ${state.sheets[selectedNames[0]]?.units?.[c]
        ? `<span class="text-muted ms-auto">${escHtml(state.sheets[selectedNames[0]].units[c])}</span>` : ''}
    </label>`).join('');
}

async function runCustomPlot() {
  if (!state.file || state.selectedSheets.size === 0) return;

  const xCol   = cpXCol.value;
  const yCols  = [...cpYCols.querySelectorAll('.cp-y-cb:checked')].map(cb => cb.value);
  const mode   = cpMode.value;

  if (!xCol || yCols.length === 0) {
    showError('Select an X column and at least one Y column.');
    return;
  }

  showLoading('Plotting…');

  const fd = new FormData();
  fd.append('file',               state.file);
  fd.append('sheet_names',        JSON.stringify([...state.selectedSheets]));
  fd.append('interval_selections',JSON.stringify(collectIntervalSelections()));
  fd.append('x_col',              xCol);
  fd.append('y_cols',             JSON.stringify(yCols));
  fd.append('mode',               mode);

  try {
    const res = await fetch('/api/rawplot', { method: 'POST', body: fd });
    if (!res.ok) {
      let msg = 'Plot failed';
      try { const err = await res.json(); msg = err.detail || msg; } catch {}
      throw new Error(msg);
    }
    const data = await res.json();
    hideLoading();
    addCustomPlotTab(data.figure, data.figure_label || 'Custom Plot');
  } catch (e) {
    showError(e.message);
  }
}

function addCustomPlotTab(fig, label) {
  // Remove old custom tab if it exists
  document.querySelectorAll('[data-custom-tab]').forEach(btn => {
    const pane = document.querySelector(btn.getAttribute('data-bs-target'));
    btn.closest('li')?.remove();
    pane?.remove();
  });

  const uid = Date.now();
  const id  = `tab-pane-custom-${uid}`;

  const li = document.createElement('li');
  li.className = 'nav-item';
  li.innerHTML = `<button class="nav-link" data-bs-toggle="tab" data-bs-target="#${id}"
    type="button" data-custom-tab="true">
    <i class="bi bi-scatter-chart me-1"></i>${escHtml(label)}
  </button>`;
  plotTabs.appendChild(li);

  const pane = document.createElement('div');
  pane.className = 'tab-pane fade';
  pane.id        = id;
  pane.innerHTML = `<div class="plot-container" id="plot-div-custom-${uid}"></div>`;
  plotTabContent.appendChild(pane);

  // Show this new tab
  const tabEl = li.querySelector('[data-bs-toggle="tab"]');
  new bootstrap.Tab(tabEl).show();

  if (plotSection.classList.contains('d-none')) showPlotSection(true);

  // Wait one tick for DOM then render
  setTimeout(() => {
    const el = document.getElementById(`plot-div-custom-${uid}`);
    if (!el) return;
    const cleanFig = JSON.parse(JSON.stringify(fig));
    Plotly.newPlot(el, cleanFig.data || [], cleanFig.layout || {}, {
      responsive: true,
      displayModeBar: true,
    });
    tabEl.addEventListener('shown.bs.tab', () => {
      Plotly.Plots.resize(el);
      applyAxisScale(el);
    });
  }, 50);
}


// ===== Description panel =====
function updateDescription(testType, figLabel) {
  const activePane = document.querySelector('#plot-tab-content .tab-pane.show.active');
  const activeId = activePane ? activePane.id : '';
  
  // Hide box for raw data tabs, manual analysis, or the Burgers component tab
  if (activeId === 'tab-pane-creep-ts' || activeId === 'tab-pane-creep-tbl' || 
      activeId === 'by-hand-tab-pane' || activeId === 'tab-pane-fit-2') {
    descAccordion.classList.add('d-none');
    return;
  }

  // Resolve type key — handle "auto" mode labels like "Creep Recovery — G' and G''"
  let typeKey  = testType;
  let labelKey = figLabel;
  if (testType === 'auto') {
    const sep = figLabel.indexOf(' — ');
    if (sep >= 0) {
      typeKey  = LABEL_TO_KEY[figLabel.substring(0, sep)] || typeKey;
      labelKey = figLabel.substring(sep + 3);
    }
  }

  const html = DESCRIPTIONS[typeKey]?.[labelKey] || '';
  if (!html) { descAccordion.classList.add('d-none'); return; }

  descAccordion.classList.remove('d-none');
  descContent.innerHTML = html;
  if (window.MathJax) MathJax.typesetPromise([descContent]).catch(console.error);
}

// ===== Inferred parameters display (creep_recovery) =====
// Reads from state.sheets (populated at parse time) — shown before the user runs analysis.
function renderInferredParams() {
  const tt = testTypeSelect.value;
  if (tt !== 'creep_recovery') {
    inferredParamsCard.classList.add('d-none');
    return;
  }

  const rows = [];
  for (const name of state.selectedSheets) {
    const info = state.sheets[name];
    if (!info || !info.inferred || Object.keys(info.inferred).length === 0) continue;
    const { sigma0, t_release } = info.inferred;
    rows.push({ sample: name, sigma0, t_release });
  }

  if (rows.length === 0) {
    inferredParamsCard.classList.add('d-none');
    return;
  }

  const tableRows = rows.map(r => {
    const sigma0Str = r.sigma0    != null ? Number(r.sigma0).toPrecision(4)       : '—';
    const tRelStr   = r.t_release != null ? Number(r.t_release).toFixed(1) + ' s' : '—';
    return `<tr>
      <td class="text-truncate" style="max-width:110px;" title="${escHtml(r.sample)}">${escHtml(r.sample)}</td>
      <td>${escHtml(sigma0Str)}</td>
      <td>${escHtml(tRelStr)}</td>
    </tr>`;
  }).join('');

  inferredParamsBody.innerHTML = `
    <table class="table table-sm table-borderless mb-0" style="font-size:0.78rem;">
      <thead class="table-light">
        <tr>
          <th>Sample</th>
          <th>σ₀ (Pa)</th>
          <th>t<sub>release</sub></th>
        </tr>
      </thead>
      <tbody>${tableRows}</tbody>
    </table>
    <p class="text-muted mb-0 mt-1" style="font-size:0.7rem;">
      <i class="bi bi-info-circle me-1"></i>
      σ₀ = median of first 10 Shear Stress points ·
      t<sub>release</sub> inferred from strain peak
    </p>`;

  inferredParamsCard.classList.remove('d-none');
}

// ===== Point-based prune sliders (creep_recovery) =====

/**
 * Return { allTimes, afterTimes } for the first selected creep_recovery sheet.
 * allTimes  : time values of all data points in the combined series
 * afterTimes: time values of points strictly after the inferred t_release
 */
function _getPruneTimes() {
  const firstName = [...state.selectedSheets].find(name => {
    const info = state.sheets[name];
    return info && info.inferred && Object.keys(info.inferred).length > 0;
  }) || [...state.selectedSheets][0];

  const info = firstName ? state.sheets[firstName] : null;
  const data = info?.sample_data || [];
  const t_release = info?.inferred?.t_release ?? null;

  const allTimes = data
    .map(r => r['Time'])
    .filter(v => v != null && isFinite(parseFloat(v)))
    .map(Number);

  const afterTimes = t_release != null
    ? allTimes.filter(t => t > t_release)
    : [];

  return { allTimes, afterTimes };
}

/** Format a slider position as "N pts (≤ X.X s)" using actual data-point times. */
function _pruneLabel(n, times) {
  if (n === 0) return '0 pts (none)';
  const lastT = n <= times.length ? times[n - 1] : (times.length > 0 ? times[times.length - 1] : null);
  const tStr = lastT != null ? ` (≤ ${lastT.toFixed(1)} s)` : '';
  return `${n} pt${n !== 1 ? 's' : ''}${tStr}`;
}

/** Update the label spans next to the two prune sliders. */
function _updatePruneLabels() {
  const startEl   = document.getElementById('p-prune-start-n');
  const releaseEl = document.getElementById('p-prune-release-n');
  if (!startEl && !releaseEl) return;

  const { allTimes, afterTimes } = _getPruneTimes();

  if (startEl) {
    const lbl = document.getElementById('p-prune-start-label');
    if (lbl) lbl.textContent = _pruneLabel(parseInt(startEl.value), allTimes);
  }
  if (releaseEl) {
    const lbl = document.getElementById('p-prune-release-label');
    if (lbl) lbl.textContent = _pruneLabel(parseInt(releaseEl.value), afterTimes);
  }
}

/** Wire event listeners on the two prune sliders (called from renderParams). */
function _initPruneSliders() {
  _updatePruneLabels();   // set initial labels

  ['p-prune-start-n', 'p-prune-release-n'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input', () => {
      _updatePruneLabels();
      updateCreepPreviewZones();   // live update shading on the preview plot
      if (state.hasRun) scheduleRerun();
    });
  });
}

// ===== Creep preview plot: interactive zones =====

/**
 * Overlay red-shaded rectangles on the Time Series preview plot to show
 * which data points will be excluded by the two prune sliders.
 * Called on slider input and after the plot is first rendered.
 */
function updateCreepPreviewZones() {
  const el = document.getElementById('plot-div-creep-ts');
  if (!el?._fullLayout) return;

  const startN   = parseInt(document.getElementById('p-prune-start-n')?.value  || 0);
  const releaseN = parseInt(document.getElementById('p-prune-release-n')?.value || 0);

  const { allTimes, afterTimes } = _getPruneTimes();
  const shapes = [];

  // Zone 1 — first startN data points
  if (startN > 0 && allTimes.length > 0) {
    const x0 = allTimes[0];
    const x1 = allTimes[Math.min(startN, allTimes.length) - 1];
    if (x1 >= x0) shapes.push({
      type: 'rect', xref: 'x', yref: 'paper',
      x0, x1, y0: 0, y1: 1,
      fillcolor: 'rgba(220,53,69,0.18)',
      line: { color: 'rgba(220,53,69,0.5)', width: 1 },
      layer: 'below',
      label: { text: 'Zone 1', textposition: 'top left', font: { color: 'rgba(220,53,69,0.9)', size: 11 } },
    });
  }

  // Zone 2 — first releaseN data points after t_release
  if (releaseN > 0 && afterTimes.length > 0) {
    const x0 = afterTimes[0];
    const x1 = afterTimes[Math.min(releaseN, afterTimes.length) - 1];
    if (x1 >= x0) shapes.push({
      type: 'rect', xref: 'x', yref: 'paper',
      x0, x1, y0: 0, y1: 1,
      fillcolor: 'rgba(220,53,69,0.18)',
      line: { color: 'rgba(220,53,69,0.5)', width: 1 },
      layer: 'below',
      label: { text: 'Zone 2', textposition: 'top left', font: { color: 'rgba(220,53,69,0.9)', size: 11 } },
    });
  }

  Plotly.relayout(el, { shapes });
}

// ===== Auto-generated Shear Strain vs Time preview (creep_recovery) =====

/**
 * Append the "Time Series" and "Data Table" preview tabs to plotTabs/plotTabContent.
 * active=true  → Time Series tab is visible and its plot is rendered immediately.
 * active=false → tabs are appended but not active; Time Series renders lazily on click.
 */
/**
 * Append creep preview tabs.
 * active    — whether the first appended tab is active.
 * tblFirst  — if true, appends Data Table then Time Series; otherwise the reverse.
 */
function _appendCreepPreviewTabs(activeId = null, tblFirst = false) {
  if (!state.creepPreviewFig) return;

  const sheetNames   = Object.keys(state.sheets);
  const defaultSheet = sheetNames[0] || '';

  // ── Time Series tab ──
  const _addTs = (tsActive) => {
    const tsId = 'tab-pane-creep-ts';
    const tsLi = document.createElement('li');
    tsLi.className = 'nav-item';
    tsLi.innerHTML = `<button class="nav-link${tsActive ? ' active' : ''}" data-bs-toggle="tab"
      data-bs-target="#${tsId}" type="button">
      <i class="bi bi-graph-up me-1"></i>Time Series
    </button>`;
    plotTabs.appendChild(tsLi);

    const tsPane = document.createElement('div');
    tsPane.className = `tab-pane${tsActive ? ' active' : ''}`;
    tsPane.id        = tsId;
    tsPane.innerHTML = `<div class="plot-wrapper"><div class="plot-container" id="plot-div-creep-ts"></div></div>`;
    plotTabContent.appendChild(tsPane);

    const _renderTsPlot = () => {
      const el = document.getElementById('plot-div-creep-ts');
      if (!el || el.dataset.rendered) return;
      el.dataset.rendered = '1';
      const fig = JSON.parse(JSON.stringify(state.creepPreviewFig));
      Plotly.newPlot(el, fig.data || [], fig.layout || {}, {
        responsive: true, displayModeBar: true,
      });
      setTimeout(() => updateCreepPreviewZones(), 80);
    };

    if (tsActive) setTimeout(_renderTsPlot, 50);

    tsLi.querySelector('button').addEventListener('shown.bs.tab', () => {
      _renderTsPlot();
      const el = document.getElementById('plot-div-creep-ts');
      if (el) Plotly.Plots.resize(el);
      updateCreepPreviewZones();
    });
  };

  // ── Data Table tab ──
  const _addTbl = (tblActive) => {
    const tblId = 'tab-pane-creep-tbl';
    const tblLi = document.createElement('li');
    tblLi.className = 'nav-item';
    tblLi.innerHTML = `<button class="nav-link${tblActive ? ' active' : ''}" data-bs-toggle="tab"
      data-bs-target="#${tblId}" type="button">
      <i class="bi bi-table me-1"></i>Data Table
    </button>`;
    plotTabs.appendChild(tblLi);

    const tblPane = document.createElement('div');
    tblPane.className = `tab-pane${tblActive ? ' active' : ''}`;
    tblPane.id        = tblId;
    tblPane.innerHTML = `
      <div class="plot-wrapper">
        <div class="d-flex align-items-center gap-2 mb-2 mt-2">
          <label class="small text-muted mb-0">Sheet:</label>
          <select class="form-select form-select-sm" id="creep-tbl-sheet-sel"
                  style="width:auto;min-width:130px;">
            ${sheetNames.map(n => `<option value="${escHtml(n)}">${escHtml(n)}</option>`).join('')}
          </select>
        </div>
        <div id="creep-tbl-content"></div>
      </div>`;
    plotTabContent.appendChild(tblPane);

    const _renderTbl = () => {
      const sel = document.getElementById('creep-tbl-sheet-sel');
      document.getElementById('creep-tbl-content').innerHTML =
        _buildPreviewHTML(sel?.value || defaultSheet);
    };

    if (tblActive) setTimeout(_renderTbl, 50);

    tblLi.querySelector('button').addEventListener('shown.bs.tab', _renderTbl);
    tblPane.addEventListener('change', e => {
      if (e.target.id === 'creep-tbl-sheet-sel') _renderTbl();
    });
  };

  const tsId  = 'tab-pane-creep-ts';
  const tblId = 'tab-pane-creep-tbl';

  let tsActive, tblActive;
  if (typeof activeId === 'string') {
    tsActive  = (activeId === '#' + tsId);
    tblActive = (activeId === '#' + tblId);
  } else {
    // If activeId was passed as a boolean (legacy)
    tblActive = !!activeId && tblFirst;
    tsActive  = !!activeId && !tblFirst;
  }

  if (tblFirst) {
    _addTbl(tblActive);
    _addTs(tsActive);
  } else {
    _addTs(tsActive);
    _addTbl(tblActive);
  }
}

async function autoRunCreepPreview() {
  if (!state.file || state.selectedSheets.size === 0) return;
  if (testTypeSelect.value !== 'creep_recovery') return;

  const hasStrain = [...state.selectedSheets].some(name =>
    state.sheets[name]?.columns?.includes('Shear Strain')
  );
  if (!hasStrain) return;

  const fd = new FormData();
  fd.append('file',                state.file);
  fd.append('sheet_names',         JSON.stringify([...state.selectedSheets]));
  fd.append('interval_selections', JSON.stringify(collectIntervalSelections()));
  fd.append('x_col',  'Time');
  fd.append('y_cols', JSON.stringify(['Shear Strain']));
  fd.append('mode',   'lines+markers');

  try {
    const res = await fetch('/api/rawplot', { method: 'POST', body: fd });
    if (!res.ok) return;
    const rawData = await res.json();

    state.creepPreviewFig = rawData.figure;   // persist for later re-use

    const tsPlotDiv = document.getElementById('plot-div-creep-ts');
    if (tsPlotDiv) {
      // If the plot div already exists (on the page), just update it
      const fig = JSON.parse(JSON.stringify(state.creepPreviewFig));
      Plotly.react(tsPlotDiv, fig.data || [], fig.layout || {});
      setTimeout(() => updateCreepPreviewZones(), 50);
    } else if (!state.hasRun) {
      // If no analysis run yet, show the preview as the main view
      plotTabs.innerHTML       = '';
      plotTabContent.innerHTML = '';
      _appendCreepPreviewTabs('#tab-pane-creep-ts', false);   // Time Series active by default
      showPlotSection(true);
    }

  } catch (e) {
    console.warn('Creep preview failed:', e);
  }
}

// ===== Run analysis =====
runBtn.addEventListener('click', runAnalysis);

async function runAnalysis() {
  if (!state.file) return;
  if (state.selectedSheets.size === 0) {
    showError('Please select at least one sheet.');
    return;
  }

  showLoading('Running analysis…');
  const fd = new FormData();
  fd.append('file',                state.file);
  fd.append('sheet_names',         JSON.stringify([...state.selectedSheets]));
  fd.append('test_type',           testTypeSelect.value);
  fd.append('params',              JSON.stringify(collectParams()));
  fd.append('interval_selections', JSON.stringify(collectIntervalSelections()));
  fd.append('sheet_test_types',    JSON.stringify(state.sheetTestTypes));

  try {
    const res = await fetch('/api/analyze', { method: 'POST', body: fd });
    if (!res.ok) {
      let msg = 'Analysis failed';
      try { const err = await res.json(); msg = err.detail || msg; } catch {}
      throw new Error(msg);
    }
    const data = await res.json();
    state.lastResponse = data;
    state.hasRun = true;
    renderPlots(data);
    hideLoading();
  } catch (e) {
    showError(e.message);
  }
}

// ===== Render plots =====
function renderPlots(data) {
  // Capture the currently active tab ID before clearing
  const activeBtn = plotTabs.querySelector('.nav-link.active');
  const prevActiveId = activeBtn ? activeBtn.getAttribute('data-bs-target') : null;

  plotTabs.innerHTML       = '';
  plotTabContent.innerHTML = '';
  clearTimeout(_rerunTimer);

  const figs    = data.figures || [];
  const labels  = data.figure_labels || figs.map((_, i) => `Plot ${i+1}`);
  const figData = figs.map(f => JSON.parse(JSON.stringify(f)));
  const isCreep = data.test_type === 'creep_recovery';

  setAxisScaleState('x', 'linear');
  setAxisScaleState('y', 'linear');

  const plotOpts = { responsive: true, displayModeBar: true, modeBarButtonsToRemove: ['toImage'] };

  // Lazy-render: only draw when a tab becomes visible for the first time
  const renderFig = (i) => {
    const el = document.getElementById(`plot-div-fit-${i}`);
    if (!el || el.dataset.rendered) return;
    el.dataset.rendered = '1';
    Plotly.newPlot(el, figData[i].data || [], figData[i].layout || {}, plotOpts);
    if (i === 0) setTimeout(() => updateFitPlotExclusionZones(), 80);
  };

  // Helper to decide if a tab should be active
  const shouldBeActive = (id, isFirstPossible) => {
    if (prevActiveId) return prevActiveId === (id.startsWith('#') ? id : '#' + id);
    return isFirstPossible;
  };

  // For creep_recovery: Preview tabs (Time Series and Data Table)
  if (isCreep && state.creepPreviewFig) {
    // If no previous active tab, default to Time Series (#tab-pane-creep-ts)
    const activeId = prevActiveId || '#tab-pane-creep-ts';
    _appendCreepPreviewTabs(activeId, false); // tblFirst=false means Time Series is first
  }

  // Main analysis tabs
  figs.forEach((fig, i) => {
    const id     = `tab-pane-fit-${i}`;
    // For non-creep, default first analysis tab to active
    const active = shouldBeActive(id, !isCreep && i === 0);

    const li = document.createElement('li');
    li.className = 'nav-item';
    li.innerHTML = `<button class="nav-link ${active ? 'active' : ''}" data-bs-toggle="tab"
        data-bs-target="#${id}" data-fig-index="${i}"
        type="button">${escHtml(labels[i])}</button>`;
    plotTabs.appendChild(li);

    const pane = document.createElement('div');
    pane.className = `tab-pane ${active ? 'active' : ''}`;
    pane.id        = id;
    // Wrap the plot-container in a wrapper to ensure layout clearance
    pane.innerHTML = `
      <div class="plot-wrapper">
        <div class="plot-container" id="plot-div-fit-${i}"></div>
      </div>`;
    plotTabContent.appendChild(pane);
  });

  // Recovery Components (by hand) — always last for creep_recovery
  if (isCreep && data.creep_samples?.length) {
    _appendByHandTab(data.creep_samples, shouldBeActive('by-hand-tab-pane', false));
  }

  showPlotSection(true);
  updateDescription(data.test_type, labels[0]);

  // Render the currently active fit plot if it exists
  const activeFitBtn = plotTabs.querySelector('.nav-link.active[data-fig-index]');
  if (activeFitBtn) {
    renderFig(parseInt(activeFitBtn.dataset.figIndex));
  } else if (!isCreep) {
    // Default fallback for first non-creep run
    setTimeout(() => renderFig(0), 30);
  }

  plotTabs.querySelectorAll('[data-fig-index]').forEach(btn => {
    btn.addEventListener('shown.bs.tab', () => {
      const i  = parseInt(btn.dataset.figIndex);
      renderFig(i);
      const el = document.getElementById(`plot-div-fit-${i}`);
      if (el) { Plotly.Plots.resize(el); applyAxisScale(el); }
      updateDescription(data.test_type, labels[i]);
    });
  });
}

// ===== Recovery Components — by hand =====

/**
 * Append the "Recovery Components (by hand)" tab.
 * Each creep sample gets its own card with a mini Plotly figure and two
 * threshold inputs (ε₁ = elastic/VE boundary, ε₂ = permanent deformation).
 * All computation is client-side: no extra network call is needed.
 */
function _appendByHandTab(creepSamples, active = false) {
  // --- Tab button ---
  const li = document.createElement('li');
  li.className = 'nav-item';
  li.innerHTML =
    `<button class="nav-link ${active ? 'active' : ''}" id="by-hand-tab-btn" data-bs-toggle="tab"
             data-bs-target="#by-hand-tab-pane" type="button" role="tab">
       Recovery Components (visually)
     </button>`;
  plotTabs.appendChild(li);

  // --- Tab pane ---
  const pane = document.createElement('div');
  pane.className = `tab-pane ${active ? 'active' : ''}`;
  pane.id = 'by-hand-tab-pane';
  pane.setAttribute('role', 'tabpanel');

  // Initialise threshold state with default values (used for export)
  state.byHandThresholds = {};
  creepSamples.forEach((cs, idx) => {
    state.byHandThresholds[cs.sample] = {
      eps1:      cs.eps1_default,
      eps2:      cs.eps2_default,
      eps_total: cs.eps_total,
    };
    pane.appendChild(_buildByHandCard(cs, idx));
  });

  plotTabContent.appendChild(pane);

  // Lazy-render all mini-plots when the tab becomes visible for the first time
  const tabBtn = li.querySelector('button');
  tabBtn.addEventListener('shown.bs.tab', () => {
    creepSamples.forEach((cs, idx) => _initByHandPlot(cs, idx));
    updateDescription(null, null); // Hide desc for this tab
  });
}

/** Build the DOM card for one sample (plot + inputs + fraction display). */
function _buildByHandCard(cs, idx) {
  const card = document.createElement('div');
  card.className = 'card mb-3';

  const hasBurgers = cs.burgers_fracs !== null && cs.burgers_fracs !== undefined;
  const burgersCols = hasBurgers
    ? `<th class="text-center" style="color:#888">Burgers</th>` : '';

  card.innerHTML = `
    <div class="card-header fw-semibold d-flex align-items-center gap-2">
      ${cs.sample}
      <span class="badge bg-secondary fw-normal ms-1">
        ε<sub>total</sub> = ${cs.eps_total.toFixed(5)}
      </span>
    </div>
    <div class="card-body">
      <div class="row g-3 align-items-start flex-nowrap">
        <div class="col" style="min-width:0;overflow:hidden;">
          <div id="bh-plot-${idx}" style="height:280px;width:100%;"></div>
        </div>
        <div class="col-auto" style="width:260px;">

        <label class="form-label small fw-semibold mb-1" style="color:#ff7f0e">
          ε₁ — end of elastic recovery
        </label>
        <div class="input-group input-group-sm mb-3">
          <input type="number" class="form-control" id="bh-eps1-${idx}"
                 step="0.00001" value="${cs.eps1_default.toFixed(5)}"
                 min="0" max="${cs.eps_total.toFixed(5)}">
          <span class="input-group-text">—</span>
        </div>

        <label class="form-label small fw-semibold mb-1" style="color:#4CAF50">
          ε₂ — permanent deformation
        </label>
        <div class="input-group input-group-sm mb-3">
          <input type="number" class="form-control" id="bh-eps2-${idx}"
                 step="0.00001" value="${cs.eps2_default.toFixed(5)}"
                 min="0" max="${cs.eps_total.toFixed(5)}">
          <span class="input-group-text">—</span>
        </div>

        <table class="table table-sm table-bordered small text-center mb-0"
               id="bh-fracs-${idx}">
          <thead class="table-light">
            <tr>
              <th>Component</th>
              <th>Visual</th>
              ${burgersCols}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><span style="color:#2196F3">■</span> Elastic</td>
              <td id="bh-fel-${idx}">—</td>
              ${hasBurgers ? `<td class="text-muted">${cs.burgers_fracs.elastic.toFixed(1)} %</td>` : ''}
            </tr>
            <tr>
              <td><span style="color:#FF9800">■</span> Viscoelastic</td>
              <td id="bh-fve-${idx}">—</td>
              ${hasBurgers ? `<td class="text-muted">${cs.burgers_fracs.viscoelastic.toFixed(1)} %</td>` : ''}
            </tr>
            <tr>
              <td><span style="color:#4CAF50">■</span> Plastic</td>
              <td id="bh-fpl-${idx}">—</td>
              ${hasBurgers ? `<td class="text-muted">${cs.burgers_fracs.plastic.toFixed(1)} %</td>` : ''}
            </tr>
          </tbody>
        </table>
        </div><!-- col-auto -->
      </div><!-- row -->
    </div><!-- card-body -->`;

  // Wire inputs after insertion
  setTimeout(() => {
    const inp1 = document.getElementById(`bh-eps1-${idx}`);
    const inp2 = document.getElementById(`bh-eps2-${idx}`);
    if (!inp1 || !inp2) return;
    const onChange = () => {
      const e1 = parseFloat(inp1.value) || 0;
      const e2 = parseFloat(inp2.value) || 0;
      if (state.byHandThresholds) {
        state.byHandThresholds[cs.sample] = { eps1: e1, eps2: e2, eps_total: cs.eps_total };
      }
      _updateByHandCard(idx, e1, e2, cs.eps_total, cs.t_release);
    };
    inp1.addEventListener('input', onChange);
    inp2.addEventListener('input', onChange);
  }, 0);

  return card;
}

/** Render the Plotly figure for one card (called lazily on tab-shown). */
function _initByHandPlot(cs, idx) {
  const el = document.getElementById(`bh-plot-${idx}`);
  if (!el || el.dataset.rendered) return;
  el.dataset.rendered = '1';

  const eps1 = parseFloat(document.getElementById(`bh-eps1-${idx}`)?.value) || cs.eps1_default;
  const eps2 = parseFloat(document.getElementById(`bh-eps2-${idx}`)?.value) || cs.eps2_default;

  const trace = {
    x: cs.t, y: cs.strain,
    mode: 'markers',
    marker: { color: '#1f77b4', size: 3, symbol: 'circle-open' },
    name: 'Shear Strain',
    hovertemplate: 't=%{x:.2f} s<br>ε=%{y:.5f}<extra></extra>',
  };

  const layout = {
    margin: { l: 60, r: 10, t: 10, b: 40 },
    xaxis: { title: 'Time (s)' },
    yaxis: { title: 'Shear Strain' },
    showlegend: false,
    plot_bgcolor: 'white',
    shapes: [
      // Vertical line at t_release
      { type: 'line', x0: cs.t_release, x1: cs.t_release, y0: 0, y1: 1,
        yref: 'paper', line: { color: '#888', dash: 'dot', width: 1.5 } },
      // ε₁ horizontal line (orange) — shape index 1
      { type: 'line', x0: cs.t_release, x1: cs.t_max, y0: eps1, y1: eps1,
        line: { color: '#ff7f0e', dash: 'dash', width: 2 } },
      // ε₂ horizontal line (green) — shape index 2
      { type: 'line', x0: cs.t_release, x1: cs.t_max, y0: eps2, y1: eps2,
        line: { color: '#4CAF50', dash: 'dash', width: 2 } },
    ],
  };

  Plotly.newPlot(el, [trace], layout, { responsive: true, displayModeBar: false });

  // First fraction update
  _updateByHandCard(idx, eps1, eps2, cs.eps_total, cs.t_release);
}

/** Update threshold lines and fraction table for one sample card. */
function _updateByHandCard(idx, eps1, eps2, epsTotal, tRelease) {
  // Enforce epsTotal ≥ eps1 ≥ eps2 ≥ 0
  eps2 = Math.max(0, Math.min(eps2, epsTotal));
  eps1 = Math.max(eps2, Math.min(eps1, epsTotal));

  // Move the horizontal lines on the plot
  const el = document.getElementById(`bh-plot-${idx}`);
  if (el?._fullLayout) {
    Plotly.relayout(el, {
      'shapes[1].y0': eps1, 'shapes[1].y1': eps1,
      'shapes[2].y0': eps2, 'shapes[2].y1': eps2,
    });
  }

  // Compute fractions
  const fEl = epsTotal > 0 ? 100 * (epsTotal - eps1) / epsTotal : 0;
  const fVe = epsTotal > 0 ? 100 * (eps1  - eps2)  / epsTotal : 0;
  const fPl = epsTotal > 0 ? 100 *  eps2            / epsTotal : 0;

  const fmt = v => `${v.toFixed(1)} %`;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set(`bh-fel-${idx}`, fmt(fEl));
  set(`bh-fve-${idx}`, fmt(fVe));
  set(`bh-fpl-${idx}`, fmt(fPl));
}

// ===== Axis scale =====
function setAxisScaleState(axis, type) {
  axisScale[axis] = type;
  document.getElementById(`${axis}-lin-btn`).classList.toggle('active', type === 'linear');
  document.getElementById(`${axis}-log-btn`).classList.toggle('active', type === 'log');
}

function setAxisScale(axis, type) {
  setAxisScaleState(axis, type);
  const activePane = document.querySelector('#plot-tab-content .tab-pane.show.active');
  if (!activePane) return;
  const plotDiv = activePane.querySelector('[id^="plot-div-"]');
  if (plotDiv) applyAxisScale(plotDiv);
}

function applyAxisScale(plotDiv) {
  if (!plotDiv?._fullLayout) return;
  // Bar charts (e.g. Recovery Components) use fixed percentage axes — skip rescaling
  if (plotDiv._fullLayout.barmode === 'stack') return;
  const update = {
    'xaxis.type': axisScale.x === 'log' ? 'log' : 'linear',
    'yaxis.type': axisScale.y === 'log' ? 'log' : 'linear',
  };
  if (plotDiv._fullLayout.xaxis2) update['xaxis2.type'] = update['xaxis.type'];
  if (plotDiv._fullLayout.yaxis2) update['yaxis2.type'] = update['yaxis.type'];
  Plotly.relayout(plotDiv, update);
}

// ===== Download =====
dlExcelBtn.addEventListener('click', () => triggerDownload('excel'));
dlCsvBtn.addEventListener('click',   () => triggerDownload('csv'));

async function triggerDownload(fmt) {
  if (!state.file || state.selectedSheets.size === 0) return;

  const fd = new FormData();
  fd.append('file',                state.file);
  fd.append('sheet_names',         JSON.stringify([...state.selectedSheets]));
  fd.append('test_type',           testTypeSelect.value);
  fd.append('params',              JSON.stringify(collectParams()));
  fd.append('interval_selections', JSON.stringify(collectIntervalSelections()));
  fd.append('sheet_test_types',    JSON.stringify(state.sheetTestTypes));
  fd.append('download_format',     fmt);
  if (state.byHandThresholds && Object.keys(state.byHandThresholds).length > 0) {
    fd.append('by_hand_thresholds', JSON.stringify(state.byHandThresholds));
  }

  try {
    const res = await fetch('/api/download', { method: 'POST', body: fd });
    if (!res.ok) throw new Error('Download failed');

    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const match = cd.match(/filename=(.+)/);
    const filename = match ? match[1] : `results.${fmt === 'excel' ? 'xlsx' : 'csv'}`;

    const a  = document.createElement('a');
    a.href   = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    showError(e.message);
  }
}

// ===== UI helpers =====
function showLoading(msg = 'Loading…') {
  welcomeState.classList.add('d-none');
  errorState.classList.add('d-none');
  plotSection.classList.add('d-none');
  previewState.classList.add('d-none');
  loadingMsg.textContent = msg;
  loadingState.classList.remove('d-none');
}

function hideLoading() {
  loadingState.classList.add('d-none');
}

function showError(msg) {
  hideLoading();
  welcomeState.classList.add('d-none');
  plotSection.classList.add('d-none');
  previewState.classList.add('d-none');
  errorMsg.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-2"></i>${escHtml(msg)}`;
  errorState.classList.remove('d-none');
}

function showPlotSection(visible) {
  if (visible) {
    welcomeState.classList.add('d-none');
    errorState.classList.add('d-none');
    previewState.classList.add('d-none');
    plotSection.classList.remove('d-none');
  } else {
    plotSection.classList.add('d-none');
    welcomeState.classList.remove('d-none');
  }
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
