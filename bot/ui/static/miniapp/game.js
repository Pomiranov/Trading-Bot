/* CRYPTONITE QUANT HUNTER v3 — Interactive Trading Game */

const QuantHunter = (() => {
  const KEY = 'qf_quant_hunter_v3';
  const MAX_ENERGY = 100;
  const REGEN_RATE = 8;
  const REGEN_MS = 10 * 60 * 1000;

  // ── Sound Engine ─────────────────────────────────────────────────────────
  let _audioCtx = null;
  function _ctx() {
    if (!_audioCtx) { try { _audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(_) {} }
    return _audioCtx;
  }
  function playTone(freq, type = 'sine', dur = 0.12, vol = 0.18) {
    const ctx = _ctx(); if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = type; osc.frequency.value = freq;
      gain.gain.setValueAtTime(vol, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
      osc.start(); osc.stop(ctx.currentTime + dur);
    } catch(_) {}
  }
  function sfxCatch(type) {
    if (type === 'legendary') { playTone(880, 'sine', 0.3, 0.3); setTimeout(() => playTone(1100, 'sine', 0.2, 0.25), 120); }
    else if (type === 'epic')  { playTone(660, 'sine', 0.2, 0.22); }
    else if (type === 'rare')  { playTone(440, 'square', 0.12, 0.18); }
    else                        { playTone(330, 'triangle', 0.08, 0.12); }
  }
  function sfxPowerup() { playTone(550, 'sine', 0.18, 0.25); setTimeout(() => playTone(770, 'sine', 0.18, 0.2), 100); }
  function sfxLevelUp() {
    [440,550,660,880].forEach((f, i) => setTimeout(() => playTone(f, 'sine', 0.25, 0.28), i * 90));
  }
  function sfxMiss() { playTone(180, 'triangle', 0.06, 0.1); }
  function sfxEvent() { playTone(220, 'sawtooth', 0.35, 0.5); }

  // ── Quant Types ───────────────────────────────────────────────────────────
  const QUANT_TYPES = {
    common:    { id:'common',    label:'Common',    pts:1,    color:'#848e9c', glow:'rgba(132,142,156,0.5)', spawnW:0.55, life:4500, size:44, sym:'◇', speed:0.6 },
    rare:      { id:'rare',      label:'Rare',      pts:10,   color:'#3861fb', glow:'rgba(56,97,251,0.6)',   spawnW:0.28, life:3200, size:52, sym:'◆', speed:0.9 },
    epic:      { id:'epic',      label:'Epic',      pts:100,  color:'#8b5cf6', glow:'rgba(139,92,246,0.7)',  spawnW:0.13, life:2400, size:60, sym:'✦', speed:1.3 },
    legendary: { id:'legendary', label:'Legend',    pts:1000, color:'#F7931A', glow:'rgba(247,147,26,0.85)',spawnW:0.04, life:1800, size:68, sym:'★', speed:1.8 },
  };

  // ── Power-up Types ────────────────────────────────────────────────────────
  const POWERUP_TYPES = {
    freeze:     { id:'freeze',     sym:'❄️', label:'FREEZE',      color:'#00c9ff', dur:6000,  desc:'Все квантумы замедлены!' },
    magnet:     { id:'magnet',     sym:'🧲', label:'MAGNET',      color:'#f7c948', dur:4000,  desc:'Авто-захват в радиусе!' },
    multiplier: { id:'multiplier', sym:'⚡', label:'2× BOOST',    color:'#00c076', dur:8000,  desc:'Очки × 2!' },
    bomb:       { id:'bomb',       sym:'💣', label:'MARKET NUKE', color:'#ff4d4d', dur:0,     desc:'Все квантумы пойманы!' },
  };

  // ── Market Events ─────────────────────────────────────────────────────────
  const MARKET_EVENTS = [
    { id:'bull_run',    label:'🐂 BULL RUN!',      color:'#00c076', dur:20000, spawnMult:1.8, rarityBoost:0.15, desc:'Рынок растёт — больше редких квантумов!' },
    { id:'bear_market', label:'🐻 BEAR MARKET',    color:'#ff4d4d', dur:18000, spawnMult:0.7, speedMult:1.5,   desc:'Медвежий рынок — квантумы убегают быстрее!' },
    { id:'market_crash',label:'💥 MARKET CRASH!',  color:'#ff8800', dur:8000,  spawnMult:3.0, rarityBoost:0.3,  desc:'CRASH! Редкие квантумы повсюду — лови!' },
    { id:'ipo_frenzy',  label:'🚀 IPO FRENZY',    color:'#8b5cf6', dur:15000, rareOnly:true,                  desc:'Только редкие+ квантумы спаунятся!' },
    { id:'volatility',  label:'📊 HIGH VOLATILITY',color:'#f7c948', dur:12000, spawnMult:2.2, speedMult:1.8,   desc:'Высокая волатильность — всё быстро!' },
  ];

  // ── Missions ──────────────────────────────────────────────────────────────
  const MISSIONS = [
    { id:'catch50',    label:'Поймай 50 квантумов',   target:50,  field:'sessionCatches', reward:500,  type:'daily' },
    { id:'combo10',    label:'Combo × 10',            target:10,  field:'bestCombo',       reward:300,  type:'daily' },
    { id:'legendary1', label:'Поймай Legendary',      target:1,   field:'legendaryCaught', reward:2000, type:'daily' },
    { id:'powerup5',   label:'Используй 5 Power-ups', target:5,   field:'powerupsUsed',    reward:800,  type:'daily' },
    { id:'catch200',   label:'200 поимок всего',      target:200, field:'totalCatches',    reward:1500, type:'weekly'},
    { id:'event3',     label:'3 рыночных события',    target:3,   field:'eventsWitnessed', reward:1200, type:'weekly'},
  ];

  // ── Achievements ──────────────────────────────────────────────────────────
  const ACHIEVEMENTS = [
    { id:'first',       title:'First Catch',       desc:'Первый квантум',         icon:'🎯', check:s=>s.totalCatches>=1 },
    { id:'hundred',     title:'100 Collected',      desc:'100 поимок',             icon:'💯', check:s=>s.totalCatches>=100 },
    { id:'streak7',     title:'Week Warrior',       desc:'7 дней подряд',          icon:'🗓', check:s=>s.loginStreak>=7 },
    { id:'hunter10',    title:'Quant Hunter',       desc:'Level 10',               icon:'🏹', check:s=>s.level>=10 },
    { id:'legendary',   title:'Legend Collector',   desc:'Первый Legendary',       icon:'⭐', check:s=>s.legendaryCaught>=1 },
    { id:'master',      title:'Quant Master',       desc:'Level 50',               icon:'🏆', check:s=>s.level>=50 },
    { id:'combo20',     title:'Combo King',         desc:'Combo × 20',             icon:'👑', check:s=>s.bestCombo>=20 },
    { id:'powermaster', title:'Power Player',       desc:'50 power-ups',           icon:'⚡', check:s=>s.powerupsUsed>=50 },
    { id:'crashsurvive',title:'Crash Survivor',     desc:'Пережил Market Crash',   icon:'💥', check:s=>s.eventsWitnessed>=1 },
    { id:'predictor',   title:'Market Oracle',      desc:'10 правильных прогнозов',icon:'🔮', check:s=>s.correctPredictions>=10 },
  ];

  const LEVEL_TITLES = [
    {at:1,title:'Crypto Rookie'},{at:5,title:'Market Watcher'},{at:10,title:'Signal Hunter'},
    {at:20,title:'Quant Trader'},{at:35,title:'Alpha Seeker'},{at:50,title:'Quant Master'},
    {at:75,title:'Market Wizard'},{at:100,title:'Crypto Legend'},
  ];

  const defaultState = () => ({
    points:0, level:1, xp:0,
    energy:MAX_ENERGY, lastEnergyTick:Date.now(),
    totalCatches:0, sessionCatches:0, legendaryCaught:0,
    combo:0, bestCombo:0, powerupsUsed:0, eventsWitnessed:0, correctPredictions:0,
    loginStreak:1, lastLoginDate:new Date().toISOString().slice(0,10),
    missionsDone:{}, achievements:{}, unlockedSkins:['default'], activeSkin:'default',
    username:'Hunter', lastDaily:null, missionDay:new Date().toISOString().slice(0,10),
    leaderboard:[{username:'You',level:1,points:0,rank:1}],
    volatility:50,
  });

  let state = _loadState();
  let arena, particles, canvas, ctx;
  let spawnTimer=null, energyTimer=null, eventTimer=null, powerupTimer=null;
  let rafId=null;
  let initialized=false, uid=0;
  let activeQuants = new Map();
  let activePowerups = new Map();
  let currentEvent = null;
  let eventTimeout = null;
  let activePowerupEffects = {};  // { freeze: timeoutId, magnet: timeoutId, ... }
  let magnetInterval = null;

  function _loadState() {
    try {
      const s = { ...defaultState(), ...JSON.parse(localStorage.getItem(KEY)||'{}') };
      _resetDailyMissions(s); _trackLogin(s); _regenEnergy(s);
      return s;
    } catch(_) { return defaultState(); }
  }

  function save() {
    try {
      const you = state.leaderboard.find(e=>e.username==='You'||e.username===state.username);
      if (you) { you.points=state.points; you.level=state.level; }
      else state.leaderboard.unshift({username:state.username,level:state.level,points:state.points,rank:1});
      state.leaderboard.sort((a,b)=>b.points-a.points);
      state.leaderboard.forEach((e,i)=>{e.rank=i+1;});
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch(_) {}
  }

  function _resetDailyMissions(s) {
    const today = new Date().toISOString().slice(0,10);
    if (s.missionDay!==today) {
      s.missionDay=today; s.sessionCatches=0;
      MISSIONS.filter(m=>m.type==='daily').forEach(m=>{delete s.missionsDone[m.id];});
    }
  }

  function _trackLogin(s) {
    const today=new Date().toISOString().slice(0,10);
    const yday=new Date(Date.now()-86400000).toISOString().slice(0,10);
    if (s.lastLoginDate===today) return;
    s.loginStreak = s.lastLoginDate===yday ? (s.loginStreak||0)+1 : 1;
    s.lastLoginDate=today;
  }

  function _regenEnergy(s=state) {
    const now=Date.now();
    const ticks=Math.floor((now-(s.lastEnergyTick||now))/REGEN_MS);
    if (ticks>0) { s.energy=Math.min(MAX_ENERGY, s.energy+ticks*REGEN_RATE); s.lastEnergyTick=now; }
  }

  function xpForLevel(lvl) { return Math.floor(80+lvl*28); }

  function levelTitle(lvl) {
    let t=LEVEL_TITLES[0].title;
    for (const r of LEVEL_TITLES) if(lvl>=r.at) t=r.title;
    return t;
  }

  function haptic(type='light') { window.Telegram?.WebApp?.HapticFeedback?.impactOccurred(type); }
  function toast(msg,type='info') { window.maToast?.(msg,type); }

  // ── Visual FX ─────────────────────────────────────────────────────────────
  function showFloat(x,y,text,color) {
    if(!arena) return;
    const el=document.createElement('div');
    el.className='score-float'; el.textContent=text;
    el.style.cssText=`left:${x}px;top:${y}px;color:${color||'var(--accent)'}`;
    arena.appendChild(el);
    setTimeout(()=>el.remove(), 900);
  }

  function burstParticles(x,y,color,count=18) {
    if(!particles) return;
    for(let i=0;i<count;i++) {
      const p=document.createElement('div');
      p.className='particle'; p.style.background=color;
      p.style.left=x+'px'; p.style.top=y+'px';
      const a=(Math.PI*2*i)/count;
      const d=25+Math.random()*55;
      p.style.setProperty('--tx',Math.cos(a)*d+'px');
      p.style.setProperty('--ty',Math.sin(a)*d+'px');
      particles.appendChild(p);
      setTimeout(()=>p.remove(), 700);
    }
  }

  function screenShake() {
    if(!arena) return;
    arena.classList.add('shake');
    setTimeout(()=>arena.classList.remove('shake'), 400);
  }

  function updateVolatilityMeter() {
    const meter=document.getElementById('volatilityBar');
    if(!meter) return;
    const v=state.volatility||50;
    meter.style.width=v+'%';
    meter.style.background = v>80?'#ff4d4d':v>60?'#f7c948':'#00c076';
  }

  // ── Market Events ─────────────────────────────────────────────────────────
  function triggerMarketEvent() {
    if(currentEvent) return;
    const ev=MARKET_EVENTS[Math.floor(Math.random()*MARKET_EVENTS.length)];
    currentEvent=ev;
    state.eventsWitnessed=(state.eventsWitnessed||0)+1;
    state.volatility=Math.min(100,70+Math.random()*30);
    save();

    const banner=document.getElementById('eventBanner');
    if(banner) {
      banner.textContent=ev.label+' — '+ev.desc;
      banner.style.background=ev.color+'33';
      banner.style.borderColor=ev.color;
      banner.style.color=ev.color;
      banner.classList.add('active');
    }
    sfxEvent();
    toast(ev.label+': '+ev.desc, 'info');
    haptic('heavy');
    updateVolatilityMeter();

    eventTimeout=setTimeout(()=>{
      currentEvent=null;
      state.volatility=Math.max(20,30+Math.random()*30);
      save();
      if(banner) banner.classList.remove('active');
      updateVolatilityMeter();
    }, ev.dur);
  }

  function getSpawnInterval() {
    const base=900;
    const mult=currentEvent?.spawnMult||1;
    return Math.max(300, base/mult);
  }

  // ── Power-ups ─────────────────────────────────────────────────────────────
  function spawnPowerup() {
    if(!arena) return;
    const types=Object.values(POWERUP_TYPES);
    const type=types[Math.floor(Math.random()*types.length)];
    const id=String(++uid);
    const size=64;
    const pad=16;
    const maxX=Math.max(0,arena.clientWidth-size-pad);
    const maxY=Math.max(0,arena.clientHeight-size-pad);

    const el=document.createElement('button');
    el.type='button';
    el.className='powerup-entity';
    el.dataset.qid=id;
    el.dataset.ptype=type.id;
    el.style.cssText=`width:${size}px;height:${size}px;left:${pad+Math.random()*maxX}px;top:${pad+Math.random()*maxY}px;--pu-color:${type.color}`;
    el.innerHTML=`<span class="pu-sym">${type.sym}</span><span class="pu-tag">${type.label}</span>`;

    el.addEventListener('click',e=>{e.stopPropagation();activatePowerup(el,type);});
    arena.appendChild(el);
    activePowerups.set(id,{el,type,born:Date.now()});

    setTimeout(()=>{
      if(el.parentNode){el.classList.add('quant-expire');setTimeout(()=>{el.remove();activePowerups.delete(id);},300);}
    }, 6000);
  }

  function activatePowerup(el, type) {
    el.classList.add('quant-caught');
    setTimeout(()=>el.remove(), 280);
    activePowerups.delete(el.dataset.qid);

    state.powerupsUsed=(state.powerupsUsed||0)+1;
    sfxPowerup();
    haptic('heavy');
    toast(`${type.sym} ${type.label}: ${type.desc}`, 'success');

    const pBar=document.getElementById('powerupStatus');
    if(pBar) { pBar.textContent=`${type.sym} ${type.label} активен!`; pBar.style.color=type.color; pBar.classList.add('active'); }

    if(type.id==='bomb') {
      // Catch all active quants instantly
      const caught=[...activeQuants.values()];
      caught.forEach(q=>{
        if(q.el.parentNode) {
          const rect=q.el.getBoundingClientRect();
          const ar=arena.getBoundingClientRect();
          const x=rect.left-ar.left+rect.width/2;
          const y=rect.top-ar.top+rect.height/2;
          burstParticles(x,y,q.type.color,10);
          state.points+=q.type.pts; state.totalCatches++; state.sessionCatches++;
          q.el.remove();
        }
      });
      activeQuants.clear();
      screenShake();
      save(); renderHud();
    }

    if(type.id==='freeze') {
      activePowerupEffects.freeze=true;
      arena.classList.add('frozen');
      setTimeout(()=>{ activePowerupEffects.freeze=false; arena.classList.remove('frozen');
        if(pBar){pBar.textContent='';pBar.classList.remove('active');} }, type.dur);
    }

    if(type.id==='magnet') {
      activePowerupEffects.magnet=true;
      if(magnetInterval) clearInterval(magnetInterval);
      magnetInterval=setInterval(()=>{
        if(!activePowerupEffects.magnet){clearInterval(magnetInterval);return;}
        const arenaRect=arena?.getBoundingClientRect();
        if(!arenaRect) return;
        const cx=arenaRect.width/2; const cy=arenaRect.height/2;
        activeQuants.forEach((q,id)=>{
          const dist=Math.hypot(parseFloat(q.el.style.left)-cx,parseFloat(q.el.style.top)-cy);
          if(dist<180 && q.el.parentNode) {
            burstParticles(parseFloat(q.el.style.left)+q.type.size/2, parseFloat(q.el.style.top)+q.type.size/2, q.type.color, 8);
            state.points+=q.type.pts; state.totalCatches++; state.sessionCatches++;
            q.el.remove(); activeQuants.delete(id);
          }
        });
        save(); renderHud();
      }, 300);
      setTimeout(()=>{ activePowerupEffects.magnet=false; clearInterval(magnetInterval);
        if(pBar){pBar.textContent='';pBar.classList.remove('active');} }, type.dur);
    }

    if(type.id==='multiplier') {
      activePowerupEffects.multiplier=2;
      setTimeout(()=>{ activePowerupEffects.multiplier=null;
        if(pBar){pBar.textContent='';pBar.classList.remove('active');} }, type.dur);
    }

    checkMissions(); checkAchievements(); save();
  }

  // ── Quant Spawning (moving) ───────────────────────────────────────────────
  function pickQuantType() {
    let weights={...{}};
    for(const [k,v] of Object.entries(QUANT_TYPES)) {
      let w=v.spawnW;
      if(currentEvent?.rarityBoost && k!=='common') w+=currentEvent.rarityBoost;
      if(currentEvent?.rareOnly && k==='common') w=0;
      weights[k]=w;
    }
    const total=Object.values(weights).reduce((a,b)=>a+b,0);
    let r=Math.random()*total, acc=0;
    for(const [k,w] of Object.entries(weights)) { acc+=w; if(r<=acc) return QUANT_TYPES[k]; }
    return QUANT_TYPES.common;
  }

  function spawnQuant() {
    if(!arena) return;
    const type=pickQuantType();
    const id=String(++uid);
    const pad=12;
    const size=type.size;
    const w=arena.clientWidth-size-pad*2;
    const h=arena.clientHeight-size-pad*2;
    const x=pad+Math.random()*Math.max(0,w);
    const y=pad+Math.random()*Math.max(0,h);

    // velocity with event modifiers
    const speedMult=currentEvent?.speedMult||1;
    const frozen=activePowerupEffects.freeze;
    const baseSpeed=type.speed*(frozen?0.2:1)*speedMult;
    const angle=Math.random()*Math.PI*2;
    const vx=Math.cos(angle)*baseSpeed;
    const vy=Math.sin(angle)*baseSpeed;

    const el=document.createElement('button');
    el.type='button';
    el.className=`quant-entity quant-${type.id}`;
    el.dataset.qid=id;
    el.style.cssText=`width:${size}px;height:${size}px;left:${x}px;top:${y}px;--quant-color:${type.color};--quant-glow:${type.glow}`;
    el.innerHTML=`<span class="quant-symbol">${type.sym}</span><span class="quant-tag">${type.label}</span>`;

    el.addEventListener('click',e=>{e.stopPropagation();catchQuant(el,type,id);});
    arena.appendChild(el);

    const lifeLeft=type.life*(currentEvent?.id==='market_crash'?0.6:1);
    activeQuants.set(id,{el,type,x,y,vx,vy,born:Date.now(),life:lifeLeft});

    setTimeout(()=>{
      if(el.parentNode){el.classList.add('quant-expire');setTimeout(()=>{el.remove();activeQuants.delete(id);missQuant();},300);}
    }, lifeLeft);
  }

  // ── Physics loop ──────────────────────────────────────────────────────────
  let lastPhysics=0;
  function physicsLoop(ts) {
    rafId=requestAnimationFrame(physicsLoop);
    if(!arena||!activeQuants.size) { lastPhysics=ts; return; }
    const dt=Math.min(ts-lastPhysics, 50);
    lastPhysics=ts;
    const W=arena.clientWidth, H=arena.clientHeight;

    activeQuants.forEach(q=>{
      if(!q.el.parentNode){activeQuants.delete(q.el.dataset?.qid);return;}
      const frozen=activePowerupEffects.freeze;
      const mult=frozen?0.2:1;
      q.x+=q.vx*mult*dt*0.05;
      q.y+=q.vy*mult*dt*0.05;
      const s=q.type.size;
      if(q.x<0){q.x=0;q.vx=-q.vx;}
      if(q.y<0){q.y=0;q.vy=-q.vy;}
      if(q.x>W-s){q.x=W-s;q.vx=-q.vx;}
      if(q.y>H-s){q.y=H-s;q.vy=-q.vy;}
      q.el.style.left=q.x+'px';
      q.el.style.top=q.y+'px';
    });
    bgT+=0.008; drawBg();
  }

  // ── Catch logic ───────────────────────────────────────────────────────────
  function catchQuant(el, type, id) {
    _regenEnergy();
    if(state.energy<=0 && !activePowerupEffects.magnet) {
      toast('Нет энергии! Подождите '+Math.ceil(REGEN_MS/60000)+' мин.','warn');
      haptic('rigid'); return;
    }
    if(!activePowerupEffects.magnet) state.energy--;

    state.combo++;
    if(state.combo>state.bestCombo) state.bestCombo=state.combo;
    const comboMult=Math.min(1+state.combo*0.08, 2.5);
    const ptMult=activePowerupEffects.multiplier||1;
    const reward=Math.round(type.pts*comboMult*ptMult);

    state.points+=reward; state.totalCatches++; state.sessionCatches++;
    if(type.id==='legendary'){state.legendaryCaught++;screenShake();}

    const qData=activeQuants.get(id);
    const cx=qData?qData.x+type.size/2:parseFloat(el.style.left)+type.size/2;
    const cy=qData?qData.y+type.size/2:parseFloat(el.style.top)+type.size/2;

    burstParticles(cx,cy,type.color, type.id==='legendary'?30:18);
    showFloat(cx,cy-16,`+${reward}${state.combo>2?` ×${state.combo}`:''}`, type.color);
    sfxCatch(type.id); haptic(type.id==='legendary'?'heavy':'medium');

    el.classList.add('quant-caught');
    setTimeout(()=>{el.remove();},280);
    activeQuants.delete(id);

    addXp(Math.max(5,Math.floor(type.pts/5)));
    checkMissions(); checkAchievements(); save(); renderHud();
  }

  function missQuant() { state.combo=0; renderHud(); sfxMiss(); }

  function addXp(amount) {
    state.xp+=amount;
    while(state.xp>=xpForLevel(state.level)) {
      state.xp-=xpForLevel(state.level);
      state.level++;
      burstParticles(arena?.clientWidth/2||150,arena?.clientHeight/2||200,'#8b5cf6',40);
      sfxLevelUp(); haptic('heavy');
      toast(`🎉 Level Up! ${state.level} — ${levelTitle(state.level)}`,'success');
      if(state.level>=10&&!state.unlockedSkins.includes('holo-blue')) state.unlockedSkins.push('holo-blue');
      if(state.level>=50&&!state.unlockedSkins.includes('holo-gold')) state.unlockedSkins.push('holo-gold');
    }
    save(); renderHud(); checkAchievements();
  }

  // ── Chart Prediction mini-game ─────────────────────────────────────────────
  let predictionActive=false;
  function triggerChartPrediction() {
    if(predictionActive) return;
    predictionActive=true;

    const overlay=document.getElementById('predictionOverlay');
    if(!overlay) { predictionActive=false; return; }

    // Generate simple fake chart data (5 candles)
    const candles=[]; let price=100+Math.random()*200;
    for(let i=0;i<6;i++) {
      const ch=(Math.random()-0.48)*price*0.04;
      candles.push({o:price, c:price+ch, h:price+Math.abs(ch)*1.5, l:price-Math.abs(ch)*1.5});
      price+=ch;
    }
    const answer=candles[5].c>candles[4].c?'up':'down';

    // Draw mini chart
    const cvs=document.getElementById('predChart');
    if(cvs) {
      const c=cvs.getContext('2d');
      const W=cvs.width=overlay.querySelector('.pred-chart-wrap').clientWidth||260;
      const H=cvs.height=100;
      c.clearRect(0,0,W,H);
      const prices=candles.slice(0,5);
      const minP=Math.min(...prices.map(x=>x.l));
      const maxP=Math.max(...prices.map(x=>x.h));
      const scale=H*0.8/(maxP-minP||1);
      const cw=W/prices.length;
      prices.forEach((cd,i)=>{
        const x=i*cw+cw*0.2;
        const isUp=cd.c>=cd.o;
        c.strokeStyle=isUp?'#00c076':'#ff4d4d'; c.fillStyle=isUp?'#00c076':'#ff4d4d';
        c.lineWidth=1;
        // wick
        c.beginPath();
        c.moveTo(x+cw*0.3, H*0.1+(maxP-cd.h)*scale);
        c.lineTo(x+cw*0.3, H*0.1+(maxP-cd.l)*scale);
        c.stroke();
        // body
        const top=H*0.1+(maxP-Math.max(cd.o,cd.c))*scale;
        const bot=H*0.1+(maxP-Math.min(cd.o,cd.c))*scale;
        c.fillRect(x, top, cw*0.6, Math.max(2,bot-top));
      });
      // "?" candle
      c.fillStyle='rgba(139,92,246,0.3)'; c.strokeStyle='#8b5cf6';
      c.setLineDash([4,4]);
      c.strokeRect(prices.length*cw+cw*0.1, H*0.2, cw*0.6, H*0.6);
      c.setLineDash([]);
      c.fillStyle='#8b5cf6'; c.font='bold 14px Inter';
      c.fillText('?', prices.length*cw+cw*0.3, H*0.62);
    }

    overlay.classList.add('active');
    const tickers=['SBER','GAZP','LKOH','NVTK'];
    overlay.querySelector('.pred-ticker').textContent=tickers[Math.floor(Math.random()*tickers.length)]+' · 5M';

    const onChoice=(choice)=>{
      overlay.classList.remove('active');
      predictionActive=false;
      const correct=choice===answer;
      if(correct) {
        state.correctPredictions=(state.correctPredictions||0)+1;
        const bonus=200+state.level*10;
        state.points+=bonus;
        addXp(30);
        toast(`✅ Верно! +${bonus} pts`, 'success');
        sfxPowerup();
      } else {
        toast(`❌ Неверно (было ${answer==='up'?'📈':'📉'})`, 'warn');
        sfxMiss();
      }
      checkMissions(); checkAchievements(); save(); renderHud();
      document.getElementById('predUpBtn').onclick=null;
      document.getElementById('predDownBtn').onclick=null;
    };

    document.getElementById('predUpBtn').onclick=()=>onChoice('up');
    document.getElementById('predDownBtn').onclick=()=>onChoice('down');

    // Auto-close after 10s
    setTimeout(()=>{ if(predictionActive){overlay.classList.remove('active');predictionActive=false;} }, 10000);
  }

  // ── Daily Reward ──────────────────────────────────────────────────────────
  function dailyReward() {
    const today=new Date().toISOString().slice(0,10);
    if(state.lastDaily===today){toast('Daily reward уже получен сегодня','warn');return;}
    state.lastDaily=today;
    const bonus=150+state.level*20;
    state.points+=bonus; state.energy=Math.min(MAX_ENERGY,state.energy+40);
    addXp(80);
    toast(`🎁 Daily Reward: +${bonus} pts, +40 energy!`,'success');
    screenShake();
    save(); renderHud();
  }

  // ── Mission / Achievement checks ──────────────────────────────────────────
  function checkMissions() {
    MISSIONS.forEach(m=>{
      if(state.missionsDone[m.id]) return;
      const val=state[m.field]??0;
      if(val>=m.target) {
        state.missionsDone[m.id]=true;
        if(m.reward) state.points+=m.reward;
        toast(`✅ Миссия: ${m.label} +${m.reward||'Skin'}`,'success');
        sfxLevelUp(); save();
      }
    });
    renderMissions();
  }

  function checkAchievements() {
    let any=false;
    ACHIEVEMENTS.forEach(a=>{
      if(!state.achievements[a.id]&&a.check(state)) {
        state.achievements[a.id]=true;
        toast(`🏆 Achievement: ${a.icon} ${a.title}`,'success');
        any=true;
      }
    });
    if(any){save();renderAchievements();}
  }

  // ── Render functions ──────────────────────────────────────────────────────
  function renderHud() {
    _regenEnergy();
    const set=(id,v)=>{ const el=document.getElementById(id); if(el) el.textContent=String(v); };
    set('gamePoints', state.points.toLocaleString());
    set('gameLevel', state.level);
    set('gameXp', `${state.xp}/${xpForLevel(state.level)}`);
    set('gameEnergy', `${state.energy}/${MAX_ENERGY}`);
    set('gameTitle', levelTitle(state.level));

    const combo=document.getElementById('gameCombo');
    if(combo) { combo.textContent=state.combo>1?`COMBO ×${state.combo}`:''; combo.style.color=state.combo>9?'#F7931A':state.combo>4?'#8b5cf6':'#3861fb'; }

    const bar=document.getElementById('energyBar');
    if(bar) bar.style.width=(state.energy/MAX_ENERGY*100)+'%';
    const xpBar=document.getElementById('xpBar');
    if(xpBar) xpBar.style.width=(state.xp/xpForLevel(state.level)*100)+'%';

    updateVolatilityMeter();
  }

  function renderMissions() {
    const el=document.getElementById('missionsList');
    if(!el) return;
    el.innerHTML=MISSIONS.map(m=>{
      const val=state[m.field]??0;
      const done=state.missionsDone[m.id];
      const pct=Math.min(100,Math.round(val/m.target*100));
      const badge=m.type==='weekly'?'<span class="mission-badge weekly">weekly</span>':'';
      return `<div class="mission-card ${done?'done':''}">
        <div class="mission-top"><span>${m.label}${badge}</span><span class="mission-reward">+${m.reward||'Skin'}</span></div>
        <div class="mission-bar"><div class="mission-bar-fill" style="width:${pct}%"></div></div>
        <div class="mission-prog">${Math.min(val,m.target)}/${m.target}${done?' ✓':''}</div>
      </div>`;
    }).join('');
  }

  function renderAchievements() {
    const el=document.getElementById('achievements');
    if(!el) return;
    el.innerHTML=ACHIEVEMENTS.map(a=>`
      <div class="ach-card ${state.achievements[a.id]?'unlocked':''}">
        <span class="ach-icon">${a.icon}</span>
        <strong>${a.title}</strong><span>${a.desc}</span>
      </div>`).join('');
  }

  function renderLeaderboard() {
    const el=document.getElementById('leaderboard');
    if(!el) return;
    const bots=[
      {username:'AlphaQuant',baseLevel:8},{username:'MoonTrader',baseLevel:15},
      {username:'SigmaBot',baseLevel:22},{username:'CryptoKing',baseLevel:35},
      {username:'DeFiHunter',baseLevel:12},{username:'QuantMaster',baseLevel:45},
      {username:'BullSeeker',baseLevel:28},{username:'BearSlayer',baseLevel:19},
    ];
    const board=[...state.leaderboard];
    bots.forEach((b,i)=>{
      if(!board.find(e=>e.username===b.username))
        board.push({username:b.username, level:b.baseLevel, points:Math.floor(state.points*(0.6+i*0.1+Math.random()*0.4)),rank:0});
    });
    board.sort((a,b)=>b.points-a.points);
    board.forEach((e,i)=>{e.rank=i+1;});
    el.innerHTML=board.slice(0,10).map(e=>`
      <div class="lb-row ${e.username===state.username||e.username==='You'?'lb-you':''}">
        <span class="lb-rank">${e.rank<=3?['🥇','🥈','🥉'][e.rank-1]:'#'+e.rank}</span>
        <span class="lb-user">${e.username}</span>
        <span class="lb-lvl">Lv.${e.level}</span>
        <span class="lb-pts">${e.points.toLocaleString()}</span>
      </div>`).join('');
  }

  // ── Game loops ────────────────────────────────────────────────────────────
  function startLoops() {
    stopLoops();
    // Adaptive spawn interval
    const scheduleSpawn=()=>{
      if(!initialized) return;
      spawnQuant();
      spawnTimer=setTimeout(scheduleSpawn, getSpawnInterval());
    };
    scheduleSpawn();

    energyTimer=setInterval(()=>{ _regenEnergy(); renderHud(); }, 30000);

    // Power-up spawns every 15-25s
    const schedulePowerup=()=>{
      if(!initialized) return;
      spawnPowerup();
      powerupTimer=setTimeout(schedulePowerup, 15000+Math.random()*10000);
    };
    powerupTimer=setTimeout(schedulePowerup, 12000);

    // Market events every 35-65s
    const scheduleEvent=()=>{
      if(!initialized) return;
      triggerMarketEvent();
      eventTimer=setTimeout(scheduleEvent, 35000+Math.random()*30000);
    };
    eventTimer=setTimeout(scheduleEvent, 25000);

    // Chart prediction every 50-90s
    const schedulePrediction=()=>{
      if(!initialized) return;
      triggerChartPrediction();
      setTimeout(schedulePrediction, 50000+Math.random()*40000);
    };
    setTimeout(schedulePrediction, 40000);

    rafId=requestAnimationFrame(physicsLoop);
  }

  function stopLoops() {
    clearTimeout(spawnTimer); clearInterval(energyTimer);
    clearTimeout(powerupTimer); clearTimeout(eventTimer);
    if(eventTimeout){clearTimeout(eventTimeout);eventTimeout=null;currentEvent=null;}
    if(magnetInterval){clearInterval(magnetInterval);magnetInterval=null;}
    if(rafId){cancelAnimationFrame(rafId);rafId=null;}
    activeQuants.forEach(({el})=>el?.remove()); activeQuants.clear();
    activePowerups.forEach(({el})=>el?.remove()); activePowerups.clear();
    activePowerupEffects={};
  }

  // ── Background canvas ─────────────────────────────────────────────────────
  let bgT=0;
  function drawBg() {
    if(!ctx||!canvas||canvas.width<=0) return;
    const W=canvas.width, H=canvas.height;
    ctx.clearRect(0,0,W,H);
    // Dynamic gradient based on current event
    const eventColor=currentEvent?currentEvent.color:'rgba(139,92,246,0.07)';
    const grd=ctx.createRadialGradient(W/2,H/2,0,W/2,H/2,W*0.6);
    grd.addColorStop(0, eventColor+'22');
    grd.addColorStop(1,'transparent');
    ctx.fillStyle=grd; ctx.fillRect(0,0,W,H);
    // Floating dots
    for(let i=0;i<40;i++) {
      const x=(Math.sin(bgT+i*0.7)*0.5+0.5)*W;
      const y=(Math.cos(bgT*0.6+i*0.4)*0.5+0.5)*H;
      const r=0.8+Math.sin(bgT*1.2+i)*0.4;
      ctx.beginPath(); ctx.arc(x,y,r,0,Math.PI*2);
      ctx.fillStyle=`rgba(56,97,251,${0.06+Math.sin(bgT+i)*0.04})`; ctx.fill();
    }
    // Grid lines (subtle)
    ctx.strokeStyle='rgba(56,97,251,0.04)'; ctx.lineWidth=1;
    for(let x=0;x<W;x+=40) {ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}
    for(let y=0;y<H;y+=40) {ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
  }

  // ── Init / Destroy ────────────────────────────────────────────────────────
  function init() {
    arena=document.getElementById('gameArena');
    particles=document.getElementById('particles');
    canvas=document.getElementById('gameCanvas');

    if(!initialized) {
      initialized=true;
      if(canvas&&arena) {
        ctx=canvas.getContext('2d');
        const resize=()=>{
          canvas.width=arena.clientWidth||300;
          canvas.height=arena.clientHeight||280;
        };
        resize(); window.addEventListener('resize',resize);
      }
      arena?.addEventListener('click',e=>{
        if(e.target===arena||e.target===canvas) missQuant();
      });
      document.getElementById('dailyRewardBtn')?.addEventListener('click',dailyReward);
      document.getElementById('leaderboardBtn')?.addEventListener('click',()=>{
        const p=document.getElementById('leaderboardPanel');
        if(p){p.hidden=!p.hidden;if(!p.hidden)renderLeaderboard();}
      });
      document.getElementById('predictionOverlay')?.querySelectorAll('.pred-close').forEach(b=>{
        b.addEventListener('click',()=>{
          document.getElementById('predictionOverlay')?.classList.remove('active');
          predictionActive=false;
        });
      });
      // Manual prediction trigger for testing
      document.getElementById('chartPredBtn')?.addEventListener('click',()=>triggerChartPrediction());

      const name=window.Telegram?.WebApp?.initDataUnsafe?.user?.first_name;
      if(name){state.username=name;save();}
    }

    renderHud(); renderMissions(); renderAchievements();
    startLoops();
    lastPhysics=performance.now();
  }

  function destroy() {
    initialized=false;
    stopLoops();
    const banner=document.getElementById('eventBanner');
    if(banner) banner.classList.remove('active');
    const pBar=document.getElementById('powerupStatus');
    if(pBar){pBar.textContent='';pBar.classList.remove('active');}
    const overlay=document.getElementById('predictionOverlay');
    if(overlay) overlay.classList.remove('active');
    predictionActive=false;
  }

  return {init,destroy,getState:()=>state,QUANT_TYPES,POWERUP_TYPES,MARKET_EVENTS};
})();

window.QuantHunter=QuantHunter;
window.CryptoniteGame=QuantHunter;
