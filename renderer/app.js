// State
let windows = [];
let selectedWindowIds = new Set();

// DOM elements
const windowList = document.getElementById('window-list');
const textInput = document.getElementById('text-input');
const btnSend = document.getElementById('btn-send');
const btnRefresh = document.getElementById('btn-refresh');
const btnSelectAll = document.getElementById('btn-select-all');
const btnDeselectAll = document.getElementById('btn-deselect-all');
const selectedCount = document.getElementById('selected-count');
const sendStatus = document.getElementById('send-status');
const btnThumbsUp = document.getElementById('btn-thumbs-up');
const btnThumbsDown = document.getElementById('btn-thumbs-down');
const ratingStatus = document.getElementById('rating-status');

// ── Chat service detection ──

const CHAT_PATTERNS = [
  { pattern: /chatgpt|chat\.openai/i, label: 'ChatGPT', badge: 'badge-chatgpt' },
  { pattern: /claude\.ai|anthropic/i, label: 'Claude', badge: 'badge-claude' },
  { pattern: /gemini|bard.*google/i, label: 'Gemini', badge: 'badge-gemini' },
  { pattern: /copilot.*microsoft|copilot\.microsoft/i, label: 'Copilot', badge: 'badge-generic' },
  { pattern: /perplexity/i, label: 'Perplexity', badge: 'badge-generic' },
  { pattern: /poe\.com/i, label: 'Poe', badge: 'badge-generic' },
  { pattern: /huggingface|hugging\s*face/i, label: 'HuggingChat', badge: 'badge-generic' },
  { pattern: /deepseek/i, label: 'DeepSeek', badge: 'badge-generic' },
  { pattern: /grok/i, label: 'Grok', badge: 'badge-generic' },
  { pattern: /mistral/i, label: 'Mistral', badge: 'badge-generic' },
];

function detectChatService(title) {
  for (const { pattern, label, badge } of CHAT_PATTERNS) {
    if (pattern.test(title)) {
      return { label, badge };
    }
  }
  return null;
}

// ── Rendering ──

function renderWindows() {
  if (windows.length === 0) {
    windowList.innerHTML =
      '<div class="placeholder">No windows found. Make sure your browser with AI chats is open, then click "Refresh".</div>';
    return;
  }

  windowList.innerHTML = '';

  for (const win of windows) {
    const item = document.createElement('div');
    item.className = 'window-item' + (selectedWindowIds.has(win.id) ? ' selected' : '');
    item.dataset.id = win.id;

    const chatService = detectChatService(win.title);

    let badgeHtml = '';
    if (chatService) {
      badgeHtml = `<span class="chat-badge ${chatService.badge}">${chatService.label}</span>`;
    }

    item.innerHTML = `
      <div class="checkbox"></div>
      <div class="window-info">
        <div class="window-title">${escapeHtml(win.title)}</div>
        <div class="window-id">${win.id}</div>
      </div>
      ${badgeHtml}
    `;

    item.addEventListener('click', () => toggleWindow(win.id));
    windowList.appendChild(item);
  }
}

function updateSelectedCount() {
  const count = selectedWindowIds.size;
  selectedCount.textContent = `${count} window${count !== 1 ? 's' : ''} selected`;
  btnSend.disabled = count === 0;
  btnThumbsUp.disabled = count === 0;
  btnThumbsDown.disabled = count === 0;
}

function toggleWindow(id) {
  if (selectedWindowIds.has(id)) {
    selectedWindowIds.delete(id);
  } else {
    selectedWindowIds.add(id);
  }
  renderWindows();
  updateSelectedCount();
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Actions ──

async function refreshWindows() {
  btnRefresh.disabled = true;
  btnRefresh.textContent = '↻ Scanning...';

  try {
    windows = await window.api.getWindows();
    // Clean up selected IDs that no longer exist
    const validIds = new Set(windows.map((w) => w.id));
    selectedWindowIds = new Set([...selectedWindowIds].filter((id) => validIds.has(id)));
    renderWindows();
    updateSelectedCount();
  } catch (err) {
    windowList.innerHTML = `<div class="placeholder">Error scanning windows: ${escapeHtml(err.message)}</div>`;
  } finally {
    btnRefresh.disabled = false;
    btnRefresh.textContent = '↻ Refresh';
  }
}

async function sendText() {
  const text = textInput.value.trim();
  if (!text || selectedWindowIds.size === 0) return;

  btnSend.disabled = true;
  sendStatus.textContent = 'Sending...';
  sendStatus.className = 'sending';

  try {
    const result = await window.api.sendText(text, [...selectedWindowIds]);

    if (result.success) {
      const successCount = result.results.filter((r) => r.success).length;
      const failCount = result.results.filter((r) => !r.success).length;

      if (failCount === 0) {
        sendStatus.textContent = `✓ Sent to ${successCount} window${successCount !== 1 ? 's' : ''}`;
        sendStatus.className = 'success';
      } else {
        sendStatus.textContent = `Sent: ${successCount}, Failed: ${failCount}`;
        sendStatus.className = 'error';
      }
      textInput.value = '';
    } else {
      sendStatus.textContent = `Error: ${result.error}`;
      sendStatus.className = 'error';
    }
  } catch (err) {
    sendStatus.textContent = `Error: ${err.message}`;
    sendStatus.className = 'error';
  } finally {
    btnSend.disabled = selectedWindowIds.size === 0;
    // Clear status after 3 seconds
    setTimeout(() => {
      sendStatus.textContent = '';
      sendStatus.className = '';
    }, 3000);
  }
}

async function rateChat(ratingType) {
  if (selectedWindowIds.size === 0) return;

  const label = ratingType === 'up' ? 'thumbs up' : 'thumbs down';
  btnThumbsUp.disabled = true;
  btnThumbsDown.disabled = true;
  ratingStatus.textContent = `Rating ${label}...`;
  ratingStatus.className = 'sending';

  try {
    const result = await window.api.rateChat(ratingType, [...selectedWindowIds]);

    if (result.success) {
      const successCount = result.results.filter((r) => r.success).length;
      const failCount = result.results.filter((r) => !r.success).length;

      if (failCount === 0) {
        ratingStatus.textContent = `✓ Rated ${label} in ${successCount} window${successCount !== 1 ? 's' : ''}`;
        ratingStatus.className = 'success';
      } else {
        ratingStatus.textContent = `Done: ${successCount}, Failed: ${failCount}`;
        ratingStatus.className = 'error';
      }
    } else {
      ratingStatus.textContent = `Error: ${result.error}`;
      ratingStatus.className = 'error';
    }
  } catch (err) {
    ratingStatus.textContent = `Error: ${err.message}`;
    ratingStatus.className = 'error';
  } finally {
    btnThumbsUp.disabled = selectedWindowIds.size === 0;
    btnThumbsDown.disabled = selectedWindowIds.size === 0;
    setTimeout(() => {
      ratingStatus.textContent = '';
      ratingStatus.className = '';
    }, 4000);
  }
}

// ── Event Listeners ──

btnThumbsUp.addEventListener('click', () => rateChat('up'));
btnThumbsDown.addEventListener('click', () => rateChat('down'));

btnRefresh.addEventListener('click', refreshWindows);

btnSelectAll.addEventListener('click', () => {
  windows.forEach((w) => selectedWindowIds.add(w.id));
  renderWindows();
  updateSelectedCount();
});

btnDeselectAll.addEventListener('click', () => {
  selectedWindowIds.clear();
  renderWindows();
  updateSelectedCount();
});

btnSend.addEventListener('click', sendText);

// Enter to send, Shift+Enter for new line
textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendText();
  }
});

// ── Init ──
textInput.focus();
updateSelectedCount();
