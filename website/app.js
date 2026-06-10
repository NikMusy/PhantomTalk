// =====================================================================
//  PhantomTalk landing — cinematic intro, ember sparks, kinetic type
// =====================================================================

// ---------------------------------------------------------------------
// CINEMATIC INTRO — ~60s scene-by-scene explainer with kinetic typography
// ---------------------------------------------------------------------
(function () {
  const intro = document.getElementById('intro');
  if (!intro) return;
  const stage  = document.getElementById('intro-stage');
  const bar    = document.getElementById('intro-progress-bar');
  const skip   = document.getElementById('intro-skip');
  const replay = document.getElementById('replay-intro');
  const flash  = intro.querySelector('.intro-flash');
  const sweep  = intro.querySelector('.intro-sweep');

  let timers = [];
  let idx = 0;
  let running = false;

  const T = (fn, ms) => { const id = setTimeout(fn, ms); timers.push(id); return id; };
  const clearAll = () => { timers.forEach(clearTimeout); timers = []; };

  // Build a line whose letters drop in column-by-column (3D flip + blur).
  function line(parent, text, cls, baseDelay) {
    const el = document.createElement('div');
    el.className = 'line ' + (cls || '');
    parent.appendChild(el);
    let li = 0;
    [...text].forEach(ch => {
      if (ch === ' ') { const sp = document.createElement('span'); sp.className = 'sp'; el.appendChild(sp); return; }
      const s = document.createElement('span');
      s.className = 'l'; s.textContent = ch;
      s.style.animationDelay = ((baseDelay || 0) + li * 0.045) + 's';
      el.appendChild(s);
      li++;
    });
    return el;
  }

  // ----- the scene script (durations sum to ~60s) -----
  const SCENES = [
    { dur: 8000, build(s) {                       // 1 · cold open
        line(s, 'PhantomTalk', 'xl glow', 0.3);
        line(s, 'голос · который · слышно', 'sub', 1.3);
    }},
    { dur: 9000, build(s) {                       // 2 · the problem
        line(s, 'Твой голос', 'lg', 0.0);
        line(s, 'в Discord', 'lg', 0.5);
        line(s, 'сжат до хрипа', 'lg dim', 1.0);
        line(s, '64 кбит/с · моно', 'sub', 1.9);
    }},
    { dur: 8000, build(s) {                       // 3 · the turn
        line(s, 'Хватит.', 'xl', 0.0);
        line(s, 'Слушай по-настоящему', 'lg glow', 0.9);
    }},
    { dur: 11000, build(s) {                      // 4 · the number
        const n = document.createElement('div'); n.className = 'big-num'; n.textContent = '0'; s.appendChild(n);
        T(() => {
          const t0 = performance.now(), d = 1500;
          const step = now => { const t = Math.min(1, (now - t0) / d); n.textContent = Math.round(510 * (1 - Math.pow(1 - t, 3))); if (t < 1) requestAnimationFrame(step); };
          requestAnimationFrame(step);
        }, 350);
        line(s, 'кбит/с · stereo', 'md glow', 1.5);
        line(s, '× 5 к голосу Discord', 'sub', 2.2);
    }},
    { dur: 9000, build(s) {                       // 5 · what you get
        line(s, 'Свои серверы', 'lg', 0.0);
        line(s, 'Свои каналы', 'lg', 0.7);
        line(s, 'Только твой звук', 'lg glow', 1.4);
    }},
    { dur: 8500, build(s) {                       // 5.5 · Russia
        const flag = document.createElement('div'); flag.className = 'ru-flag';
        flag.innerHTML = '<i class="b-white"></i><i class="b-blue"></i><i class="b-red"></i>';
        s.appendChild(flag);
        line(s, 'Работает в РФ', 'lg glow', 0.2);
        line(s, 'без VPN · без блокировок · твоя инфраструктура', 'sub', 1.2);
    }},
    { dur: 7000, build(s) {                       // 6 · tech
        const c = document.createElement('div'); c.className = 'chips'; s.appendChild(c);
        ['Opus', 'UDP-relay', '0 пересжатий', 'self-hosted'].forEach((t, i) => {
          const d = document.createElement('div'); d.className = 'ichip'; d.textContent = t;
          d.style.animationDelay = (0.15 + i * 0.18) + 's'; c.appendChild(d);
        });
    }},
    { dur: 7000, build(s) {                       // 7 · logo finale
        line(s, 'PhantomTalk', 'xl glow', 0.2);
        line(s, 'голос, который слышно', 'sub', 1.4);
    }},
  ];

  const fire = (el) => { if (!el) return; el.classList.remove('go'); void el.offsetWidth; el.classList.add('go'); };

  function runScene() {
    if (idx >= SCENES.length) { finish(); return; }
    const sc = SCENES[idx++];
    stage.innerHTML = '';
    const node = document.createElement('div'); node.className = 'scene';
    stage.appendChild(node);
    sc.build(node);
    void node.offsetWidth;
    fire(flash); fire(sweep);
    T(() => node.classList.add('leaving'), sc.dur - 650);
    T(runScene, sc.dur);
  }

  function startBar(total) {
    if (!bar) return;
    bar.style.transition = 'none'; bar.style.width = '0'; void bar.offsetWidth;
    bar.style.transition = 'width ' + total + 'ms linear'; bar.style.width = '100%';
  }

  function finish() {
    if (!running && intro.classList.contains('gone')) return;
    clearAll(); running = false;
    intro.classList.add('gone');
    document.body.classList.remove('intro-lock');
    setTimeout(() => { intro.style.display = 'none'; }, 1100);
  }

  function play() {
    clearAll(); running = true; idx = 0;
    sessionStorage.setItem('pt_intro_seen', '1');
    intro.style.display = 'flex';
    intro.classList.remove('gone');
    intro.classList.add('lit');
    document.body.classList.add('intro-lock');
    const total = SCENES.reduce((a, b) => a + b.dur, 0);
    startBar(total);
    runScene();
  }

  skip && skip.addEventListener('click', finish);
  window.addEventListener('keydown', e => { if (e.key === 'Escape' && running) finish(); });
  replay && replay.addEventListener('click', e => { e.preventDefault(); play(); });

  // screenshot helper: ?scene=N — freeze intro scene N at its final state
  const sceneParam = new URLSearchParams(location.search).get('scene');
  if (sceneParam !== null) {
    const st = document.createElement('style');
    st.textContent = `
      #intro * { animation: none !important; transition: none !important; }
      #intro .line .l { opacity:1 !important; transform:none !important; filter:none !important; }
      #intro .ichip   { opacity:1 !important; transform:none !important; filter:none !important; }
      #intro .big-num { opacity:1 !important; transform:none !important; filter:none !important; }
      #intro .ru-flag { opacity:.6 !important; transform:translate(-50%,-50%) rotate(-3deg) skewX(-3deg) !important; }
      #intro .intro-rings span { opacity:.45 !important; }`;
    document.head.appendChild(st);
    intro.style.display = 'flex';
    intro.classList.remove('gone'); intro.classList.add('lit');
    document.body.classList.add('intro-lock');
    const n = Math.max(0, Math.min(SCENES.length - 1, parseInt(sceneParam, 10) || 0));
    stage.innerHTML = '';
    const node = document.createElement('div'); node.className = 'scene';
    stage.appendChild(node);
    const realST = window.setTimeout;          // mute scene-internal timers (counter anim)
    window.setTimeout = () => 0;
    SCENES[n].build(node);
    window.setTimeout = realST;
    const big = node.querySelector('.big-num'); if (big) big.textContent = '510';
    if (bar) bar.style.width = (((n + 1) / SCENES.length) * 100) + '%';
    return;
  }

  const noIntro = new URLSearchParams(location.search).has('nointro');
  if (noIntro || sessionStorage.getItem('pt_intro_seen')) {
    intro.style.display = 'none';
    intro.classList.add('gone');
    document.body.classList.remove('intro-lock');
  } else {
    play();
  }
})();

// ---------------------------------------------------------------------
// KINETIC HEADLINE — split into words, glow tokens wrapped in |glow:..|
// ---------------------------------------------------------------------
(function () {
  document.querySelectorAll('[data-kin]').forEach(h => {
    const raw = h.textContent.trim();
    h.textContent = '';
    // tokens like "|glow:слышно|" become glowing words
    const parts = raw.split(/(\|glow:[^|]+\|)/g).filter(Boolean);
    let idx = 0;
    parts.forEach(part => {
      const m = part.match(/^\|glow:(.+)\|$/);
      const words = (m ? m[1] : part).split(/(\s+)/);
      words.forEach(w => {
        if (/^\s+$/.test(w)) { h.appendChild(document.createTextNode(w)); return; }
        if (w === '') return;
        const span = document.createElement('span');
        span.className = 'w' + (m ? ' glow' : '');
        span.textContent = w;
        span.style.animationDelay = (0.15 + idx * 0.12) + 's';
        h.appendChild(span);
        idx++;
      });
    });
  });
})();

// ---------------------------------------------------------------------
// EMBER SPARKS canvas — sprite-blitted particles (fast), FPS-adaptive
// ---------------------------------------------------------------------
(function () {
  const c = document.getElementById('bg-canvas');
  if (!c) return;
  const ctx = c.getContext('2d');
  const DPR = Math.min(devicePixelRatio || 1, 2);
  let W, H;
  function resize() {
    W = innerWidth; H = innerHeight;
    c.width = W * DPR; c.height = H * DPR; c.style.width = W + 'px'; c.style.height = H + 'px';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  resize();
  addEventListener('resize', resize);

  // Pre-render the spark glow once; per-frame we only drawImage (way cheaper
  // than building a radial gradient for every particle every frame).
  const SPR = 64;
  const sprites = [12, 22, 32].map(hue => {
    const oc = document.createElement('canvas'); oc.width = oc.height = SPR;
    const og = oc.getContext('2d');
    const g = og.createRadialGradient(SPR/2, SPR/2, 0, SPR/2, SPR/2, SPR/2);
    g.addColorStop(0, `hsla(${hue},100%,72%,1)`);
    g.addColorStop(0.25, `hsla(${hue},100%,60%,.55)`);
    g.addColorStop(1, `hsla(${hue},100%,50%,0)`);
    og.fillStyle = g; og.fillRect(0, 0, SPR, SPR);
    return oc;
  });

  let MAX = Math.min(64, Math.floor((W * H) / 34000));
  const rnd = (a, b) => a + Math.random() * (b - a);
  function mk(seed) {
    return {
      x: rnd(0, W), y: seed ? rnd(0, H) : H + rnd(0, 60),
      r: rnd(2.5, 9), vy: rnd(0.25, 1.0), vx: rnd(-0.25, 0.25),
      life: rnd(0, 1), tw: rnd(0.008, 0.035),
      spr: sprites[(Math.random() * sprites.length) | 0],
    };
  }
  const ps = Array.from({ length: MAX }, () => mk(true));
  const mouse = { x: -1e9, y: -1e9 };
  addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; }, { passive: true });

  // FPS adaptive: if frames take >22ms on average, thin the swarm.
  let emaDt = 16, lastT = performance.now(), skip = false;

  function tick(now) {
    // sparks drift slowly — drawing at 30fps halves the cost invisibly
    skip = !skip;
    if (skip) { requestAnimationFrame(tick); return; }
    const dt = now - lastT; lastT = now;
    emaDt += (dt - emaDt) * 0.06;
    if (emaDt > 44 && ps.length > 24) ps.splice(0, 3);

    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < ps.length; i++) {
      const p = ps[i];
      p.y -= p.vy; p.x += p.vx + Math.sin(p.y * 0.01) * 0.3;
      p.life += p.tw;
      const dx = p.x - mouse.x, dy = p.y - mouse.y, d2 = dx * dx + dy * dy;
      if (d2 < 12000) { p.x += dx / d2 * 60; p.y += dy / d2 * 60; }
      if (p.y < -12 || p.x < -24 || p.x > W + 24) Object.assign(p, mk(false));
      const flick = 0.55 + 0.45 * Math.sin(p.life * 6.283);
      const s = p.r * (1.4 + 0.8 * flick);
      ctx.globalAlpha = 0.45 + 0.55 * flick;
      ctx.drawImage(p.spr, p.x - s / 2, p.y - s / 2, s, s);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
})();

// ---------------------------------------------------------------------
// 3D TILT on cards (transform-only, rAF-throttled — no layout thrash)
// ---------------------------------------------------------------------
(function () {
  const sel = '.card, .eco-card, .bar-card, .ai-chip';
  let raf = 0;
  document.querySelectorAll(sel).forEach(card => {
    let rx = 0, ry = 0, tx = 0, ty = 0, hovering = false;
    function apply() {
      raf = 0;
      card.style.transform = hovering
        ? `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-6px)`
        : '';
    }
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      ry = px * 7; rx = -py * 7; hovering = true;
      card.style.transition = 'transform .08s ease-out';
      if (!raf) raf = requestAnimationFrame(apply);
    }, { passive: true });
    card.addEventListener('mouseleave', () => {
      hovering = false;
      card.style.transition = 'transform .45s cubic-bezier(.2,.8,.2,1)';
      if (!raf) raf = requestAnimationFrame(apply);
    });
  });
})();

// ---------------------------------------------------------------------
// PARALLAX hero orb — follows cursor softly
// ---------------------------------------------------------------------
(function () {
  const art = document.querySelector('.hero-art');
  if (!art) return;
  let tx = 0, ty = 0, cx = 0, cy = 0, running = false;
  addEventListener('mousemove', e => {
    tx = (e.clientX / innerWidth - 0.5) * 26;
    ty = (e.clientY / innerHeight - 0.5) * 18;
    if (!running) { running = true; requestAnimationFrame(step); }
  }, { passive: true });
  function step() {
    cx += (tx - cx) * 0.06; cy += (ty - cy) * 0.06;
    art.style.transform = `translate(${cx.toFixed(2)}px, ${cy.toFixed(2)}px)`;
    if (Math.abs(tx - cx) > 0.05 || Math.abs(ty - cy) > 0.05) requestAnimationFrame(step);
    else running = false;
  }
})();

// ---------------------------------------------------------------------
// LIVE WEB CHAT — global lobby over WebSocket
// ---------------------------------------------------------------------
const webchat = (function () {
  const log = document.getElementById('chat-log');
  if (!log) return null;
  const nickEl = document.getElementById('chat-nick');
  const onlineEl = document.getElementById('chat-online');
  let ws = null, myNick = localStorage.getItem('pt_nick') || '';
  if (myNick) nickEl.value = myNick;

  function fmt(ts) {
    const d = new Date((ts || 0) * 1000);
    return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
  }
  function addMsg(m, mine) {
    const el = document.createElement('div');
    el.className = 'chat-msg' + (mine ? ' mine' : '');
    el.innerHTML = `<span class="nick">${escapeHtml(m.nick)}</span>${escapeHtml(m.text)}<span class="time">${fmt(m.ts)}</span>`;
    log.appendChild(el);
    while (log.children.length > 120) log.removeChild(log.firstChild);
    log.scrollTop = log.scrollHeight;
  }
  function sys(text) {
    const el = document.createElement('div');
    el.className = 'chat-msg sys'; el.textContent = text;
    log.appendChild(el); log.scrollTop = log.scrollHeight;
  }

  // demo fill for screenshots: ?demo=1
  if (new URLSearchParams(location.search).has('demo')) {
    const now = Date.now() / 1000;
    [['NikMusy', 'здарова бандиты, это наш чат прямо на сайте 🔥', 300],
     ['кент', 'звук реально чище дискорда, я в шоке', 240],
     ['Claude Fable', 'анимации полировал всю ночь, заценили?', 120],
     ['гость-42', 'как поднять свой сервер? а, вижу кнопку сверху', 30],
    ].forEach(([nick, text, ago]) => addMsg({ nick, text, ts: now - ago }, nick === 'NikMusy'));
    if (onlineEl) onlineEl.textContent = '· онлайн: 4';
    return { send() {} };
  }

  function connect() {
    if (sessionStorage.getItem('pt_block_ws')) { sys('чат на паузе (debug)'); return; }
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    try { ws = new WebSocket(`${proto}://${location.host}/ws/webchat`); }
    catch (e) { sys('чат недоступен'); return; }
    ws.onopen = () => { log.innerHTML = ''; sys('ты в чате — пиши!'); };
    ws.onmessage = ev => {
      let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.type === 'history') {
        (m.messages || []).forEach(x => addMsg(x, x.nick === myNick));
        if (onlineEl) onlineEl.textContent = `· онлайн: ${m.online}`;
      } else if (m.type === 'chat') {
        addMsg(m, m.nick === myNick);
      } else if (m.type === 'online' && onlineEl) {
        onlineEl.textContent = `· онлайн: ${m.online}`;
      }
    };
    ws.onclose = () => { sys('переподключение…'); setTimeout(connect, 3000); };
  }
  connect();

  return {
    send(text) {
      myNick = (nickEl.value || '').trim() || ('гость-' + Math.floor(Math.random() * 999));
      nickEl.value = myNick;
      localStorage.setItem('pt_nick', myNick);
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'chat', nick: myNick, text }));
    }
  };
})();

function webchatSend(ev) {
  ev.preventDefault();
  const t = document.getElementById('chat-text');
  const text = t.value.trim();
  if (text && webchat) { webchat.send(text); t.value = ''; }
  return false;
}

// ---------------------------------------------------------------------
// SCROLL REVEAL
// ---------------------------------------------------------------------
(function () {
  const els = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) { els.forEach(e => e.classList.add('in')); return; }
  const io = new IntersectionObserver(es => {
    for (const e of es) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }, { threshold: 0.12 });
  els.forEach(e => io.observe(e));
})();

// ---------------------------------------------------------------------
// COUNTERS
// ---------------------------------------------------------------------
(function () {
  const els = document.querySelectorAll('[data-counter]');
  if (!els.length) return;
  const run = el => {
    const end = parseFloat(el.dataset.counter), suf = el.dataset.suffix || '';
    const dur = 1500, t0 = performance.now();
    const step = now => {
      const t = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(end * e) + suf;
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const io = new IntersectionObserver(es => {
    for (const e of es) if (e.isIntersecting) { run(e.target); io.unobserve(e.target); }
  }, { threshold: 0.5 });
  els.forEach(e => io.observe(e));
})();

// ---------------------------------------------------------------------
// BAR GROWTH
// ---------------------------------------------------------------------
(function () {
  const bars = document.querySelectorAll('.bar > div[data-w]');
  if (!bars.length) return;
  const io = new IntersectionObserver(es => {
    for (const e of es) if (e.isIntersecting) { e.target.style.width = e.target.dataset.w + '%'; io.unobserve(e.target); }
  }, { threshold: 0.4 });
  bars.forEach(b => io.observe(b));
})();

// ---------------------------------------------------------------------
// CARD MOUSE GLOW
// ---------------------------------------------------------------------
(function () {
  document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${e.clientX - r.left}px`);
      card.style.setProperty('--my', `${e.clientY - r.top}px`);
    });
  });
})();

// ---------------------------------------------------------------------
// SERVER LIST + CREATE
// ---------------------------------------------------------------------
async function loadServers() {
  const el = document.getElementById('servers-list');
  el.innerHTML = '<div class="server-row"><span>Загрузка…</span></div>';
  try {
    const r = await fetch('/api/servers');
    const data = await r.json();
    if (!data.length) { el.innerHTML = '<div class="server-row"><span>(нет публичных серверов)</span></div>'; return; }
    el.innerHTML = data.map((s, i) => `
      <div class="server-row" style="animation-delay:${i * 0.06}s">
        <div class="who">
          <b>#${s.id} · ${escapeHtml(s.name)}</b>
          <span>${escapeHtml(s.description || 'нет описания')}</span>
        </div>
        <div class="count"><span class="live"></span>${s.online}/${s.max_users}</div>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = '<div class="server-row"><span>Ошибка: ' + escapeHtml(e.message) + '</span></div>';
  }
}

async function createServer(ev) {
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const body = { name: fd.get('name'), description: fd.get('description'), public: true, max_users: parseInt(fd.get('max_users') || '64', 10) };
  const out = document.getElementById('create-result');
  out.textContent = 'Создание…';
  try {
    const r = await fetch('/api/servers', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'ошибка');
    out.textContent = `✓ Сервер #${data.id} создан.\nAdmin token (сохрани, без него нельзя управлять):\n${data.admin_token}\n\nВ клиенте выбери его в списке и заходи.`;
    loadServers();
  } catch (e) { out.textContent = 'Ошибка: ' + e.message; }
  return false;
}

function escapeHtml(s) { return (s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

loadServers();
setInterval(loadServers, 15000);

// screenshot helper: ?goto=<section id> — instant jump + force reveal
(function () {
  const target = new URLSearchParams(location.search).get('goto');
  if (!target) return;
  function go() {
    const st = document.createElement('style');
    st.textContent = '*{transition:none!important;}';
    document.head.appendChild(st);
    document.querySelectorAll('.reveal').forEach(e => e.classList.add('in'));
    document.querySelectorAll('.bar > div[data-w]').forEach(b => b.style.width = b.dataset.w + '%');
    document.querySelectorAll('[data-counter]').forEach(e => e.textContent = e.dataset.counter + (e.dataset.suffix || ''));
    // headless can't screenshot a scrolled page — hide everything except the target
    const el = document.getElementById(target);
    if (el) {
      document.querySelectorAll('main > section').forEach(s => { if (s !== el) s.style.display = 'none'; });
      const nav = document.querySelector('.nav'); if (nav) nav.style.display = 'none';
    }
  }
  if (document.readyState === 'complete') setTimeout(go, 300);
  else addEventListener('load', () => setTimeout(go, 300));
})();

// smooth-scroll for in-page anchors
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const id = a.getAttribute('href');
    if (id.length < 2) return;
    const t = document.querySelector(id);
    if (t) { e.preventDefault(); t.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
});
