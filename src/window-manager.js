const { exec } = require('child_process');
const { clipboard } = require('electron');
const { generateRatingScript } = require('./rating-scripts');

function execAsync(cmd) {
  return new Promise((resolve, reject) => {
    exec(cmd, { timeout: 5000 }, (err, stdout, stderr) => {
      if (err) return reject(err);
      resolve(stdout.trim());
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Linux implementation using xdotool & wmctrl ──

async function getWindowsLinux() {
  // wmctrl -l gives: <wid> <desktop> <host> <title>
  const output = await execAsync('wmctrl -l');
  const lines = output.split('\n').filter(Boolean);

  const windows = [];
  for (const line of lines) {
    // Format: 0x04a00003  0 hostname Window Title Here
    const match = line.match(/^(0x[\da-f]+)\s+\S+\s+\S+\s+(.+)$/i);
    if (!match) continue;

    const [, id, title] = match;
    windows.push({ id, title });
  }

  return windows;
}

async function sendTextToWindowsLinux(text, windowIds, mainWindow) {
  // Save the original clipboard content
  const originalClipboard = clipboard.readText();

  // Save our own window ID so we can return focus
  let ourWindowId;
  try {
    ourWindowId = await execAsync('xdotool getactivewindow');
  } catch (e) {
    // fallback: don't restore focus
  }

  // Put the text on the clipboard
  clipboard.writeText(text);

  const results = [];

  for (const wid of windowIds) {
    try {
      // Convert hex window ID to decimal for xdotool
      const decId = parseInt(wid, 16);

      // Activate the target window
      await execAsync(`xdotool windowactivate --sync ${decId}`);
      await sleep(200);

      // Paste from clipboard (Ctrl+V)
      await execAsync(`xdotool key --clearmodifiers ctrl+v`);
      await sleep(100);

      // Press Enter to send the message
      await execAsync(`xdotool key --clearmodifiers Return`);
      await sleep(100);

      results.push({ windowId: wid, success: true });
    } catch (err) {
      results.push({ windowId: wid, success: false, error: err.message });
    }
  }

  // Restore focus to our window
  if (ourWindowId) {
    try {
      await execAsync(`xdotool windowactivate --sync ${ourWindowId}`);
    } catch (e) {
      // Best effort
    }
  }

  // Restore original clipboard after a short delay
  setTimeout(() => {
    clipboard.writeText(originalClipboard);
  }, 500);

  return results;
}

// ── Linux bulk rating via console injection ──

async function rateChatInWindowsLinux(ratingType, windowIds, mainWindow) {
  const originalClipboard = clipboard.readText();

  let ourWindowId;
  try {
    ourWindowId = await execAsync('xdotool getactivewindow');
  } catch (e) {
    // fallback: don't restore focus
  }

  const script = generateRatingScript(ratingType);
  const results = [];

  for (const wid of windowIds) {
    try {
      const decId = parseInt(wid, 16);

      // Activate the target browser window
      await execAsync(`xdotool windowactivate --sync ${decId}`);
      await sleep(300);

      // Open Chrome DevTools Console (Ctrl+Shift+J)
      await execAsync(`xdotool key --clearmodifiers ctrl+shift+j`);
      await sleep(800);

      // Type "allow pasting" to bypass Chrome's paste protection
      await execAsync(`xdotool type --clearmodifiers "allow pasting"`);
      await sleep(100);
      await execAsync(`xdotool key --clearmodifiers Return`);
      await sleep(300);

      // Copy rating script to clipboard and paste into console
      clipboard.writeText(script);
      await sleep(100);
      await execAsync(`xdotool key --clearmodifiers ctrl+v`);
      await sleep(200);

      // Execute the script
      await execAsync(`xdotool key --clearmodifiers Return`);

      // Wait for script to start executing in the page context
      await sleep(1500);

      // Close the DevTools Console
      await execAsync(`xdotool key --clearmodifiers ctrl+shift+j`);
      await sleep(200);

      results.push({ windowId: wid, success: true });
    } catch (err) {
      results.push({ windowId: wid, success: false, error: err.message });
    }
  }

  // Restore focus to our window
  if (ourWindowId) {
    try {
      await execAsync(`xdotool windowactivate --sync ${ourWindowId}`);
    } catch (e) {
      // Best effort
    }
  }

  // Restore original clipboard
  setTimeout(() => {
    clipboard.writeText(originalClipboard);
  }, 500);

  return results;
}

// ── macOS implementation using osascript ──

async function getWindowsMac() {
  const script = `
    tell application "System Events"
      set windowList to {}
      repeat with proc in (every process whose visible is true)
        repeat with w in (every window of proc)
          set end of windowList to (name of proc) & " | " & (name of w) & " | " & (id of w)
        end repeat
      end repeat
    end tell
    return windowList
  `;
  try {
    const output = await execAsync(`osascript -e '${script.replace(/'/g, "'\\''")}'`);
    const entries = output.split(', ');
    return entries.map((entry) => {
      const parts = entry.split(' | ');
      return {
        id: parts[2] || parts[0],
        title: parts.length >= 2 ? `${parts[0]} - ${parts[1]}` : entry,
        appName: parts[0],
      };
    });
  } catch {
    return [];
  }
}

async function sendTextToWindowsMac(text, windowIds, mainWindow) {
  const originalClipboard = clipboard.readText();
  clipboard.writeText(text);

  const results = [];

  for (const wid of windowIds) {
    try {
      // Use osascript to activate window and paste
      await execAsync(`osascript -e 'tell application "System Events" to keystroke "v" using command down'`);
      await sleep(100);
      await execAsync(`osascript -e 'tell application "System Events" to key code 36'`); // Enter
      results.push({ windowId: wid, success: true });
    } catch (err) {
      results.push({ windowId: wid, success: false, error: err.message });
    }
  }

  setTimeout(() => clipboard.writeText(originalClipboard), 500);
  return results;
}

// ── Windows implementation using PowerShell ──

async function getWindowsWin() {
  const psScript = `
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    using System.Text;
    using System.Collections.Generic;
    public class WindowHelper {
      [DllImport("user32.dll")]
      public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
      [DllImport("user32.dll")]
      public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
      [DllImport("user32.dll")]
      public static extern bool IsWindowVisible(IntPtr hWnd);
      public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
      public static List<string> GetWindows() {
        var windows = new List<string>();
        EnumWindows((hWnd, lParam) => {
          if (IsWindowVisible(hWnd)) {
            var sb = new StringBuilder(256);
            GetWindowText(hWnd, sb, 256);
            var title = sb.ToString();
            if (!string.IsNullOrEmpty(title)) {
              windows.Add(hWnd.ToInt64() + "|" + title);
            }
          }
          return true;
        }, IntPtr.Zero);
        return windows;
      }
    }
"@
    [WindowHelper]::GetWindows() | ForEach-Object { $_ }
  `;
  try {
    const output = await execAsync(
      `powershell -NoProfile -Command "${psScript.replace(/"/g, '\\"')}"`,
    );
    return output
      .split('\n')
      .filter(Boolean)
      .map((line) => {
        const [id, ...titleParts] = line.split('|');
        return { id: id.trim(), title: titleParts.join('|').trim() };
      });
  } catch {
    return [];
  }
}

async function sendTextToWindowsWin(text, windowIds, mainWindow) {
  const originalClipboard = clipboard.readText();
  clipboard.writeText(text);

  const results = [];

  for (const wid of windowIds) {
    try {
      const psScript = `
        Add-Type @"
        using System;
        using System.Runtime.InteropServices;
        public class WinActivate {
          [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        }
"@
        [WinActivate]::SetForegroundWindow([IntPtr]${wid})
      `;
      await execAsync(`powershell -NoProfile -Command "${psScript.replace(/"/g, '\\"')}"`);
      await sleep(200);

      // Simulate Ctrl+V and Enter using PowerShell SendKeys
      await execAsync(
        `powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('^v'); Start-Sleep -Milliseconds 100; [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')"`,
      );
      await sleep(100);

      results.push({ windowId: wid, success: true });
    } catch (err) {
      results.push({ windowId: wid, success: false, error: err.message });
    }
  }

  setTimeout(() => clipboard.writeText(originalClipboard), 500);
  return results;
}

// ── macOS bulk rating via console injection ──

async function rateChatInWindowsMac(ratingType, windowIds, mainWindow) {
  const originalClipboard = clipboard.readText();
  const script = generateRatingScript(ratingType);
  const results = [];

  for (const wid of windowIds) {
    try {
      // Activate window, open console, inject script
      await execAsync(`osascript -e 'tell application "System Events" to keystroke "j" using {command down, shift down}'`);
      await sleep(800);

      // Type "allow pasting" for paste protection
      await execAsync(`osascript -e 'tell application "System Events" to keystroke "allow pasting"'`);
      await sleep(100);
      await execAsync(`osascript -e 'tell application "System Events" to key code 36'`);
      await sleep(300);

      // Paste the script
      clipboard.writeText(script);
      await sleep(100);
      await execAsync(`osascript -e 'tell application "System Events" to keystroke "v" using command down'`);
      await sleep(200);

      // Execute
      await execAsync(`osascript -e 'tell application "System Events" to key code 36'`);
      await sleep(1500);

      // Close console
      await execAsync(`osascript -e 'tell application "System Events" to keystroke "j" using {command down, shift down}'`);
      await sleep(200);

      results.push({ windowId: wid, success: true });
    } catch (err) {
      results.push({ windowId: wid, success: false, error: err.message });
    }
  }

  setTimeout(() => clipboard.writeText(originalClipboard), 500);
  return results;
}

// ── Windows bulk rating via console injection ──

async function rateChatInWindowsWin(ratingType, windowIds, mainWindow) {
  const originalClipboard = clipboard.readText();
  const script = generateRatingScript(ratingType);
  const results = [];

  for (const wid of windowIds) {
    try {
      // Activate window
      const psActivate = `
        Add-Type @"
        using System;
        using System.Runtime.InteropServices;
        public class WinActivate {
          [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        }
"@
        [WinActivate]::SetForegroundWindow([IntPtr]${wid})
      `;
      await execAsync(`powershell -NoProfile -Command "${psActivate.replace(/"/g, '\\"')}"`);
      await sleep(300);

      // Open DevTools Console (Ctrl+Shift+J)
      await execAsync(
        `powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('^+j')"`,
      );
      await sleep(800);

      // Type "allow pasting"
      await execAsync(
        `powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('allow pasting{ENTER}')"`,
      );
      await sleep(300);

      // Paste script
      clipboard.writeText(script);
      await sleep(100);
      await execAsync(
        `powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('^v'); Start-Sleep -Milliseconds 200; [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')"`,
      );
      await sleep(1500);

      // Close console
      await execAsync(
        `powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('^+j')"`,
      );
      await sleep(200);

      results.push({ windowId: wid, success: true });
    } catch (err) {
      results.push({ windowId: wid, success: false, error: err.message });
    }
  }

  setTimeout(() => clipboard.writeText(originalClipboard), 500);
  return results;
}

// ── Platform dispatch ──

async function getWindows() {
  switch (process.platform) {
    case 'linux':
      return getWindowsLinux();
    case 'darwin':
      return getWindowsMac();
    case 'win32':
      return getWindowsWin();
    default:
      throw new Error(`Unsupported platform: ${process.platform}`);
  }
}

async function sendTextToWindows(text, windowIds, mainWindow) {
  switch (process.platform) {
    case 'linux':
      return sendTextToWindowsLinux(text, windowIds, mainWindow);
    case 'darwin':
      return sendTextToWindowsMac(text, windowIds, mainWindow);
    case 'win32':
      return sendTextToWindowsWin(text, windowIds, mainWindow);
    default:
      throw new Error(`Unsupported platform: ${process.platform}`);
  }
}

async function rateChatInWindows(ratingType, windowIds, mainWindow) {
  switch (process.platform) {
    case 'linux':
      return rateChatInWindowsLinux(ratingType, windowIds, mainWindow);
    case 'darwin':
      return rateChatInWindowsMac(ratingType, windowIds, mainWindow);
    case 'win32':
      return rateChatInWindowsWin(ratingType, windowIds, mainWindow);
    default:
      throw new Error(`Unsupported platform: ${process.platform}`);
  }
}

module.exports = { getWindows, sendTextToWindows, rateChatInWindows };
