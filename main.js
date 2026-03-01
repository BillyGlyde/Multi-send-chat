const { app, BrowserWindow, ipcMain, clipboard, globalShortcut } = require('electron');
const path = require('path');
const windowManager = require('./src/window-manager');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    minWidth: 400,
    minHeight: 300,
    alwaysOnTop: true,
    frame: true,
    transparent: false,
    title: 'All AI Chat',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers

// Get list of open windows that look like browser/chat windows
ipcMain.handle('get-windows', async () => {
  try {
    return await windowManager.getWindows();
  } catch (err) {
    console.error('Failed to get windows:', err);
    return [];
  }
});

// Send text to selected windows
ipcMain.handle('send-text', async (event, { text, windowIds }) => {
  try {
    const results = await windowManager.sendTextToWindows(text, windowIds, mainWindow);
    return { success: true, results };
  } catch (err) {
    console.error('Failed to send text:', err);
    return { success: false, error: err.message };
  }
});
