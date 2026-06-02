// ============================ BACKGROUND CANVAS ============================
// Floating connected-particle network behind the page.
(function () {
  const c = document.getElementById('bg-canvas');
  if (!c) return;
  const ctx = c.getContext('2d');
  let W = (c.width = innerWidth);
  let H = (c.height = innerHeight);
  const DPR = Math.min(devicePixelRatio || 1, 2);
  function resize() {
    W = innerWidth; H = innerHeight;
    c.width = W * DPR; c.height = H * DPR; c.style.width = W + 'px'; c.style.height = H + 'px';
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  resize();
  addEventListener('resize', resize);

  const N = Math.min(110, Math.floor((W * H) / 22000));
  const pts = Array.from({ length: N }, () => ({
    x: Math.random() * W, y: Math.random() * H,
    vx: (Math.random() - 0.5) * 0.25, vy: (Math.random() - 0.5) * 0.25,
    r: Math.random() * 1.6 + 0.4,
    hue: Math.random() < 0.5 ? 195 : 265,
  }));

  const mouse = { x: -1e9, y: -1e9 };
  addEventListener('mousemove', e => { mouse.x = e.clientX; mouse.y = e.clientY; });

  function tick() {
    ctx.clearRect(0, 0, W, H);
    for (const p of pts) {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > W) p.vx *= -1;
      if (p.y < 0 || p.y > H) p.vy *= -1;
      // attract slightly toward mouse
      const dx = mouse.x - p.x, dy = mouse.y - p.y; const d2 = dx*dx + dy*dy;
      if (d2 < 30000) { p.vx += dx * 0.000004; p.vy += dy * 0.000004; }
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${p.hue}, 85%, 70%, 0.7)`;
      ctx.fill();
    }
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const a = pts[i], b = pts[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx*dx + dy*dy;
        if (d2 < 18000) {
          const alpha = (1 - d2 / 18000) * 0.22;
          ctx.strokeStyle = `hsla(220, 80%, 70%, ${alpha})`;
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(tick);
  }
  tick();
})();

// ============================ SCROLL REVEAL ============================
(function () {
  const els = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) {
    els.forEach(e => e.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver(entries => {
    for (const ent of entries) {
      if (ent.isIntersecting) {
        ent.target.classList.add('in');
        io.unobserve(ent.target);
      }
    }
  }, { threshold: 0.12 });
  els.forEach(e => io.observe(e));
})();

// ============================ COUNTERS ============================
(function () {
  const els = document.querySelectorAll('[data-counter]');
  if (!els.length) return;
  const animate = el => {
    const end = parseFloat(el.dataset.counter);
    const suf = el.dataset.suffix || '';
    const dur = 1400; const start = performance.now();
    const step = now => {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      const v = Math.round(end * eased);
      el.textContent = v + suf;
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const io = new IntersectionObserver(es => {
    for (const e of es) if (e.isIntersecting) { animate(e.target); io.unobserve(e.target); }
  }, { threshold: 0.5 });
  els.forEach(e => io.observe(e));
})();

// ============================ BAR GROWTH ============================
(function () {
  const bars = document.querySelectorAll('.bar > div[data-w]');
  if (!bars.length) return;
  const io = new IntersectionObserver(es => {
    for (const e of es) if (e.isIntersecting) {
      e.target.style.width = e.target.dataset.w + '%';
      io.unobserve(e.target);
    }
  }, { threshold: 0.4 });
  bars.forEach(b => io.observe(b));
})();

// ============================ CARD MOUSE GLOW ============================
(function () {
  document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('mousemove', e => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${e.clientX - r.left}px`);
      card.style.setProperty('--my', `${e.clientY - r.top}px`);
    });
  });
})();

// ============================ SERVER LIST ============================
async function loadServers() {
  const el = document.getElementById('servers-list');
  el.innerHTML = '<div class="server-row"><span>Загрузка…</span></div>';
  try {
    const r = await fetch('/api/servers');
    const data = await r.json();
    if (!data.length) {
      el.innerHTML = '<div class="server-row"><span>(нет публичных серверов)</span></div>';
      return;
    }
    el.innerHTML = data.map((s, i) => `
      <div class="server-row" style="animation-delay:${i * 0.06}s">
        <div class="who">
          <b>#${s.id} · ${escapeHtml(s.name)}</b>
          <span>${escapeHtml(s.description || 'нет описания')}</span>
        </div>
        <div class="count"><span class="live"></span>${s.online}/${s.max_users}</div>
      </div>
    `).join('');
  } catch (e) {
    el.innerHTML = '<div class="server-row"><span>Ошибка: ' + escapeHtml(e.message) + '</span></div>';
  }
}

async function createServer(ev) {
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const body = {
    name: fd.get('name'),
    description: fd.get('description'),
    public: true,
    max_users: parseInt(fd.get('max_users') || '64', 10),
  };
  const out = document.getElementById('create-result');
  out.textContent = 'Создание…';
  try {
    const r = await fetch('/api/servers', {
      method: 'POST', headers: {'content-type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'ошибка');
    out.textContent =
      `✓ Сервер #${data.id} создан.\n` +
      `Admin token (сохрани, без него нельзя управлять):\n${data.admin_token}\n\n` +
      `В клиенте выбери его в списке и заходи.`;
    loadServers();
  } catch (e) {
    out.textContent = 'Ошибка: ' + e.message;
  }
  return false;
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

loadServers();
setInterval(loadServers, 15000);

// ============================ SMOOTH SCROLL ============================
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const t = document.querySelector(a.getAttribute('href'));
    if (t) { e.preventDefault(); t.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
});
