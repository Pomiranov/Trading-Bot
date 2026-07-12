/* QuantFlow Chart Engine v2 — LW Charts + ECharts */

const QFChart = (() => {
  const instances = new Map();
  const observers = new Map();
  const COLORS = {
    long: '#00c076', short: '#f6465d', accent: '#f0b90b', blue: '#3861fb',
    grid: 'rgba(255,255,255,0.04)', text: '#848e9c',
    palette: ['#00c076', '#3861fb', '#f0b90b', '#f6465d', '#8b5cf6', '#06b6d4'],
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

    el.innerHTML = '';
    const h = el.clientHeight || 260;
    const chart = LightweightCharts.createChart(el, { ...lwOpts, width: el.clientWidth, height: h });

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

    const points = data
      .map((d, i) => ({ time: normalizeTime(d.time ?? d.ts, i), value: Number(d.value ?? d.equity ?? d.close ?? 0) }))
      .filter(p => !isNaN(p.value));

    if (!points.length) { showEmpty(id); return null; }
    series.setData(points);
    chart.timeScale().fitContent();
    instances.set(id, { type: 'lw', chart, series });
    observeResize(id, chart, 'lw');
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
    const maxVal = Math.max(...data.flatMap(d => [d.wins || 0, d.losses || 0]), 1);
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: { backgroundColor: '#161a22', borderColor: '#2a2e38', textStyle: { color: '#eaecef' } },
      grid: { top: 8, bottom: 24, left: 36, right: 8 },
      xAxis: { type: 'category', data: ['Win', 'Loss'], axisLabel: { color: COLORS.text, fontSize: 10 }, axisLine: { show: false } },
      yAxis: { type: 'category', data: days, axisLabel: { color: COLORS.text, fontSize: 10 }, axisLine: { show: false } },
      visualMap: { min: 0, max: maxVal, show: false, inRange: { color: ['#161a22', COLORS.long, COLORS.accent] } },
      series: [{
        type: 'heatmap',
        data: data.flatMap(d => [[0, Number(d.day), d.wins || 0], [1, Number(d.day), d.losses || 0]]),
        label: { show: true, color: '#eaecef', fontSize: 10 },
        itemStyle: { borderRadius: 4 },
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