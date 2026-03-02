/**
 * Generates JavaScript to inject into browser console that clicks
 * all thumbs-up or thumbs-down rating buttons in an AI chat page.
 *
 * @param {'up'|'down'} ratingType
 * @returns {string} Minified JavaScript code
 */
function generateRatingScript(ratingType) {
  const script = `
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const h = location.hostname;
  const R = '${ratingType}';
  let count = 0;

  async function dismissPopup() {
    await sleep(500);
    const sels = [
      '[aria-label="Close"]',
      '[aria-label="close"]',
      '[data-testid="close-button"]',
      '[role="dialog"] button[aria-label="Close"]',
      '[role="dialog"] button:first-of-type',
      '.fixed [aria-label="Close"]',
      '.modal button[aria-label="Close"]',
    ];
    for (const sel of sels) {
      const els = document.querySelectorAll(sel);
      for (const el of els) {
        if (el.offsetParent !== null) { el.click(); await sleep(200); return; }
      }
    }
    document.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true, cancelable: true
    }));
    await sleep(300);
  }

  function isActive(btn) {
    if (btn.getAttribute('aria-pressed') === 'true') return true;
    if (btn.dataset.state === 'active' || btn.dataset.state === 'selected') return true;
    const cls = btn.className || '';
    if (/\\b(active|selected|filled|liked|disliked)\\b/.test(cls)) return true;
    return false;
  }

  async function clickAll(btns) {
    const todo = btns.filter(b => !isActive(b));
    for (const btn of todo) {
      btn.scrollIntoView({ block: 'center', behavior: 'instant' });
      await sleep(100);
      btn.click();
      count++;
      if (R === 'down') await dismissPopup();
      else await sleep(100);
    }
  }

  const services = [
    {
      match: ['chatgpt.com', 'chat.openai.com'],
      up: ['[data-testid="thumbs-up"]', '[data-testid="good-response-turn-action"]', 'button[aria-label="Good response"]', 'button[aria-label="Like"]'],
      down: ['[data-testid="thumbs-down"]', '[data-testid="bad-response-turn-action"]', 'button[aria-label="Bad response"]', 'button[aria-label="Dislike"]'],
    },
    {
      match: ['claude.ai'],
      up: ['button[aria-label="Thumbs up"]', 'button[aria-label="Good response"]', 'button[data-testid="thumbs-up"]'],
      down: ['button[aria-label="Thumbs down"]', 'button[aria-label="Bad response"]', 'button[data-testid="thumbs-down"]'],
    },
    {
      match: ['gemini.google.com'],
      up: ['button[aria-label="Good response"]', 'button[aria-label="Like"]', 'button[aria-label="Thumbs up"]'],
      down: ['button[aria-label="Bad response"]', 'button[aria-label="Dislike"]', 'button[aria-label="Thumbs down"]'],
    },
    {
      match: ['copilot.microsoft.com'],
      up: ['button[aria-label="Like"]', 'button[aria-label="Helpful"]', 'button[aria-label="Thumbs up"]'],
      down: ['button[aria-label="Dislike"]', 'button[aria-label="Not helpful"]', 'button[aria-label="Thumbs down"]'],
    },
    {
      match: ['perplexity.ai'],
      up: ['button[aria-label="Like"]', 'button[aria-label="Thumbs up"]', 'button[aria-label="Good"]'],
      down: ['button[aria-label="Dislike"]', 'button[aria-label="Thumbs down"]', 'button[aria-label="Bad"]'],
    },
    {
      match: ['deepseek.com', 'chat.deepseek.com'],
      up: ['button[aria-label="Like"]', 'button[aria-label="Thumbs up"]', '[data-testid="thumbs-up"]'],
      down: ['button[aria-label="Dislike"]', 'button[aria-label="Thumbs down"]', '[data-testid="thumbs-down"]'],
    },
    {
      match: ['grok.com'],
      up: ['button[aria-label="Like"]', 'button[aria-label="Good"]', 'button[aria-label="Thumbs up"]'],
      down: ['button[aria-label="Dislike"]', 'button[aria-label="Bad"]', 'button[aria-label="Thumbs down"]'],
    },
    {
      match: ['chat.mistral.ai', 'mistral.ai'],
      up: ['button[aria-label="Like"]', 'button[aria-label="Thumbs up"]', 'button[aria-label="Good"]'],
      down: ['button[aria-label="Dislike"]', 'button[aria-label="Thumbs down"]', 'button[aria-label="Bad"]'],
    },
    {
      match: ['poe.com'],
      up: ['button[aria-label="Upvote"]', 'button[aria-label="Like"]', 'button[aria-label="Thumbs up"]'],
      down: ['button[aria-label="Downvote"]', 'button[aria-label="Dislike"]', 'button[aria-label="Thumbs down"]'],
    },
    {
      match: ['huggingface.co'],
      up: ['button[aria-label="Like"]', 'button[aria-label="Thumbs up"]', 'button[aria-label="Good"]'],
      down: ['button[aria-label="Dislike"]', 'button[aria-label="Thumbs down"]', 'button[aria-label="Bad"]'],
    },
  ];

  let selectors = null;
  for (const svc of services) {
    if (svc.match.some(p => h.includes(p))) {
      selectors = R === 'up' ? svc.up : svc.down;
      break;
    }
  }

  if (!selectors) {
    selectors = R === 'up'
      ? ['button[aria-label*="like" i]', 'button[aria-label*="good" i]', 'button[aria-label*="thumbs up" i]']
      : ['button[aria-label*="dislike" i]', 'button[aria-label*="bad" i]', 'button[aria-label*="thumbs down" i]'];
  }

  let btns = [];
  for (const sel of selectors) {
    try {
      const found = [...document.querySelectorAll(sel)];
      if (found.length > 0) { btns = found; break; }
    } catch (e) {}
  }

  if (btns.length === 0) {
    console.log('[AllAIChat] No rating buttons found on this page.');
  } else {
    await clickAll(btns);
    console.log('[AllAIChat] Bulk rating complete: ' + count + ' buttons clicked');
  }
})()`;

  // Minify: strip comments, collapse whitespace, join to single line
  return script
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0 && !line.startsWith('//'))
    .join(' ');
}

module.exports = { generateRatingScript };
