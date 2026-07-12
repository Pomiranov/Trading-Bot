/* CRYPTONITE QUANT HUNTER — Virtual gamification */

const QuantHunter = (() => {
  const KEY = 'qf_quant_hunter_v2';
  const MAX_ENERGY = 100;
  const ENERGY_REGEN = 10;
  const REGEN_MS = 10 * 60 * 1000;

  const QUANT_TYPES = {
    common:    { id: 'common',    label: 'Common',    points: 1,    color: '#848e9c', glow: 'rgba(132,142,156,0.5)',  spawn: 0.55, lifetime: 4000, size: 44, symbol: '◇' },
    rare:      { id: 'rare',      label: 'Rare',      points: 10,   color: '#3861fb', glow: 'rgba(56,97,251,0.6)',    spawn: 0.28, lifetime: 2800, size: 52, symbol: '◆' },
    epic:      { id: 'epic',      label: 'Epic',      points: 100,  color: '#8b5cf6', glow: 'rgba(139,92,246,0.7)',   spawn: 0.14, lifetime: 2000, size: 60, symbol: '✦' },
    legendary: { id: 'legendary', label: 'Legendary', points: 1000, color: '#f0b90b', glow: 'rgba(240,185,11,0.85)', spawn: 0.03, lifetime: 1500, size: 68, symbol: '★' },
  };

  const LEVEL_TITLES = [
    { at: 1, title: 'Crypto Rookie' },
    { at: 10, title: 'Market Hunter' },
    { at: 25, title: 'Signal Seeker' },
    { at: 50, title: 'Quant Master' },
    { at: 100, title: 'Crypto Legend' },
  ];

  const MISSIONS = [
    { id: 'catch50', label: 'Catch 50 Quant', target: 50, field: 'sessionCatches', reward: 500, type: 'daily' },
    { id: 'catch200', label: 'Catch 200 Quant', target: 200, field: 'totalCatches', reward: 1500, type: 'daily' },
    { id: 'legendary1', label: 'Catch Legendary Quant', target: 1, field: 'legendaryCaught', reward: 2000, type: 'daily' },
    { id: 'login7', label: 'Login 7 days streak', target: 7, field: 'loginStreak', reward: 0, rewardSkin: 'holo-rare', type: 'weekly' },
  ];

  const ACHIEVEMENTS = [
    { id: 'first', title: 'First Catch', desc: 'Поймай первый Quant', check: s => s.totalCatches >= 1 },
    { id: 'hundred', title: '100 Quant Collected', desc: '100 поимок всего', check: s => s.totalCatches >= 100 },
    { id: 'streak7', title: '7 Days Active', desc: '7 дней подряд', check: s => s.loginStreak >= 7 },
    { id: 'hunter', title: 'Quant Hunter', desc: 'Достигни Level 10', check: s => s.level >= 10 },
    { id: 'legendary', title: 'Legendary Collector', desc: 'Поймай Legendary', check: s => s.legendaryCaught >= 1 },
    { id: 'master', title: 'Quant Master', desc: 'Level 50', check: s => s.level >= 50 },
  ];

  const defaultState = () => ({
    points: 0, level: 1, xp: 0,
    energy: MAX_ENERGY, lastEnergyTick: Date.now(),
    totalCatches: 0, sessionCatches: 0, legendaryCaught: 0,
    combo: 0, bestCombo: 0,
    loginStreak: 1, lastLoginDate: new Date().toISOString().slice(0, 10),
    missionsDone: {}, achievements: {}, unlockedSkins: ['default'],
    activeSkin: 'default',
    username: 'Hunter',
    leaderboard: [{ username: 'You', level: 1, points: 0, rank: 1 }],
    missionDay: new Date().toISOString().slice(0, 10),
  });

  let state = load();
  let arena, particles, canvas, ctx, spawnTimer, energyTimer, activeQuants = new Map();
  let initialized = false;
  let uid = 0;

  function load() {
    try {
      const s = { ...defaultState(), ...JSON.parse(localStorage.getItem(KEY) || '{}') };
      resetDailyMissionsIfNeeded(s);
      trackLogin(s);
      regenEnergy(s);
      return s;
    } catch (_) { return defaultState(); }
  }

  function save() {
    localStorage.setItem(KEY, JSON.stringify(state));
    const you = state.leaderboard.find(e => e.username === 'You' || e.username === state.username);
    if (you) { you.points = state.points; you.level = state.level; }
    else state.leaderboard.unshift({ username: state.username, level: state.level, points: state.points, rank: 1 });
    state.leaderboard.sort((a, b) => b.points - a.points);
    state.leaderboard.forEach((e, i) => { e.rank = i + 1; });
  }

  function resetDailyMissionsIfNeeded(s) {
    const today = new Date().toISOString().slice(0, 10);
    if (s.missionDay !== today) {
      s.missionDay = today;
      s.sessionCatches = 0;
      MISSIONS.filter(m => m.type === 'daily').forEach(m => { delete s.missionsDone[m.id]; });
    }
  }

  function trackLogin(s) {
    const today = new Date().toISOString().slice(0, 10);
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
    if (s.lastLoginDate === today) return;
    if (s.lastLoginDate === yesterday) s.loginStreak = (s.loginStreak || 0) + 1;
    else s.loginStreak = 1;
    s.lastLoginDate = today;
  }

  function regenEnergy(s = state) {
    const now = Date.now();
    const elapsed = now - (s.lastEnergyTick || now);
    const ticks = Math.floor(elapsed / REGEN_MS);
    if (ticks > 0) {
      s.energy = Math.min(MAX_ENERGY, s.energy + ticks * ENERGY_REGEN);
      s.lastEnergyTick = now;
    }
  }

  function xpForLevel(lvl) { return Math.floor(80 + lvl * 25); }

  function levelTitle(lvl) {
    let t = LEVEL_TITLES[0].title;
    for (const row of LEVEL_TITLES) if (lvl >= row.at) t = row.title;
    return t;
  }

  function pickQuantType() {
    const r = Math.random();
    let acc = 0;
    for (const t of Object.values(QUANT_TYPES)) {
      acc += t.spawn;
      if (r <= acc) return t;
    }
    return QUANT_TYPES.common;
  }

  function haptic(type = 'light') {
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(type);
  }

  function toast(msg, type = 'info') { window.maToast?.(msg, type); }

  function showFloat(x, y, text, color) {
    if (!arena) return;
    const el = document.createElement('div');
    el.className = 'score-float';
    el.textContent = text;
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.style.color = color || 'var(--accent)';
    arena.appendChild(el);
    setTimeout(() => el.remove(), 1000);
  }

  function burstParticles(x, y, color) {
    if (!particles) return;
    for (let i = 0; i < 18; i++) {
      const p = document.createElement('div');
      p.className = 'particle';
      p.style.background = color;
      p.style.left = x + 'px';
      p.style.top = y + 'px';
      const a = (Math.PI * 2 * i) / 18;
      const d = 30 + Math.random() * 45;
      p.style.setProperty('--tx', Math.cos(a) * d + 'px');
      p.style.setProperty('--ty', Math.sin(a) * d + 'px');
      particles.appendChild(p);
      setTimeout(() => p.remove(), 750);
    }
  }

  function addXp(amount) {
    state.xp += amount;
    while (state.xp >= xpForLevel(state.level)) {
      state.xp -= xpForLevel(state.level);
      state.level++;
      burstParticles(arena.clientWidth / 2, arena.clientHeight / 2, '#8b5cf6');
      haptic('heavy');
      toast(`Level Up! ${state.level} — ${levelTitle(state.level)}`, 'success');
      if (state.level >= 10 && !state.unlockedSkins.includes('holo-blue')) state.unlockedSkins.push('holo-blue');
      if (state.level >= 50 && !state.unlockedSkins.includes('holo-gold')) state.unlockedSkins.push('holo-gold');
    }
    save();
    renderHud();
    checkAchievements();
  }

  function catchQuant(el, type) {
    regenEnergy();
    if (state.energy <= 0) {
      toast('Нет энергии! Подождите восстановления', 'warn');
      haptic('rigid');
      return;
    }

    state.energy--;
    state.combo++;
    if (state.combo > state.bestCombo) state.bestCombo = state.combo;
    const comboMult = 1 + Math.min(state.combo * 0.05, 0.75);
    const reward = Math.round(type.points * comboMult);
    state.points += reward;
    state.totalCatches++;
    state.sessionCatches++;
    if (type.id === 'legendary') state.legendaryCaught++;

    const rect = el.getBoundingClientRect();
    const arenaRect = arena.getBoundingClientRect();
    const x = rect.left - arenaRect.left + rect.width / 2;
    const y = rect.top - arenaRect.top + rect.height / 2;

    burstParticles(x, y, type.color);
    showFloat(x, y - 10, `+${reward}${state.combo > 2 ? ` x${state.combo}` : ''}`, type.color);
    haptic(type.id === 'legendary' ? 'heavy' : 'medium');

    el.classList.add('quant-caught');
    setTimeout(() => el.remove(), 280);
    activeQuants.delete(el.dataset.qid);

    addXp(Math.max(5, Math.floor(type.points / 5)));
    checkMissions();
    checkAchievements();
    save();
    renderHud();
    renderMissions();
  }

  function missQuant() {
    state.combo = 0;
    renderHud();
  }

  function spawnQuant() {
    if (!arena || state.energy <= 0) return;
    const type = pickQuantType();
    const id = String(++uid);
    const pad = 16;
    const size = type.size;
    const maxX = Math.max(0, arena.clientWidth - size - pad);
    const maxY = Math.max(0, arena.clientHeight - size - pad);

    const el = document.createElement('button');
    el.type = 'button';
    el.className = `quant-entity quant-${type.id}`;
    el.dataset.qid = id;
    el.style.width = size + 'px';
    el.style.height = size + 'px';
    el.style.left = pad + Math.random() * maxX + 'px';
    el.style.top = pad + Math.random() * maxY + 'px';
    el.style.setProperty('--quant-color', type.color);
    el.style.setProperty('--quant-glow', type.glow);
    el.innerHTML = `<span class="quant-symbol">${type.symbol}</span><span class="quant-tag">${type.label}</span>`;

    el.addEventListener('click', e => { e.stopPropagation(); catchQuant(el, type); });
    arena.appendChild(el);
    activeQuants.set(id, { el, type, born: Date.now() });

    setTimeout(() => {
      if (el.parentNode) {
        el.classList.add('quant-expire');
        setTimeout(() => { el.remove(); activeQuants.delete(id); missQuant(); }, 300);
      }
    }, type.lifetime);
  }

  function checkMissions() {
    MISSIONS.forEach(m => {
      if (state.missionsDone[m.id]) return;
      const val = state[m.field] ?? 0;
      if (val >= m.target) {
        state.missionsDone[m.id] = true;
        if (m.reward) state.points += m.reward;
        if (m.rewardSkin) state.unlockedSkins.push(m.rewardSkin);
        toast(`Mission: ${m.label} +${m.reward || 'Skin'}`, 'success');
        save();
      }
    });
  }

  function checkAchievements() {
    ACHIEVEMENTS.forEach(a => {
      if (!state.achievements[a.id] && a.check(state)) {
        state.achievements[a.id] = true;
        toast(`Achievement: ${a.title}`, 'success');
      }
    });
    save();
    renderAchievements();
  }

  function dailyReward() {
    const today = new Date().toISOString().slice(0, 10);
    if (state.lastDaily === today) { toast('Daily reward уже получен', 'warn'); return; }
    state.lastDaily = today;
    const bonus = 100 + state.level * 15;
    state.points += bonus;
    state.energy = Math.min(MAX_ENERGY, state.energy + 30);
    addXp(50);
    toast(`Daily +${bonus} pts, +30 energy`, 'success');
    save();
    renderHud();
  }

  function renderHud() {
    regenEnergy();
    const set = (id, v) => document.getElementById(id)?.replaceChildren(document.createTextNode(String(v)));
    set('gamePoints', state.points);
    set('gameLevel', state.level);
    set('gameXp', `${state.xp}/${xpForLevel(state.level)}`);
    set('gameEnergy', `${state.energy}/${MAX_ENERGY}`);
    set('gameTitle', levelTitle(state.level));
    set('gameCombo', state.combo > 1 ? `COMBO x${state.combo}` : '');

    const bar = document.getElementById('energyBar');
    if (bar) bar.style.width = (state.energy / MAX_ENERGY * 100) + '%';

    const xpBar = document.getElementById('xpBar');
    if (xpBar) xpBar.style.width = (state.xp / xpForLevel(state.level) * 100) + '%';
  }

  function renderMissions() {
    const el = document.getElementById('missionsList');
    if (!el) return;
    el.innerHTML = MISSIONS.map(m => {
      const val = state[m.field] ?? 0;
      const done = state.missionsDone[m.id];
      const pct = Math.min(100, Math.round(val / m.target * 100));
      return `<div class="mission-card ${done ? 'done' : ''}">
        <div class="mission-top"><span>${m.label}</span><span class="mission-reward">+${m.reward || 'Skin'}</span></div>
        <div class="mission-bar"><div class="mission-bar-fill" style="width:${pct}%"></div></div>
        <div class="mission-prog">${Math.min(val, m.target)}/${m.target}</div>
      </div>`;
    }).join('');
  }

  function renderAchievements() {
    const el = document.getElementById('achievements');
    if (!el) return;
    el.innerHTML = ACHIEVEMENTS.map(a => `
      <div class="ach-card ${state.achievements[a.id] ? 'unlocked' : ''}">
        <strong>${a.title}</strong><span>${a.desc}</span>
      </div>`).join('');
  }

  function renderLeaderboard() {
    const el = document.getElementById('leaderboard');
    if (!el) return;
    const bots = ['AlphaQuant', 'MoonTrader', 'SigmaBot', 'CryptoKing', 'DeFiHunter'];
    const board = [...state.leaderboard];
    while (board.length < 8) {
      const name = bots[board.length % bots.length];
      board.push({ username: name, level: 5 + board.length * 3, points: Math.floor(state.points * (0.8 + Math.random() * 0.6)), rank: 0 });
    }
    board.sort((a, b) => b.points - a.points);
    board.forEach((e, i) => { e.rank = i + 1; });
    el.innerHTML = board.slice(0, 10).map(e => `
      <div class="lb-row ${e.username === state.username || e.username === 'You' ? 'lb-you' : ''}">
        <span class="lb-rank">#${e.rank}</span>
        <span class="lb-user">${e.username}</span>
        <span class="lb-lvl">Lv.${e.level}</span>
        <span class="lb-pts">${e.points}</span>
      </div>`).join('');
  }

  function startLoops() {
    if (spawnTimer) clearInterval(spawnTimer);
    spawnTimer = setInterval(spawnQuant, 900);
    if (energyTimer) clearInterval(energyTimer);
    energyTimer = setInterval(() => { regenEnergy(); renderHud(); }, 30000);
  }

  function stopLoops() {
    clearInterval(spawnTimer);
    clearInterval(energyTimer);
    activeQuants.forEach(({ el }) => el.remove());
    activeQuants.clear();
  }

  function init() {
    arena = document.getElementById('gameArena');
    particles = document.getElementById('particles');
    canvas = document.getElementById('gameCanvas');

    if (!initialized) {
      initialized = true;
      if (canvas && arena) {
        ctx = canvas.getContext('2d');
        const resize = () => { canvas.width = arena.clientWidth; canvas.height = arena.clientHeight; };
        resize();
        window.addEventListener('resize', resize);
        animateBg();
      }
      arena?.addEventListener('click', e => {
        if (e.target === arena || e.target === canvas) missQuant();
      });
      document.getElementById('dailyRewardBtn')?.addEventListener('click', dailyReward);
      document.getElementById('leaderboardBtn')?.addEventListener('click', () => {
        const p = document.getElementById('leaderboardPanel');
        if (p) { p.hidden = !p.hidden; if (!p.hidden) renderLeaderboard(); }
      });
      const name = window.Telegram?.WebApp?.initDataUnsafe?.user?.first_name;
      if (name) { state.username = name; save(); }
    }

    renderHud();
    renderMissions();
    renderAchievements();
    startLoops();
  }

  function destroy() { stopLoops(); }

  let bgT = 0;
  function animateBg() {
    if (!ctx || !canvas) return;
    bgT += 0.012;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const grd = ctx.createRadialGradient(canvas.width / 2, canvas.height / 2, 0, canvas.width / 2, canvas.height / 2, canvas.width * 0.7);
    grd.addColorStop(0, 'rgba(139,92,246,0.08)');
    grd.addColorStop(1, 'transparent');
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < 30; i++) {
      const x = (Math.sin(bgT + i * 0.5) * 0.5 + 0.5) * canvas.width;
      const y = (Math.cos(bgT * 0.7 + i * 0.3) * 0.5 + 0.5) * canvas.height;
      ctx.beginPath();
      ctx.arc(x, y, 1 + Math.sin(bgT + i) * 0.5, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(56,97,251,${0.08 + Math.sin(bgT + i) * 0.05})`;
      ctx.fill();
    }
    requestAnimationFrame(animateBg);
  }

  return { init, destroy, getState: () => state, QUANT_TYPES };
})();

window.QuantHunter = QuantHunter;
window.CryptoniteGame = QuantHunter;