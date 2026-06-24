#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const targets = ['node_modules', 'package-lock.json'];

for (const target of targets) {
  const fullPath = path.join(root, target);
  if (fs.existsSync(fullPath)) {
    console.log(`Removing ${target}...`);
    fs.rmSync(fullPath, { recursive: true, force: true });
  }
}

console.log('Reinstalling npm dependencies for this platform...');
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const result = spawnSync(npm, ['install'], {
  cwd: root,
  stdio: 'inherit',
  env: process.env
});

process.exit(result.status ?? 1);
