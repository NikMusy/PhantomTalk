// =====================================================================
//  PhantomTalk landing — cinematic intro, ember sparks, kinetic type
// =====================================================================

// ---------------------------------------------------------------------
// CINEMATIC INTRO
// ---------------------------------------------------------------------
(function () {
  const intro = document.getElementById('intro');
  const wordEl = intro ? intro.querySelector('.intro-word') : null;
  const skip = document.getElementById('intro-skip');
  const replay = document.getElementById('replay-intro');
  if (!intro || !wordEl) return;

  // build the wordmark char-by-char with staggered bloom
  function buildWord() {
    const word = wordEl.dataset.word || 'PhantomTalk';
    wordEl.innerHTML = '';
    [...word].forEach((c, i) => {
      const s = document.createElement('span');
      s.className = 'ch';
      // make "Talk" tail bolder/amber via <b> grouping not needed; color handled by gradient
      s.textContent = c;
      s.style.animationDelay = (0.6 + i * 0.06) + 's';
      wordEl.appendChild(s);
    });
  }

  function end() {
    if (intro.classList.contains('gone')) return;
    intro.classList.add('gone');
    document.body.classList.remove('intro-lock');
    setTimeout(() => { intro.style.display = 'none'; }, 1100);
  }

  function play() {
    intro.style.display = 'flex';
    intro.classList.remove('gone');
    document.body.classList.add('intro-lock');
    // restart ring/orb/flare animations by reflow
    intro.querySelectorAll('.intro-rings span, .intro-orb, .intro-flare, .intro-tag, .intro-skip')
      .forEach(el => { el.style.animation = 'none'; void el.offsetWidth; el.style.animation = ''; });
    buildWord();
    clearTimeout(play._t);
    play._t = setTimeout(end, 4200);
  }

  skip && skip.addEventListener('click', end);
  intro.addEventListener('click', end);
  window.addEventListener('keydown', e => { if (e.key === 'Escape' || e.key === ' ') end(); }, { once: true });
  replay && replay.addEventListener('click', e => { e.preventDefault(); play(); });

  // Play once per browser session; instantly dismiss on later loads.
  if (sessionStorage.getItem('pt_intro_seen')) {
    intro.style.display = 'none';
    intro.classList.add('gone');
    document.body.classList.remove('intro-lock');
  } else {
    sessionStorage.setItem('pt_intro_seen', '1');
    buildWord();
    play._t = setTimeout(end, 4200);
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
