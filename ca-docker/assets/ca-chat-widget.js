/**
 * Collective Access — AI Collection Agent Widget
 * Injected into every CA admin page via nginx sub_filter.
 * Talks to /ca-agent-proxy.php (PHP file in CA web root).
 */
(function () {
  'use strict';

  // ── Styles ──────────────────────────────────────────────────────────────
  const CSS = `
    #ca-agent-btn {
      position: fixed; bottom: 24px; right: 24px; z-index: 99999;
      width: 54px; height: 54px; border-radius: 50%;
      background: #2563eb; color: #fff; border: none; cursor: pointer;
      box-shadow: 0 4px 16px rgba(0,0,0,.28);
      font-size: 24px; display: flex; align-items: center; justify-content: center;
      transition: background .2s, transform .15s;
    }
    #ca-agent-btn:hover { background: #1d4ed8; transform: scale(1.07); }

    #ca-agent-panel {
      position: fixed; bottom: 88px; right: 24px; z-index: 99998;
      width: 380px; max-width: calc(100vw - 32px);
      height: 520px; max-height: calc(100vh - 110px);
      background: #fff; border-radius: 14px;
      box-shadow: 0 8px 32px rgba(0,0,0,.22);
      display: flex; flex-direction: column;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px; overflow: hidden;
      transition: opacity .2s, transform .2s;
    }
    #ca-agent-panel.hidden { opacity: 0; pointer-events: none; transform: translateY(12px); }

    #ca-agent-header {
      background: #2563eb; color: #fff;
      padding: 12px 16px; font-weight: 600; font-size: 15px;
      display: flex; align-items: center; gap: 8px; flex-shrink: 0;
    }
    #ca-agent-header span.subtitle {
      font-size: 11px; font-weight: 400; opacity: .8; margin-left: auto;
    }

    #ca-agent-messages {
      flex: 1; overflow-y: auto; padding: 12px 14px;
      display: flex; flex-direction: column; gap: 10px;
    }

    .ca-msg { display: flex; gap: 8px; align-items: flex-start; }
    .ca-msg.user  { flex-direction: row-reverse; }

    .ca-bubble {
      max-width: 82%; padding: 9px 13px; border-radius: 12px;
      line-height: 1.5; white-space: pre-wrap; word-break: break-word;
    }
    .ca-msg.user  .ca-bubble { background: #2563eb; color: #fff; border-bottom-right-radius: 4px; }
    .ca-msg.asst  .ca-bubble { background: #f1f5f9; color: #1e293b; border-bottom-left-radius: 4px; }
    .ca-msg.asst  .ca-bubble.error { background: #fee2e2; color: #991b1b; }

    .ca-avatar {
      width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center; font-size: 14px;
    }
    .ca-msg.user .ca-avatar { background: #dbeafe; }
    .ca-msg.asst .ca-avatar { background: #e0e7ff; }

    .ca-typing { display: flex; gap: 5px; align-items: center; padding: 10px 14px; }
    .ca-typing span {
      width: 7px; height: 7px; border-radius: 50%; background: #94a3b8;
      animation: ca-bounce .9s infinite;
    }
    .ca-typing span:nth-child(2) { animation-delay: .15s; }
    .ca-typing span:nth-child(3) { animation-delay: .30s; }
    @keyframes ca-bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }

    #ca-agent-suggestions {
      display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 14px 0;
    }
    .ca-suggestion {
      background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;
      border-radius: 99px; padding: 4px 11px; font-size: 12px; cursor: pointer;
      transition: background .15s;
    }
    .ca-suggestion:hover { background: #dbeafe; }

    #ca-agent-footer {
      padding: 10px 12px; border-top: 1px solid #e2e8f0;
      display: flex; gap: 8px; flex-shrink: 0;
    }
    #ca-agent-input {
      flex: 1; border: 1px solid #cbd5e1; border-radius: 8px;
      padding: 8px 10px; font-size: 13px; resize: none; outline: none;
      font-family: inherit; line-height: 1.4; max-height: 100px; overflow-y: auto;
    }
    #ca-agent-input:focus { border-color: #2563eb; }
    #ca-agent-send {
      background: #2563eb; color: #fff; border: none; border-radius: 8px;
      padding: 0 14px; cursor: pointer; font-size: 18px; flex-shrink: 0;
      transition: background .2s;
    }
    #ca-agent-send:hover { background: #1d4ed8; }
    #ca-agent-send:disabled { background: #94a3b8; cursor: default; }
  `;

  // ── Initial suggestions ──────────────────────────────────────────────────
  const SUGGESTIONS = [
    'Find all paintings',
    'Show me object 1',
    'Search sculptures',
    'Create new artwork',
  ];

  // ── State ────────────────────────────────────────────────────────────────
  let sessionId = null;
  let open = false;
  let loading = false;

  // ── Build DOM ────────────────────────────────────────────────────────────
  function buildWidget() {
    // Style
    const style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    // Toggle button
    const btn = document.createElement('button');
    btn.id = 'ca-agent-btn';
    btn.title = 'AI Collection Agent';
    btn.textContent = '🤖';
    btn.addEventListener('click', togglePanel);
    document.body.appendChild(btn);

    // Panel
    const panel = document.createElement('div');
    panel.id = 'ca-agent-panel';
    panel.className = 'hidden';
    panel.innerHTML = `
      <div id="ca-agent-header">
        🤖 Collection Agent
        <span class="subtitle">AI · CollectiveAccess</span>
      </div>
      <div id="ca-agent-messages"></div>
      <div id="ca-agent-suggestions"></div>
      <div id="ca-agent-footer">
        <textarea id="ca-agent-input" rows="1"
          placeholder="Ask about your collection…"></textarea>
        <button id="ca-agent-send">➤</button>
      </div>
    `;
    document.body.appendChild(panel);

    // Welcome message
    addMessage('asst', "Hi! I can search, create, update and delete records in this collection.\n\nTry asking me to find artworks, show a record, or create a new object.");
    buildSuggestions();

    // Events
    document.getElementById('ca-agent-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });
    document.getElementById('ca-agent-send').addEventListener('click', send);
  }

  function togglePanel() {
    open = !open;
    const panel = document.getElementById('ca-agent-panel');
    panel.classList.toggle('hidden', !open);
    if (open) setTimeout(() => document.getElementById('ca-agent-input').focus(), 80);
  }

  // ── Suggestions ──────────────────────────────────────────────────────────
  function buildSuggestions() {
    const container = document.getElementById('ca-agent-suggestions');
    container.innerHTML = '';
    SUGGESTIONS.forEach((s) => {
      const chip = document.createElement('button');
      chip.className = 'ca-suggestion';
      chip.textContent = s;
      chip.addEventListener('click', () => {
        document.getElementById('ca-agent-input').value = s;
        container.innerHTML = '';
        send();
      });
      container.appendChild(chip);
    });
  }

  // ── Messages ─────────────────────────────────────────────────────────────
  function addMessage(role, text, isError) {
    const msgs = document.getElementById('ca-agent-messages');
    const row = document.createElement('div');
    row.className = `ca-msg ${role === 'user' ? 'user' : 'asst'}`;

    const avatar = document.createElement('div');
    avatar.className = 'ca-avatar';
    avatar.textContent = role === 'user' ? '👤' : '🤖';

    const bubble = document.createElement('div');
    bubble.className = 'ca-bubble' + (isError ? ' error' : '');
    bubble.textContent = text;

    row.appendChild(avatar);
    row.appendChild(bubble);
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function showTyping() {
    const msgs = document.getElementById('ca-agent-messages');
    const dots = document.createElement('div');
    dots.id = 'ca-typing';
    dots.className = 'ca-msg asst';
    dots.innerHTML = `
      <div class="ca-avatar">🤖</div>
      <div class="ca-bubble ca-typing">
        <span></span><span></span><span></span>
      </div>`;
    msgs.appendChild(dots);
    msgs.scrollTop = msgs.scrollHeight;
  }

  function removeTyping() {
    const el = document.getElementById('ca-typing');
    if (el) el.remove();
  }

  // ── Send ─────────────────────────────────────────────────────────────────
  async function send() {
    const input = document.getElementById('ca-agent-input');
    const message = input.value.trim();
    if (!message || loading) return;

    input.value = '';
    document.getElementById('ca-agent-suggestions').innerHTML = '';
    addMessage('user', message);
    loading = true;
    document.getElementById('ca-agent-send').disabled = true;
    showTyping();

    try {
      const resp = await fetch('/ca-agent-proxy.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
      });

      const data = await resp.json();
      removeTyping();

      if (!resp.ok || data.error) {
        addMessage('asst', data.error || 'Something went wrong. Please try again.', true);
      } else {
        sessionId = data.session_id;
        addMessage('asst', data.reply);
      }
    } catch (err) {
      removeTyping();
      addMessage('asst', 'Network error. Please check your connection and try again.', true);
    } finally {
      loading = false;
      document.getElementById('ca-agent-send').disabled = false;
      input.focus();
    }
  }

  // ── Init ─────────────────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildWidget);
  } else {
    buildWidget();
  }
})();
