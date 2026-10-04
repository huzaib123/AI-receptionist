/*
 * Aura chat widget — drop onto any website with one line:
 *
 *   <script src="https://YOUR-AURA-HOST/widget.js" defer></script>
 *
 * Talks to the same Aura backend that served this script.
 */
(function () {
  if (window.__auraWidgetLoaded) return;
  window.__auraWidgetLoaded = true;

  var script = document.currentScript;
  var API = (script && script.src) ? new URL(script.src).origin : '';
  var SID_KEY = 'aura_widget_session';
  var sid;
  try { sid = localStorage.getItem(SID_KEY); } catch (e) {}
  if (!sid) {
    // Unguessable id, so nobody can continue someone else's conversation.
    var bytes = new Uint8Array(16);
    (window.crypto || window.msCrypto).getRandomValues(bytes);
    sid = 'w_' + Array.prototype.map.call(bytes, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
    try { localStorage.setItem(SID_KEY, sid); } catch (e) {}
  }

  var css = [
    '.aura-w{position:fixed;right:20px;bottom:20px;z-index:2147483000;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}',
    '.aura-w button{font:inherit;cursor:pointer}',
    '.aura-fab{width:58px;height:58px;border-radius:50%;border:0;background:var(--aura-c);color:#fff;box-shadow:0 6px 20px rgba(0,0,0,.25);font-size:26px}',
    '.aura-panel{display:none;position:absolute;right:0;bottom:72px;width:min(360px,calc(100vw - 32px));height:min(520px,calc(100vh - 110px));background:#fff;color:#111;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.25);overflow:hidden;flex-direction:column}',
    '.aura-open .aura-panel{display:flex}',
    '.aura-head{background:var(--aura-c);color:#fff;padding:14px 16px;display:flex;justify-content:space-between;align-items:center}',
    '.aura-head b{display:block;font-size:15px}.aura-head small{opacity:.85;font-size:12px}',
    '.aura-x{background:none;border:0;color:#fff;font-size:20px}',
    '.aura-log{flex:1;overflow-y:auto;padding:14px;background:#f6f7f9;display:flex;flex-direction:column;gap:8px}',
    '.aura-m{max-width:82%;padding:9px 12px;border-radius:14px;font-size:14px;line-height:1.4;white-space:pre-wrap;word-wrap:break-word}',
    '.aura-bot{background:#fff;border:1px solid #e5e7eb;align-self:flex-start}',
    '.aura-me{background:var(--aura-c);color:#fff;align-self:flex-end}',
    '.aura-m a{color:inherit;text-decoration:underline}',
    '.aura-form{display:flex;border-top:1px solid #e5e7eb}',
    '.aura-form input{flex:1;border:0;padding:14px;font-size:14px;outline:none}',
    '.aura-form button{border:0;background:none;color:var(--aura-c);font-weight:600;padding:0 16px}',
    '.aura-wa{display:block;text-align:center;font-size:12px;padding:6px;color:#555;text-decoration:none;border-top:1px solid #eee}'
  ].join('');
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var root = document.createElement('div');
  root.className = 'aura-w';
  root.style.setProperty('--aura-c', '#0f766e');
  root.innerHTML =
    '<div class="aura-panel" role="dialog" aria-label="Chat">' +
      '<div class="aura-head"><div><b class="aura-name">Chat with us</b><small>Usually replies instantly · EN / BM / 中文</small></div>' +
      '<button class="aura-x" aria-label="Close">×</button></div>' +
      '<div class="aura-log" aria-live="polite"></div>' +
      '<form class="aura-form"><input placeholder="Type a message…" aria-label="Message" /><button type="submit">Send</button></form>' +
      '<a class="aura-wa" target="_blank" rel="noopener" style="display:none">Prefer a human? Chat on WhatsApp</a>' +
    '</div>' +
    '<button class="aura-fab" aria-label="Open chat">💬</button>';
  document.body.appendChild(root);

  var log = root.querySelector('.aura-log');
  var input = root.querySelector('input');

  function linkify(text) {
    var esc = text.replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
    return esc.replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  }
  function add(text, who) {
    var m = document.createElement('div');
    m.className = 'aura-m ' + (who === 'me' ? 'aura-me' : 'aura-bot');
    m.innerHTML = linkify(text);
    log.appendChild(m);
    log.scrollTop = log.scrollHeight;
    return m;
  }

  fetch(API + '/api/profile').then(function (r) { return r.json(); }).then(function (p) {
    root.style.setProperty('--aura-c', p.brand_color || '#0f766e');
    root.querySelector('.aura-name').textContent = p.name;
    add('Hi! 👋 Welcome to ' + p.name + '. I can answer questions, share prices and book appointments for you. How can I help?', 'bot');
    if (p.whatsapp_link) {
      var wa = root.querySelector('.aura-wa');
      wa.href = p.whatsapp_link;
      wa.style.display = 'block';
    }
  }).catch(function () { add('Hi! 👋 How can I help you today?', 'bot'); });

  root.querySelector('.aura-fab').onclick = function () {
    root.classList.toggle('aura-open');
    if (root.classList.contains('aura-open')) input.focus();
  };
  root.querySelector('.aura-x').onclick = function () { root.classList.remove('aura-open'); };

  root.querySelector('form').onsubmit = function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    add(text, 'me');
    var typing = add('…', 'bot');
    fetch(API + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, session_id: sid })
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (d) {
      typing.innerHTML = linkify(d.reply);
    }).catch(function () {
      typing.textContent = 'Sorry, something went wrong. Please try again in a moment.';
    });
  };
})();
