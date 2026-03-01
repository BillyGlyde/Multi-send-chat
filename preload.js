const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  getWindows: () => ipcRenderer.invoke('get-windows'),
  sendText: (text, windowIds) => ipcRenderer.invoke('send-text', { text, windowIds }),
});
