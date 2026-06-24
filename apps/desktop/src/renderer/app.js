let backendUrl = '';
let pollTimer = null;
let stageState = [null, 'idle', 'idle', 'idle', 'idle']; // index 1-4

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

function setRunStatus(text, cls) {
  $('run-status').textContent = text;
  $('run-status').style.color = cls === 'ok' ? '#107c10' : cls === 'error' ? '#d13438' : cls === 'pending' ? '#bf7300' : '#888';
}

function enableResultButtons(enabled) {
  $('open-html').disabled = !enabled;
  $('open-export').disabled = !enabled;
}

// ── Stage progress UI ────────────────────────────────────────────

function setStagePill(stage, state) {
  // state: 'idle' | 'active' | 'done' | 'error'
  const pills = document.querySelectorAll('.stage-pill');
  for (const pill of pills) {
    if (pill.dataset.stage === String(stage)) {
      pill.className = 'stage-pill';
      if (state === 'active') pill.classList.add('stage-active');
      else if (state === 'done') pill.classList.add('stage-done');
      else if (state === 'error') pill.classList.add('stage-error');
    }
  }
  stageState[stage] = state;
}

function resetStages() {
  for (let i = 1; i <= 4; i++) setStagePill(i, 'idle');
}

// ── Smart run orchestration ─────────────────────────────────────

function detectStageFromLog(logLines) {
  // Parse the log to detect stage transitions
  const all = (logLines || []).join('\n');
  const stages = { 1: 'idle', 2: 'idle', 3: 'idle', 4: 'idle' };

  // Check for completion marker
  if (all.includes('✅ Smart kjøring fullført')) {
    return { 1: 'done', 2: 'done', 3: 'done', 4: 'done' };
  }

  // Check for errors
  if (all.includes('❌ Stage 1 feilet')) { stages[1] = 'error'; stages[2] = 'idle'; stages[3] = 'idle'; stages[4] = 'idle'; return stages; }
  if (all.includes('❌ Stage 2 feilet')) { stages[1] = 'done'; stages[2] = 'error'; stages[3] = 'idle'; stages[4] = 'idle'; return stages; }
  if (all.includes('❌ Stage 3 feilet')) { stages[1] = 'done'; stages[2] = 'done'; stages[3] = 'error'; stages[4] = 'idle'; return stages; }

  // Check stage completion markers: "─── STAGE2 ───" means stage1 is done
  const stageMarkers = all.match(/─── (STAGE[1-4]) ───/g) || [];
  for (const m of stageMarkers) {
    const num = parseInt(m.match(/STAGE([1-4])/)[1], 10);
    // The marker for stage N means stage N-1 is done
    if (num > 1) stages[num - 1] = 'done';
    // Stage N is currently active
    stages[num] = 'active';
  }

  // If export marker exists, all stages done
  if (all.includes('─── STAGE4 ───')) {
    // Check if Stage 4 completed
    const lines = logLines || [];
    const lastLines = lines.slice(-5).join('\n');
    if (lastLines.includes('✅') || lastLines.includes('Stage 4:')) {
      stages[4] = 'done';
    } else {
      stages[4] = 'active';
    }
  }

  return stages;
}

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
  setRunStatus('Smart kjøring...', 'pending');
}

async function startSimpleRun() {
  resetStages();
  enableResultButtons(false);
  await saveSettings(true);
  await api('/run', {
    method: 'POST',
    body: JSON.stringify({
      input_path: $('input-path').value,
      export_dir: $('export-dir').value,
      allow_missing_sources: $('allow-missing').checked,
      log_level: 'info',
    })
  });
  setRunStatus('Kjører...', 'pending');
}

// ── Polling ─────────────────────────────────────────────────────

async function pollStatus() {
  try {
    const status = await api('/run/status');
    const lines = status.log_lines || [];
    $('log').textContent = lines.join('\n') || 'Ingen logg enda.';
    $('log').parentElement.scrollTop = $('log').parentElement.scrollHeight;

    // If smart run is in progress or just finished, update stage pills
    if (status.run_type === 'pipeline') {
      const detected = detectStageFromLog(lines);
      for (let i = 1; i <= 4; i++) {
        if (detected[i] && detected[i] !== stageState[i]) {
          setStagePill(i, detected[i]);
        }
      }
    }

    $('smart-run').disabled = !!status.running;
    $('simple-run').disabled = !!status.running;

    if (status.running) {
      setRunStatus('Kjører...', 'pending');
    } else if (status.exit_code === 0) {
      setRunStatus('Ferdig', 'ok');
      enableResultButtons(true);
    } else if (status.exit_code) {
      setRunStatus('Feilet', 'error');
    } else {
      setRunStatus('Ikke startet', '');
    }
  } catch (err) {
    setRunStatus(err.message, 'error');
  }
}

// ── Stage status viewer (idle) ──────────────────────────────────

async function fetchStageStatus() {
  try {
    const data = await api('/stage/status');
    const stages = data.stages || [];
    const workDir = data.work_dir || '';

    $('work-dir-display').textContent = workDir;

    // Update stage pills based on existing checkpoints
    for (const s of stages) {
      const num = parseInt(s.name.replace('stage', ''), 10);
      if (s.exists) {
        setStagePill(num, 'done');
      } else {
        setStagePill(num, 'idle');
      }
    }
  } catch {
    // ignore — stage status is not critical
  }
}

// ── Settings ────────────────────────────────────────────────────

async function loadSettings() {
  const data = await api('/settings');
  const settings = data.settings || {};
  $('input-path').value = settings.input_path || $('input-path').value || 'input.xlsx';
  $('export-dir').value = settings.export_dir || $('export-dir').value || 'export';
  $('allow-missing').checked = !!settings.allow_missing_sources;

  // LLM config
  const llm = settings.llm || {};
  $('llm-provider').value = llm.provider || 'openai';
  $('llm-endpoint').value = llm.endpoint || 'https://api.openai.com/v1';
  // Use ?? not || so empty string stays empty (LM Studio has no fixed model)
  $('llm-model').value = llm.model ?? 'gpt-4o';
  if (llm.enabled) $('llm-config-status').textContent = '✅ KI-assistenten er aktiv — brukes under Smart kjøring';
  else $('llm-config-status').textContent = '💤 KI-assistenten er av. Aktiver ved å lagre endepunkt og nøkkel.';

  $('ring-status').textContent = data.secrets_backend === 'keyring'
    ? (navigator.platform.includes('Mac') ? 'macOS' : 'System') : 'Lokal fil';

  const secrets = data.secrets || {};
  $('bookup-email').placeholder = secrets.BOOKUP_EMAIL?.configured ? 'Lagret' : '';
  $('bookup-password').placeholder = secrets.BOOKUP_PASSWORD?.configured ? 'Lagret' : '';
}

async function saveSettings(silent) {
  const secrets = {};
  if ($('bookup-email').value) secrets.BOOKUP_EMAIL = $('bookup-email').value;
  if ($('bookup-password').value) secrets.BOOKUP_PASSWORD = $('bookup-password').value;
  if ($('llm-api-key').value) secrets.LLM_API_KEY = $('llm-api-key').value;

  const endpoint = $('llm-endpoint').value.trim();
  const model = $('llm-model').value.trim();
  const provider = $('llm-provider').value;
  const enabled = !!(endpoint || model);

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
  // Save settings first so the backend has the latest config
  await saveSettings(true);

  $('test-llm').disabled = true;
  $('test-llm').textContent = 'Tester...';
  try {
    const data = await api('/llm/test', { method: 'POST' });
    if (data.ok) {
      $('llm-config-status').textContent = `✅ Tilkobling OK: ${data.response}`;
    }
  } catch (err) {
    $('llm-config-status').textContent = `❌ ${err.message}`;
  } finally {
    $('test-llm').disabled = false;
    $('test-llm').textContent = 'Test KI-tilkobling';
  }
}

function resultPath(file) {
  const exportDir = $('export-dir').value || 'export';
  if (exportDir.endsWith('/') || exportDir.endsWith('\\')) return `${exportDir}${file}`;
  return `${exportDir}/${file}`;
}

// ── Command runners ─────────────────────────────────────────────

let availableCommands = [];

async function loadCommands() {
  try {
    const data = await api('/commands');
    availableCommands = data.commands || [];
    renderCommandButtons(availableCommands);
  } catch {
    availableCommands = [];
  }
}

function renderCommandButtons(commands) {
  const container = $('cmd-buttons');
  container.innerHTML = '';
  const curated = ['verdict', 'critic', 'status', 'tournament', 'calendars'];
  for (const cmd of curated) {
    if (!commands.includes(cmd)) continue;
    const label = {
      verdict: 'Vurder plan',
      critic: 'Plan-kritikk',
      status: 'Pipeline-status',
      tournament: 'List turneringer',
      calendars: 'Generer kalendere',
    }[cmd] || cmd;
    const btn = document.createElement('button');
    btn.className = 'btn cmd-btn';
    btn.textContent = label;
    btn.dataset.cmd = cmd;
    btn.addEventListener('click', () => runCliCmd(cmd));
    container.appendChild(btn);
  }
}

function runCliCmd(cmd) {
  if (['verdict', 'critic', 'status', 'tournament'].includes(cmd)) {
    const argsStr = $('cmd-sync-args').value.trim();
    const args = argsStr ? argsStr.split(/\s+/) : [];
    if (cmd === 'tournament') args.unshift('list');
    runFastCommand(cmd === 'tournament' ? 'tournament' : cmd, args);
  } else {
    const argsStr = $('cmd-args').value.trim();
    const args = argsStr ? argsStr.split(/\s+/) : [];
    runAsyncCommand(cmd, args);
  }
}

async function runFastCommand(command, args) {
  const box = $('cmd-result-box');
  const pre = $('cmd-result');
  box.style.display = 'block';
  pre.textContent = 'Kjører...';

  try {
    // Special case: /stage/status is an API call, not a CLI command
    if (command === 'stage/status') {
      const data = await api('/stage/status');
      pre.textContent = JSON.stringify(data, null, 2);
      pre.style.color = '#ccc';
      return;
    }

    const data = await api('/run/command/result', {
      method: 'POST',
      body: JSON.stringify({ command, args })
    });
    let text = '';
    if (data.stdout) text += data.stdout;
    if (data.stderr) text += '\n[stderr]\n' + data.stderr;
    if (!text) text = '(ingen utdata)';
    if (data.exit_code !== 0) {
      text = `❌ Feilet (exit code: ${data.exit_code})\n\n${text}`;
      pre.style.color = '#f17070';
    } else {
      pre.style.color = '#ccc';
    }
    pre.textContent = text;
  } catch (err) {
    pre.textContent = `❌ ${err.message}`;
    pre.style.color = '#f17070';
  }
}

async function runAsyncCommand(command, args) {
  try {
    await api('/run/command', {
      method: 'POST',
      body: JSON.stringify({ command, args })
    });
    setRunStatus('Kjører kommando...', 'pending');
  } catch (err) {
    alert(err.message);
  }
}

// ── Init ────────────────────────────────────────────────────────

async function init() {
  backendUrl = await window.rvvDesktop.backendUrl();
  await waitForBackend();
  await loadSettings().catch(err => console.error(err));
  await loadCommands();
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
  $('smart-run').addEventListener('click', () => startSmartRun().catch(err => alert(err.message)));
  $('simple-run').addEventListener('click', () => startSimpleRun().catch(err => alert(err.message)));
  $('open-html').addEventListener('click', () => window.rvvDesktop.openPath(resultPath('season_plan.html')));
  $('open-export').addEventListener('click', () => window.rvvDesktop.openPath($('export-dir').value || 'export'));
  $('test-llm').addEventListener('click', () => testLlmConnection().catch(err => alert(err.message)));

  // Auto-fill endpoint + model based on provider selection
  $('llm-provider').addEventListener('change', () => {
    const prov = $('llm-provider').value;
    const presets = {
      'openai':      { endpoint: 'https://api.openai.com/v1',          model: 'gpt-4o' },
      'deepseek':    { endpoint: 'https://api.deepseek.com/v1',        model: 'deepseek-chat' },
      'lm-studio':   { endpoint: 'http://localhost:1234/v1',           model: '' },
      'ollama':      { endpoint: 'http://localhost:11434/v1',          model: '' },
      'custom':      { endpoint: '',                                   model: '' },
    };
    const preset = presets[prov];
    if (preset) {
      if (preset.endpoint) $('llm-endpoint').value = preset.endpoint;
      if (preset.model) $('llm-model').value = preset.model;
    }
    // Update API key hint
    const needsKey = { 'openai': true, 'deepseek': true, 'lm-studio': false, 'ollama': false, 'custom': true };
    if (needsKey[prov] === false) {
      $('llm-key-hint').textContent = 'Kan være tom — lokal LLM krever ingen nøkkel';
    } else {
      $('llm-key-hint').textContent = 'Påkrevd for API-tilgang';
    }
  });

  // Command UI
  $('cmd-run-btn').addEventListener('click', () => {
    const parts = $('cmd-select').value.split(/\s+/);
    const command = parts[0];
    const selectArgs = parts.slice(1);
    const extraStr = $('cmd-args').value.trim();
    const extraArgs = extraStr ? extraStr.split(/\s+/) : [];
    runAsyncCommand(command, [...selectArgs, ...extraArgs]);
  });
  $('cmd-run-fast').addEventListener('click', () => {
    const parts = $('cmd-select').value.split(/\s+/);
    const command = parts[0];
    const selectArgs = parts.slice(1);
    const extraStr = $('cmd-sync-args').value.trim();
    const extraArgs = extraStr ? extraStr.split(/\s+/) : [];
    runFastCommand(command, [...selectArgs, ...extraArgs]);
  });
  $('cmd-result-close').addEventListener('click', () => {
    $('cmd-result-box').style.display = 'none';
  });
}

window.addEventListener('beforeunload', () => { if (pollTimer) clearInterval(pollTimer); });
init().catch(err => alert(err.message));
