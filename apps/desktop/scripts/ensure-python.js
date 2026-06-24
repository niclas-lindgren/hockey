#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const repoRoot = path.resolve(__dirname, '..', '..', '..');
const venvPython = process.platform === 'win32'
  ? path.join(repoRoot, 'venv', 'Scripts', 'python.exe')
  : path.join(repoRoot, 'venv', 'bin', 'python3');

function pythonReady() {
  if (!fs.existsSync(venvPython)) return false;
  const result = spawnSync(venvPython, ['-c', 'import rich, openpyxl, playwright'], {
    cwd: repoRoot,
    stdio: 'ignore'
  });
  return result.status === 0;
}

if (pythonReady()) process.exit(0);

console.log('\nPython environment is missing or incomplete. Setting it up now...\n');
const result = spawnSync(process.execPath, [path.join(__dirname, 'setup-python.js')], {
  cwd: path.resolve(__dirname, '..'),
  stdio: 'inherit',
  env: process.env
});

process.exit(result.status ?? 1);
