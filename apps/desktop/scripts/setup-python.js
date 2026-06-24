#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..', '..', '..');
const venvDir = path.join(repoRoot, 'venv');
const venvPython = process.platform === 'win32'
  ? path.join(venvDir, 'Scripts', 'python.exe')
  : path.join(venvDir, 'bin', 'python3');

function run(command, args, options = {}) {
  console.log(`$ ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, {
    cwd: repoRoot,
    stdio: 'inherit',
    shell: false,
    env: process.env,
    ...options
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function capture(command, args) {
  return spawnSync(command, args, {
    cwd: repoRoot,
    stdio: 'pipe',
    encoding: 'utf8',
    shell: false,
    env: process.env
  });
}

function pythonVersion(command, prefixArgs = []) {
  const script = 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")';
  const result = capture(command, [...prefixArgs, '-c', script]);
  if (result.status !== 0) return null;
  const text = (result.stdout || '').trim();
  const parts = text.split('.').map(Number);
  if (parts.length < 2 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) return null;
  return { text, major: parts[0], minor: parts[1] };
}

function isSupported(version) {
  return version && (version.major > 3 || (version.major === 3 && version.minor >= 10));
}

function findPython() {
  const candidates = [];
  if (process.env.PYTHON) candidates.push({ command: process.env.PYTHON, args: [] });

  if (process.platform === 'win32') {
    candidates.push({ command: 'py', args: ['-3.12'] });
    candidates.push({ command: 'py', args: ['-3.11'] });
    candidates.push({ command: 'py', args: ['-3.10'] });
    candidates.push({ command: 'python', args: [] });
  } else {
    candidates.push({ command: 'python3.12', args: [] });
    candidates.push({ command: 'python3.11', args: [] });
    candidates.push({ command: 'python3.10', args: [] });
    candidates.push({ command: '/opt/homebrew/bin/python3', args: [] });
    candidates.push({ command: '/usr/local/bin/python3', args: [] });
    candidates.push({ command: 'python3', args: [] });
  }

  for (const candidate of candidates) {
    const version = pythonVersion(candidate.command, candidate.args);
    if (isSupported(version)) return { ...candidate, version };
  }
  return null;
}

function existingVenvVersion() {
  if (!fs.existsSync(venvPython)) return null;
  return pythonVersion(venvPython, []);
}

const existing = existingVenvVersion();
if (existing && !isSupported(existing)) {
  console.log(`Existing venv uses Python ${existing.text}, but RVV Miniputt requires Python 3.10+. Recreating venv...`);
  fs.rmSync(venvDir, { recursive: true, force: true });
}

const python = findPython();
if (!python) {
  const macHint = process.platform === 'darwin'
    ? '\n\nOn macOS, install a newer Python with one of:\n  brew install python@3.12\n  # or download from https://www.python.org/downloads/'
    : '';
  console.error(`Could not find Python 3.10 or newer.${macHint}\n\nThen rerun:\n  npm run setup:python`);
  process.exit(1);
}

console.log(`Using Python ${python.version.text}: ${python.command} ${python.args.join(' ')}`.trim());

if (!fs.existsSync(venvPython)) {
  run(python.command, [...python.args, '-m', 'venv', venvDir]);
}

run(venvPython, ['-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel']);
run(venvPython, ['-m', 'pip', 'install', '-e', '.[desktop]']);

console.log('\nPython environment is ready. You can now run:\n  npm start\n');
