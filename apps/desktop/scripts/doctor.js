#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function fail(message) {
  console.error(`\nRVV Miniputt desktop setup problem:\n${message}\n`);
  process.exit(1);
}

function warn(message) {
  console.warn(`RVV Miniputt desktop warning: ${message}`);
}

const major = Number(process.versions.node.split('.')[0]);
if (major > 22) {
  warn(`Node ${process.version} is newer than the tested range. If Electron fails, use Node 20 or 22 LTS.`);
}

let electronPath;
try {
  electronPath = require('electron');
} catch (error) {
  fail(`Electron is not installed. Run:\n  npm install\n\nDetails: ${error.message}`);
}

if (typeof electronPath !== 'string' || !fs.existsSync(electronPath)) {
  fail(`Electron binary was not found. Run:\n  rm -rf node_modules package-lock.json\n  npm install`);
}

const normalized = electronPath.split(path.sep).join('/');

if (process.platform === 'darwin' && !normalized.includes('Electron.app/Contents/MacOS/Electron')) {
  fail(`Electron was installed for the wrong platform.\n\nCurrent OS: macOS\nInstalled Electron path: ${electronPath}\n\nThis usually happens when node_modules was created in a Linux/Pi environment and then reused on macOS. Fix from apps/desktop on your Mac:\n\n  rm -rf node_modules package-lock.json\n  npm install\n  npm start`);
}

if (process.platform === 'linux' && !normalized.endsWith('/dist/electron')) {
  fail(`Electron does not look like a Linux install.\nInstalled Electron path: ${electronPath}\n\nFix:\n  rm -rf node_modules package-lock.json\n  npm install`);
}

if (process.platform === 'win32' && !normalized.endsWith('/dist/electron.exe')) {
  fail(`Electron does not look like a Windows install.\nInstalled Electron path: ${electronPath}\n\nFix in PowerShell:\n  Remove-Item -Recurse -Force node_modules, package-lock.json\n  npm install`);
}

const repoRoot = path.resolve(__dirname, '..', '..', '..');
const venvPython = process.platform === 'win32'
  ? path.join(repoRoot, 'venv', 'Scripts', 'python.exe')
  : path.join(repoRoot, 'venv', 'bin', 'python3');

if (!fs.existsSync(venvPython)) {
  fail(`Python dependencies are not installed in the repo venv. Run:\n\n  npm run setup:python\n  npm start\n\nThis creates ./venv and installs RVV Miniputt dependencies such as rich/openpyxl/playwright.`);
}

const importCheck = spawnSync(venvPython, ['-c', 'import rich, openpyxl, playwright'], {
  cwd: repoRoot,
  stdio: 'pipe',
  encoding: 'utf8'
});
if (importCheck.status !== 0) {
  fail(`The repo venv exists, but required Python packages are missing. Run:\n\n  npm run setup:python\n  npm start\n\nDetails:\n${importCheck.stderr || importCheck.stdout}`);
}

process.exit(0);
