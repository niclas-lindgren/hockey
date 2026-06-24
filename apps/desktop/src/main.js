const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const BACKEND_PORT = process.env.RVV_MINIPUTT_DESKTOP_PORT || '8765';
let backendProcess = null;
let mainWindow = null;

function backendExecutableName() {
  if (process.platform === 'win32') return 'rvv-miniputt-backend.exe';
  return 'rvv-miniputt-backend';
}

function resolveBackendCommand() {
  const resourceBackend = path.join(process.resourcesPath || '', 'backend');
  const packagedCandidates = [
    path.join(resourceBackend, backendExecutableName()),
    path.join(resourceBackend, 'rvv-miniputt-backend', backendExecutableName())
  ];
  const packaged = packagedCandidates.find(candidate => fs.existsSync(candidate));
  if (app.isPackaged && packaged) {
    return { command: packaged, args: ['--port', BACKEND_PORT], cwd: path.dirname(packaged) };
  }

  // Development fallback: run the Python module from the repo root.
  const repoRoot = path.resolve(__dirname, '..', '..', '..');
  const venvPython = process.platform === 'win32'
    ? path.join(repoRoot, 'venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, 'venv', 'bin', 'python3');
  const python = fs.existsSync(venvPython) ? venvPython : (process.env.PYTHON || 'python3');
  return {
    command: python,
    args: ['-m', 'tournament_scheduler.desktop_server', '--port', BACKEND_PORT],
    cwd: repoRoot
  };
}

function startBackend() {
  const backend = resolveBackendCommand();
  backendProcess = spawn(backend.command, backend.args, {
    cwd: backend.cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1' }
  });

  backendProcess.stdout.on('data', data => console.log(`[backend] ${data}`));
  backendProcess.stderr.on('data', data => console.error(`[backend] ${data}`));
  backendProcess.on('exit', code => console.log(`Backend exited with ${code}`));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 820,
    minWidth: 900,
    minHeight: 650,
    title: 'RVV Miniputt',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

ipcMain.handle('backend-url', () => `http://127.0.0.1:${BACKEND_PORT}`);

ipcMain.handle('choose-file', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Velg input.xlsx',
    properties: ['openFile'],
    filters: [{ name: 'Excel', extensions: ['xlsx'] }]
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('choose-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Velg mappe',
    properties: ['openDirectory', 'createDirectory']
  });
  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle('open-path', async (_event, targetPath) => {
  if (!targetPath) return false;
  await shell.openPath(targetPath);
  return true;
});

app.whenReady().then(() => {
  startBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', () => {
  if (backendProcess && !backendProcess.killed) backendProcess.kill();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
