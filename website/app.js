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
    { dur: 10000, build(s) {                      // 5 · what you get
        line(s, 'Свои серверы', 'lg', 0.0);
        line(s, 'Свои каналы', 'lg', 0.7);
        line(s, 'Только твой звук', 'lg glow', 1.4);
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

  if (sessionStorage.getItem('pt_intro_seen')) {
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
// EMBER SPARKS canvas — warm particles drifting upward with flicker
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

  const N = Math.min(90, Math.floor((W * H) / 26000));
  const rnd = (a, b) => a + Math.random() * (b - a);
  function mk(seed) {
    return {
      x: rnd(0, W),
      y: seed ? rnd(0, H) : H + rnd(0, 60),
      r: rnd(0.6, 2.6),
      vy: rnd(0.2, 0.9),
      vx: rnd(-0.25, 0.25),
      life: rnd(0, 1),
      hue: rnd(12, 32),          // orange→amber
      tw: rnd(0.01, 0.04),
    };
  }
  const ps = Array.from({ length: N }, () => mk(true));
  const mouse = { x: -1e9, y: -1e9 };
  addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });

  function tick() {
    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < ps.length; i++) {
      const p = ps[i];
      p.y -= p.vy; p.x += p.vx + Math.sin(p.y * 0.01) * 0.3;
      p.life += p.tw;
      // gentle repel from cursor
      const dx = p.x - mouse.x, dy = p.y - mouse.y, d2 = dx * dx + dy * dy;
      if (d2 < 12000) { p.x += dx / d2 * 60; p.y += dy / d2 * 60; }
      if (p.y < -10 || p.x < -20 || p.x > W + 20) Object.assign(p, mk(false));
      const flick = 0.55 + 0.45 * Math.sin(p.life * 6.283);
      const r = p.r * (0.8 + 0.4 * flick);
      const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 4);
      g.addColorStop(0, `hsla(${p.hue}, 100%, 65%, ${0.9 * flick})`);
      g.addColorStop(1, `hsla(${p.hue}, 100%, 50%, 0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r * 4, 0, 6.283);
      ctx.fill();
    }
    ctx.globalCompositeOperation = 'source-over';
    requestAnimationFrame(tick);
  }
  tick();
})();

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

// smooth-scroll for in-page anchors
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const id = a.getAttribute('href');
    if (id.length < 2) return;
    const t = document.querySelector(id);
    if (t) { e.preventDefault(); t.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
});
