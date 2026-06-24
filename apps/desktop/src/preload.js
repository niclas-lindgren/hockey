const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('rvvDesktop', {
  backendUrl: () => ipcRenderer.invoke('backend-url'),
  chooseFile: () => ipcRenderer.invoke('choose-file'),
  chooseFolder: () => ipcRenderer.invoke('choose-folder'),
  openPath: path => ipcRenderer.invoke('open-path', path)
});
