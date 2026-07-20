/* QuantFlow — Progressive visual enhancements (additive only, no functional deps) */
(function () {
  'use strict';

  /* ── Risk gauge sync: reads #metDrawdown text, drives #riskGauge conic fill ── */
  function syncRiskGauge() {
    const label = document.getElementById('metDrawdown');
    const gauge = document.getElementById('riskGauge');
    if (!label || !gauge) return;
    const raw = parseFloat((label.textContent || '').replace(',', '.').replace(/[^\d.-]/g, ''));
    const dd = isNaN(raw) ? 0 : Math.abs(raw);
    const fillPct = Math.max(4, Math.min(dd / 20 * 100, 100));
    let color = 'var(--qf-long)';
    if (dd >= 15) color = 'var(--qf-short)';
    else if (dd >= 6) color = 'var(--qf-accent)';
    gauge.style.setProperty('--gauge-value', fillPct.toFixed(1));
    gauge.style.setProperty('--gauge-color', color);
  }

  const ddLabel = document.getElementById('metDrawdown');
  if (ddLabel) {
    new MutationObserver(syncRiskGauge).observe(ddLabel, { childList: true, characterData: true, subtree: true });
    syncRiskGauge();
  }

  /* ── Collapsed-sidebar tooltips (body-level portal, escapes overflow clipping) ── */
  const tooltipEl = document.createElement('div');
  tooltipEl.className = 'qf-tooltip';
  document.body.appendChild(tooltipEl);

  function showTooltip(target) {
    if (!document.body.classList.contains('sidebar-collapsed')) return;
    const text = target.getAttribute('data-tooltip');
    if (!text) return;
    const rect = target.getBoundingClientRect();
    tooltipEl.textContent = text;
    tooltipEl.style.left = (rect.right + 12) + 'px';
    tooltipEl.style.top = (rect.top + rect.height / 2) + 'px';
    tooltipEl.classList.add('show');
  }
  function hideTooltip() { tooltipEl.classList.remove('show'); }

  document.querySelectorAll('[data-tooltip]').forEach((el) => {
    el.addEventListener('mouseenter', () => showTooltip(el));
    el.addEventListener('mouseleave', hideTooltip);
    el.addEventListener('click', hideTooltip);
  });

  /* ── Staggered card entrance on view switch ── */
  function staggerView(name) {
    const view = document.getElementById(`view-${name}`);
    if (!view) return;
    const cards = view.querySelectorAll(':scope > .dash-hero > .card, :scope > .dash-grid .dash-main-col > .card, :scope > .dash-grid .dash-side-col > .card');
    cards.forEach((el, i) => {
      el.classList.remove('qf-row-in');
      void el.offsetWidth; // force reflow so the animation restarts
      el.style.animationDelay = Math.min(i * 35, 260) + 'ms';
      el.classList.add('qf-row-in');
    });
  }

  if (typeof window.showView === 'function') {
    const originalShowView = window.showView;
    window.showView = function (name) {
      originalShowView(name);
      requestAnimationFrame(() => staggerView(name));
    };
    requestAnimationFrame(() => staggerView('dashboard'));
  }

  /* ── Click ripple feedback for buttons & nav items ── */
  function spawnRipple(target, evt) {
    const rect = target.getBoundingClientRect();
    const ripple = document.createElement('span');
    const size = Math.max(rect.width, rect.height) * 1.6;
    ripple.className = 'qf-ripple';
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = (evt.clientX - rect.left - size / 2) + 'px';
    ripple.style.top = (evt.clientY - rect.top - size / 2) + 'px';
    target.appendChild(ripple);
    ripple.addEventListener('animationend', () => ripple.remove());
  }

  document.addEventListener('click', (evt) => {
    const target = evt.target.closest('.btn, .btn-icon, .btn-refresh, .btn-action, .sidebar-nav a, .nav a');
    if (!target) return;
    const style = getComputedStyle(target);
    if (style.position === 'static') target.style.position = 'relative';
    spawnRipple(target, evt);
  }, true);
})();
