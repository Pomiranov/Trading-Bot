/* QuantFlow Chart Engine v2 — LW Charts + ECharts */

const QFChart = (() => {
  const instances = new Map();
  const observers = new Map();
  const COLORS = {
    long: '#00c076', short: '#f6465d', accent: '#F7931A', blue: '#3861fb',
    grid: 'rgba(255,255,255,0.04)', text: '#848e9c',
    palette: ['#F7931A', '#3861fb', '#00c076', '#f6465d', '#8b5cf6', '#06b6d4'],
  };

  function normalizeTime(t, index) {
    if (typeof t === 'string' && t.length >= 8) return t.slice(0, 10);
    if (typeof t === 'number') {
      const d = new Date(2020, 0, 1);
      d.setDate(d.getDate() + (t < 100000 ? t : index));
      return d.toISOString().slice(0, 10);
    }
    return `2020-01-${String((index % 28) + 1).padStart(2, '0')}`;
  }

  function showEmpty(id, text = 'Нет данных') {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = `<div class="chart-empty">${text}</div>`;
  }

  function observeResize(id, chart, type) {
    if (observers.has(id)) { observers.get(id).disconnect(); }
    const el = document.getElementById(id);
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => {
      if (type === 'lw' && chart) {
        chart.applyOptions({ width: el.clientWidth, height: el.clientHeight || 200 });
      } else if (type === 'echarts' && chart) {
        chart.resize();
      }
    });
    ro.observe(el);
    observers.set(id, ro);
  }

  function destroy(id) {
    if (observers.has(id)) { observers.get(id).disconnect(); observers.delete(id); }
    const inst = instances.get(id);
    if (!inst) return;
    if (inst._flatBadge) { try { inst._flatBadge.remove(); } catch (_) {} }
    if (inst.type === 'lw' && inst.chart) inst.chart.remove();
    else if (inst.type === 'echarts' && inst.chart) inst.chart.dispose();
    instances.delete(id);
  }

  function resizeAll() {
    instances.forEach((inst, id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (inst.type === 'lw' && inst.chart) {
        inst.chart.applyOptions({ width: el.clientWidth, height: el.clientHeight || 200 });
      } else if (inst.type === 'echarts' && inst.chart) {
        inst.chart.resize();
      }
    });
  }

  window.addEventListener('resize', () => requestAnimationFrame(resizeAll));

  const lwOpts = {
    layout: { background: { color: 'transparent' }, textColor: COLORS.text, fontSize: 11, fontFamily: 'JetBrains Mono' },
    grid: { vertLines: { color: COLORS.grid }, horzLines: { color: COLORS.grid } },
    rightPriceScale: { borderColor: 'rgba(255,255,255,0.06)' },
    timeScale: { borderColor: 'rgba(255,255,255,0.06)', timeVisible: true, secondsVisible: false },
    crosshair: { vertLine: { color: 'rgba(255,255,255,0.15)' }, horzLine: { color: 'rgba(255,255,255,0.15)' } },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale: { mouseWheel: true, pinch: true },
  };

  function line(id, data, opts = {}) {
    destroy(id);
    const el = document.getElementById(id);
    if (!el) return null;
    if (!data?.length) { showEmpty(id); return null; }
    if (typeof LightweightCharts === 'undefined') { showEmpty(id, 'Chart library loading…'); return null; }

    const points = data
      .map((d, i) => ({ time: normalizeTime(d.time ?? d.ts, i), value: Number(d.value ?? d.equity ?? d.close ?? 0) }))
      .filter(p => !isNaN(p.value));

    if (!points.length) { showEmpty(id); return null; }

    // Detect flat equity — when the range is < 0.05% of the mean, notify but still render
    const vals = points.map(p => p.value);
    const minVal = Math.min(...vals), maxVal = Math.max(...vals);
    const meanVal = vals.reduce((s, v) => s + v, 0) / vals.length;
    const rangePct = meanVal > 0 ? (maxVal - minVal) / meanVal * 100 : 0;
    const isFlat = rangePct < 0.05 && points.length > 1;

    el.innerHTML = '';
    const h = el.clientHeight || 260;

    // For flat charts, use a custom autoscale to pad context around the change
    const priceScaleOpts = isFlat
      ? { autoScale: true, scaleMargins: { top: 0.3, bottom: 0.3 } }
      : {};

    const chart = LightweightCharts.createChart(el, {
      ...lwOpts,
      width: el.clientWidth,
      height: h,
      rightPriceScale: { ...lwOpts.rightPriceScale, ...priceScaleOpts },
    });

    const color = opts.color || COLORS.long;
    const series = chart.addAreaSeries({
      lineColor: color,
      topColor: opts.fill || color + '40',
      bottomColor: 'transparent',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    });

    series.setData(points);
    chart.timeScale().fitContent();
    instances.set(id, { type: 'lw', chart, series });
    observeResize(id, chart, 'lw');

    // Add flat indicator overlay
    if (isFlat) {
      const badge = document.createElement('div');
      badge.style.cssText = 'position:absolute;top:8px;left:50%;transform:translateX(-50%);background:rgba(247,147,26,.12);border:1px solid rgba(247,147,26,.25);border-radius:4px;padding:3px 8px;font-size:10px;color:#F7931A;white-space:nowrap;pointer-events:none;z-index:2;font-family:var(--qf-font-mono)';
      badge.textContent = `Δ ${(maxVal - minVal).toFixed(2)} · стабильный портфель`;
      const parent = el.parentElement;
      if (parent && getComputedStyle(parent).position === 'static') parent.style.position = 'relative';
      parent?.appendChild(badge);
      // Remove badge when chart is destroyed
      instances.get(id)._flatBadge = badge;
    }

    return chart;
  }

  function candles(id, data, opts = {}) {
    destroy(id);
    const el = document.getElementById(id);
    if (!el || !data?.length || typeof LightweightCharts === 'undefined') {
      if (el && !data?.length) showEmpty(id);
      return null;
    }
    el.innerHTML = '';
    const chart = LightweightCharts.createChart(el, { ...lwOpts, width: el.clientWidth, height: el.clientHeight || 280 });
    const series = chart.addCandlestickSeries({
      upColor: COLORS.long, downColor: COLORS.short,
      borderUpColor: COLORS.long, borderDownColor: COLORS.short,
      wickUpColor: COLORS.long, wickDownColor: COLORS.short,
    });
    const points = data.map((d, i) => ({
      time: normalizeTime(d.ts ?? d.time, i),
      open: Number(d.open), high: Number(d.high), low: Number(d.low), close: Number(d.close),
    })).filter(p => p.close > 0);
    series.setData(points);
    chart.timeScale().fitContent();
    instances.set(id, { type: 'lw', chart, series });
    observeResize(id, chart, 'lw');
    return chart;
  }

  function drawdown(id, data) {
    if (!data?.length) { showEmpty(id); return null; }
    return line(id, data.map((d, i) => ({
      time: d.ts ?? d.time ?? i,
      value: Math.abs(d.drawdown ?? d.value ?? 0),
    })), { color: COLORS.short, fill: 'rgba(246,70,93,0.2)' });
  }

  function pie(id, allocation) {
    destroy(id);
    const el = document.getElementById(id);
    if (!el) return null;
    if (!allocation?.length) { showEmpty(id); return null; }
    if (typeof echarts === 'undefined') { showEmpty(id); return null; }

    const chart = echarts.init(el, null, { renderer: 'canvas' });
    chart.setOption({
      backgroundColor: 'transparent',
      animationDuration: 600,
      tooltip: {
        trigger: 'item', backgroundColor: '#161a22', borderColor: '#2a2e38',
        textStyle: { color: '#eaecef', fontSize: 11 },
        formatter: '{b}: {c}% ({d}%)',
      },
      series: [{
        type: 'pie', radius: ['48%', '70%'], center: ['50%', '50%'],
        itemStyle: { borderRadius: 6, borderColor: '#08090d', borderWidth: 2 },
        label: { show: false },
        emphasis: { scale: true, scaleSize: 6 },
        data: allocation.map((a, i) => ({
          name: a.label, value: a.pct ?? a.value,
          itemStyle: { color: COLORS.palette[i % COLORS.palette.length] },
        })),
      }],
    });
    instances.set(id, { type: 'echarts', chart });
    observeResize(id, chart, 'echarts');
    return chart;
  }

  function bar(id, data, opts = {}) {
    destroy(id);
    const el = document.getElementById(id);
    if (!el || !data?.length || typeof echarts === 'undefined') {
      if (el) showEmpty(id);
      return null;
    }
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    chart.setOption({
      backgroundColor: 'transparent',
      grid: { top: 16, bottom: 28, left: 48, right: 12 },
      tooltip: { trigger: 'axis', backgroundColor: '#161a22', borderColor: '#2a2e38', textStyle: { color: '#eaecef' } },
      xAxis: { type: 'category', data: data.map(d => d.label ?? d.period), axisLabel: { color: COLORS.text, fontSize: 10 }, axisLine: { lineStyle: { color: '#2a2e38' } } },
      yAxis: { type: 'value', axisLabel: { color: COLORS.text, fontSize: 10 }, splitLine: { lineStyle: { color: COLORS.grid } } },
      series: [{
        type: 'bar',
        data: data.map(d => ({
          value: d.value ?? d.pnl,
          itemStyle: { color: (d.value ?? d.pnl) >= 0 ? COLORS.long : COLORS.short, borderRadius: [4, 4, 0, 0] },
        })),
        barMaxWidth: 32,
      }],
    });
    instances.set(id, { type: 'echarts', chart });
    observeResize(id, chart, 'echarts');
    return chart;
  }

  function heatmap(id, data) {
    destroy(id);
    const el = document.getElementById(id);
    if (!el || !data?.length || typeof echarts === 'undefined') {
      if (el) showEmpty(id, 'Нет данных heatmap');
      return null;
    }
    const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
    // Build full 7×2 grid so all rows are visible; fill missing days with 0
    const byDay = new Map(data.map(d => [Number(d.day), d]));
    const fullData = days.flatMap((_, i) => {
      const d = byDay.get(i) || { wins: 0, losses: 0 };
      return [[0, i, d.wins || 0], [1, i, d.losses || 0]];
    });
    const maxVal = Math.max(...data.flatMap(d => [d.wins || 0, d.losses || 0]), 1);
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        backgroundColor: '#161a22', borderColor: '#2a2e38', textStyle: { color: '#eaecef' },
        formatter: p => `${days[p.data[1]]} · ${p.seriesName === 'Win' ? 'Wins' : 'Losses'}: <b>${p.data[2]}</b>`,
      },
      grid: { top: 8, bottom: 28, left: 36, right: 8 },
      xAxis: {
        type: 'category', data: ['Win', 'Loss'],
        axisLabel: { color: COLORS.text, fontSize: 10 },
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'category', data: days,
        axisLabel: { color: COLORS.text, fontSize: 10 },
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { show: false },
      },
      visualMap: { min: 0, max: maxVal, show: false, inRange: { color: ['#1e2230', COLORS.long, COLORS.accent] } },
      series: [{
        type: 'heatmap',
        name: 'Win',
        data: fullData,
        label: {
          show: true, color: '#eaecef', fontSize: 10,
          formatter: p => p.data[2] > 0 ? String(p.data[2]) : '',
        },
        itemStyle: { borderRadius: 3, borderColor: '#0c0e14', borderWidth: 2 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(247,147,26,0.4)' } },
      }],
    });
    instances.set(id, { type: 'echarts', chart });
    observeResize(id, chart, 'echarts');
    return chart;
  }

  function calendar(id, data) { return bar(id, data); }

  return { line, candles, drawdown, pie, bar, heatmap, calendar, destroy, resizeAll, showEmpty, COLORS };
})();

window.QFChart = QFChart;