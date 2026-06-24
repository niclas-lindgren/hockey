let backendUrl = '';
let pollTimer = null;

const $ = id => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(`${backendUrl}${path}`, {
    headers: { 'content-type': 'application/json' },
    ...options
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ── Backend connection ─────────────────────────────────────────

function setTopbarStatus(text, ok) {
  $('backend-status').textContent = ok ? '● Klar' : `● ${text}`;
  $('backend-status').style.opacity = ok ? '1' : '.65';
}

async function checkBackend() {
  try {
    await api('/health');
    setTopbarStatus('Klar', true);
    return true;
  } catch {
    setTopbarStatus('Starter...', false);
    return false;
  }
}

async function waitForBackend() {
  for (let i = 0; i < 60; i++) {
    if (await checkBackend()) return;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  setTopbarStatus('Kunne ikke starte', false);
}

// ── Stage progress UI ─────────────────────────────────────────

function setStagePill(stage, state) {
  const pills = document.querySelectorAll('.stage-pill');
  for (const pill of pills) {
    if (pill.dataset.stage === String(stage)) {
      pill.className = 'stage-pill';
      if (state === 'active') pill.classList.add('stage-active');
      else if (state === 'done') pill.classList.add('stage-done');
      else if (state === 'error') pill.classList.add('stage-error');
    }
  }
}

function resetStages() {
  for (let i = 1; i <= 4; i++) setStagePill(i, 'idle');
}

function detectStageFromLog(lines) {
  const all = (lines || []).join('\n');
  const stages = { 1: 'idle', 2: 'idle', 3: 'idle', 4: 'idle' };
  if (all.includes('✅ Smart kjøring fullført')) {
    return { 1: 'done', 2: 'done', 3: 'done', 4: 'done' };
  }
  if (all.includes('❌ Stage 1 feilet')) { stages[1] = 'error'; return stages; }
  if (all.includes('❌ Stage 2 feilet')) { stages[1] = 'done'; stages[2] = 'error'; return stages; }
  if (all.includes('❌ Stage 3 feilet')) { stages[1] = 'done'; stages[2] = 'done'; stages[3] = 'error'; return stages; }
  const markers = all.match(/─── (STAGE[1-4]) ───/g) || [];
  for (const m of markers) {
    const num = parseInt(m.match(/STAGE([1-4])/)[1], 10);
    if (num > 1) stages[num - 1] = 'done';
    stages[num] = 'active';
  }
  if (all.includes('─── STAGE4 ───')) {
    const lastLines = (lines || []).slice(-5).join('\n');
    stages[4] = lastLines.includes('✅') || lastLines.includes('Stage 4:') ? 'done' : 'active';
  }
  return stages;
}

// ── Status log + run status ───────────────────────────────────

function setRunStatus(text, cls) {
  $('run-status').textContent = text;
  $('run-status').style.color = cls === 'ok' ? '#107c10' : cls === 'error' ? '#d13438' : cls === 'pending' ? '#bf7300' : '#888';
}

function enableResultButtons(enabled) {
  $('open-html').disabled = !enabled;
  $('open-export').disabled = !enabled;
  if (enabled) {
    showLatestExport();
    fetchExportHistory();
  }
}

async function showLatestExport() {
  const panel = $('result-panel');
  const list = $('result-list');
  panel.style.display = 'block';
  list.innerHTML = '<div class="result-loading">Laster...</div>';

  try {
    const cp = await api('/checkpoint/stage4');
    const data = cp.data || cp;
    const files = data.output_files || {};
    const items = Object.entries(files);
    if (items.length === 0) {
      list.innerHTML = '<div class="result-empty">Ingen filer funnet</div>';
      return;
    }
    list.innerHTML = items.map(([label, path]) =>
      `<div class="result-file" onclick="window.rvvDesktop.openPath('${path.replace(/'/g, "\\'")}')">
        <span class="result-file-icon">${fileIcon(path)}</span>
        <span class="result-file-label">${escHtml(label)}</span>
        <span class="result-file-path">${escHtml(shortPath(path))}</span>
      </div>`
    ).join('');
  } catch {
    const exports = await api('/exports');
    const latest = exports.exports?.[0];
    if (latest) {
      list.innerHTML = latest.files.map(f =>
        `<div class="result-file" onclick="window.rvvDesktop.openPath('${f.path.replace(/'/g, "\\'")}')">
          <span class="result-file-icon">${fileIcon(f.name)}</span>
          <span class="result-file-label">${escHtml(f.name)}</span>
          <span class="result-file-path">${escHtml(shortPath(f.path))}</span>
        </div>`
      ).join('');
    } else {
      list.innerHTML = '<div class="result-empty">Ingen eksporter funnet</div>';
    }
  }
}

async function fetchExportHistory() {
  const container = $('export-history');
  const list = $('export-list');
  try {
    const data = await api('/exports');
    const exports = data.exports || [];
    if (exports.length <= 1) {
      container.style.display = 'none';
      return;
    }
    container.style.display = 'block';
    // Skip most recent (shown in result panel), show the rest
    const older = exports.slice(1);
    list.innerHTML = older.map(exp =>
      `<div class="export-folder" onclick="fetchExportFolder('${escHtml(exp.folder)}', this)">
        <span class="export-folder-name">📁 ${escHtml(exp.folder)}</span>
        <span class="export-folder-count">${exp.file_count} filer</span>
      </div>`
    ).join('');
  } catch {
    container.style.display = 'none';
  }
}

async function fetchExportFolder(folder, el) {
  // Toggle expansion
  const next = el.nextElementSibling;
  if (next && next.classList.contains('export-files')) {
    next.remove();
    return;
  }
  try {
    const data = await api('/exports/' + encodeURIComponent(folder));
    const filesDiv = document.createElement('div');
    filesDiv.className = 'export-files';
    filesDiv.innerHTML = (data.files || []).map(f =>
      `<div class="result-file export-file-item" onclick="window.rvvDesktop.openPath('${f.path.replace(/'/g, "\\'")}')">
        <span class="result-file-icon">${fileIcon(f.name)}</span>
        <span class="result-file-label">${escHtml(f.name)}</span>
      </div>`
    ).join('');
    el.parentNode.insertBefore(filesDiv, el.nextSibling);
  } catch { /* ignore */ }
}

function fileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  if (ext === 'html') return '🌐';
  if (ext === 'xlsx' || ext === 'xls') return '📊';
  if (ext === 'ics') return '📅';
  if (ext === 'csv') return '📋';
  if (ext === 'json') return '📄';
  return '📎';
}

function shortPath(p) {
  const parts = p.split('/');
  if (parts.length > 3) return '.../' + parts.slice(-3).join('/');
  return p;
}

function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function pollStatus() {
  try {
    const status = await api('/run/status');
    const lines = status.log_lines || [];
    $('log').textContent = lines.join('\n') || 'Ingen logg enda.';
    $('log').parentElement.scrollTop = $('log').parentElement.scrollHeight;

    if (status.run_type === 'pipeline') {
      const detected = detectStageFromLog(lines);
      for (let i = 1; i <= 4; i++) {
        if (detected[i]) setStagePill(i, detected[i]);
      }
    }

    $('smart-run').disabled = !!status.running;

    if (status.running) {
      setRunStatus('Kjører...', 'pending');
    } else if (status.exit_code === 0) {
      setRunStatus('Ferdig', 'ok');
      enableResultButtons(true);
    } else if (status.exit_code) {
      setRunStatus('Feilet', 'error');
    } else {
      setRunStatus('Klar', '');
    }
  } catch (err) {
    setRunStatus(err.message, 'error');
  }
}

// ── Smart run ─────────────────────────────────────────────────

async function startSmartRun() {
  resetStages();
  enableResultButtons(false);
  await saveSettings(true);
  const planIters = parseInt($('plan-iterations').value, 10) || 3;
  await api('/run/smart', {
    method: 'POST',
    body: JSON.stringify({
      input_path: $('input-path').value,
      export_dir: $('export-dir').value,
      allow_missing_sources: $('allow-missing').checked,
      plan_iterations: planIters,
      max_adjust_iterations: 3,
    })
  });
  setRunStatus('Kjører...', 'pending');
}

// ── Stage status (idle) ───────────────────────────────────────

async function fetchStageStatus() {
  try {
    const data = await api('/stage/status');
    for (const s of data.stages || []) {
      const num = parseInt(s.name.replace('stage', ''), 10);
      setStagePill(num, s.exists ? 'done' : 'idle');
    }
    if (data.work_dir) $('work-dir-display').textContent = data.work_dir;
  } catch { /* ignore */ }
}

// ── Settings ──────────────────────────────────────────────────

async function loadSettings() {
  const data = await api('/settings');
  const settings = data.settings || {};
  $('input-path').value = settings.input_path || $('input-path').value || 'input.xlsx';
  $('export-dir').value = settings.export_dir || $('export-dir').value || 'export';
  $('allow-missing').checked = !!settings.allow_missing_sources;

  const llm = settings.llm || {};
  $('llm-provider').value = llm.provider || 'openai';
  $('llm-endpoint').value = llm.endpoint || 'https://api.openai.com/v1';
  $('llm-model').value = llm.model ?? '';
  updateLlmHelp(llm.provider || 'openai');

  if (llm.enabled) {
    $('llm-config-status').textContent = '✅ KI-assistenten er aktiv — brukes under Smart kjøring';
    $('llm-badge').textContent = '✅ På';
  } else {
    $('llm-config-status').textContent = '💤 KI-assistenten er ikke aktivert. Velg tjeneste og lagre for å aktivere.';
    $('llm-badge').textContent = '💤 Av';
  }

  $('ring-status').textContent = data.secrets_backend === 'keyring'
    ? (navigator.platform.includes('Mac') ? 'macOS' : 'System') : 'Lokal fil';

  const secrets = data.secrets || {};
  $('bookup-email').placeholder = secrets.BOOKUP_EMAIL?.configured ? 'Lagret' : '';
  $('bookup-password').placeholder = secrets.BOOKUP_PASSWORD?.configured ? 'Lagret' : '';
}

function updateLlmHelp(provider) {
  const presets = {
    'openai':    { endpoint: 'https://api.openai.com/v1',          model: 'gpt-4o',       needsKey: true },
    'deepseek':  { endpoint: 'https://api.deepseek.com/v1',        model: 'deepseek-chat', needsKey: true },
    'lm-studio': { endpoint: 'http://localhost:1234/v1',           model: '',              needsKey: false },
    'ollama':    { endpoint: 'http://localhost:11434/v1',          model: '',              needsKey: false },
    'custom':    { endpoint: '',                                   model: '',              needsKey: true },
  };
  const p = presets[provider];
  if (!p) return;
  $('llm-endpoint').value = p.endpoint;
  if (p.model && !$('llm-model').value) $('llm-model').value = p.model;
  $('llm-key-hint').textContent = p.needsKey ? 'Påkrevd for API-tilgang' : 'Kan være tom — lokal LLM krever ingen nøkkel';
  $('llm-model-hint').textContent = p.model ? '' : 'Tom for lokal LLM — bruker lastet modell';
}

async function saveSettings(silent) {
  const secrets = {};
  if ($('bookup-email').value) secrets.BOOKUP_EMAIL = $('bookup-email').value;
  if ($('bookup-password').value) secrets.BOOKUP_PASSWORD = $('bookup-password').value;
  if ($('llm-api-key').value) secrets.LLM_API_KEY = $('llm-api-key').value;

  const provider = $('llm-provider').value;
  const endpoint = $('llm-endpoint').value.trim();
  const model = $('llm-model').value.trim();
  const enabled = !!(endpoint);

  await api('/settings', {
    method: 'POST',
    body: JSON.stringify({
      settings: {
        input_path: $('input-path').value,
        export_dir: $('export-dir').value,
        allow_missing_sources: $('allow-missing').checked,
        llm: { enabled, provider, endpoint, model }
      },
      secrets
    })
  });

  $('bookup-email').value = '';
  $('bookup-password').value = '';
  $('llm-api-key').value = '';
  await loadSettings();
  if (!silent) alert('Innstillingene er lagret.');
}

async function testLlmConnection() {
  await saveSettings(true);
  $('test-llm').disabled = true;
  $('test-llm').textContent = 'Tester...';
  try {
    const data = await api('/llm/test', { method: 'POST' });
    if (data.ok) {
      $('llm-config-status').textContent = `✅ OK: ${data.response}`;
    }
  } catch (err) {
    $('llm-config-status').textContent = `❌ ${err.message}`;
  } finally {
    $('test-llm').disabled = false;
    $('test-llm').textContent = '▶ Test tilkobling';
  }
}

function resultPath(file) {
  const dir = $('export-dir').value || 'export';
  return dir.endsWith('/') || dir.endsWith('\\') ? `${dir}${file}` : `${dir}/${file}`;
}

// ── Init ──────────────────────────────────────────────────────

async function init() {
  backendUrl = await window.rvvDesktop.backendUrl();
  await waitForBackend();
  await loadSettings().catch(err => console.error(err));
  await fetchStageStatus();

  pollTimer = setInterval(pollStatus, 1500);
  pollStatus();
  enableResultButtons(false);

  $('choose-input').addEventListener('click', async () => {
    const file = await window.rvvDesktop.chooseFile();
    if (file) $('input-path').value = file;
  });
  $('choose-export').addEventListener('click', async () => {
    const folder = await window.rvvDesktop.chooseFolder();
    if (folder) $('export-dir').value = folder;
  });
  $('save-settings').addEventListener('click', () => saveSettings().catch(err => alert(err.message)));
  $('test-llm').addEventListener('click', () => testLlmConnection().catch(err => alert(err.message)));
  $('smart-run').addEventListener('click', () => startSmartRun().catch(err => alert(err.message)));
  $('open-html').addEventListener('click', () => window.rvvDesktop.openPath(resultPath('season_plan.html')));
  $('open-export').addEventListener('click', () => window.rvvDesktop.openPath($('export-dir').value || 'export'));
  $('result-panel-close').addEventListener('click', () => { $('result-panel').style.display = 'none'; });
  $('copy-log').addEventListener('click', async () => {
    const text = $('log').textContent;
    try {
      await navigator.clipboard.writeText(text);
      $('copy-log').textContent = '✅ Kopiert!';
      setTimeout(() => { $('copy-log').textContent = '📋 Kopier logg'; }, 2000);
    } catch {
      // Fallback for older browsers
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      $('copy-log').textContent = '✅ Kopiert!';
      setTimeout(() => { $('copy-log').textContent = '📋 Kopier logg'; }, 2000);
    }
  });

  $('llm-provider').addEventListener('change', () => updateLlmHelp($('llm-provider').value));
}

window.addEventListener('beforeunload', () => { if (pollTimer) clearInterval(pollTimer); });
init().catch(err => alert(err.message));
