#!/usr/bin/env node
const { spawn } = require('child_process');
const electron = require('electron');

const args = [];

// Linux dev environments running from mounted filesystems (for example Lima
// mounting /Users/...) often cannot set the chrome-sandbox helper to root:4755.
// Use Chromium's no-sandbox flag for local development only. Packaged apps
// should use the platform's normal sandboxing/signing story.
if (process.platform === 'linux') {
  args.push('--no-sandbox');
}

args.push('.');

const child = spawn(electron, args, { stdio: 'inherit', windowsHide: false });
child.on('close', (code, signal) => {
  if (code === null) {
    console.error(`${electron} exited with signal ${signal}`);
    process.exit(1);
  }
  process.exit(code);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    if (!child.killed) child.kill(signal);
  });
}
