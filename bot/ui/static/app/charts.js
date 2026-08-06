/**
 * Charts. Local SVG, no dependencies, ~9 KB.
 *
 * Replaces `lightweight-charts@4.2.0` (163 551 B raw) and `echarts@5.5.0`
 * (1 029 203 B raw), both loaded synchronously in `<head>` from third-party CDNs
 * with no SRI and no local fallback, for a handful of panels — and the free
 * lightweight-charts build put a TradingView watermark inside the equity panel on
 * an operator's screen.
 *
 * Every chart here obeys the standards from the audit's §17:
 *
 * * Created once, disposed properly, `ResizeObserver` on the container. Chart
 *   instances used to be re-created without `.remove()`/`.dispose()`, so every
 *   view switch leaked one.
 * * Series colour encodes *identity*, never a verdict. The old equity chart drew a
 *   green area under a curve whose own header read −80 776,12 ₽ in red.
 * * Colours come from tokens, read at draw time so a forced-colors or
 *   prefers-contrast change is picked up.
 * * Every chart ships a text summary and a data-table alternative.
 * * No candlestick chart. "It looks like TradingView" is not a workflow.
 */

import { svg } from './dom.js';
import * as fmt from './format.js';

/**
 * Base class: owns the container, the observer and the disposal contract.
 *
 * `dispose()` is not optional. A chart that survives its view keeps an observer
 * alive against a detached node, and after a few view switches the page is
 * carrying several.
 */
class Chart {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
    this.data = null;
    this.width = 0;
    this.height = 0;
    this.disposed = false;
    /** Index of the point under the cursor, or -1. */
    this.cursorIndex = -1;
    this.readout = null;
    this.pointerHandlers = null;

    this.observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const box = entry.contentRect;
        // Ignore sub-pixel noise: a redraw per scrollbar reflow is wasted work.
        if (Math.abs(box.width - this.width) < 2 && Math.abs(box.height - this.height) < 2) {
          continue;
        }
        this.width = box.width;
        this.height = box.height;
        this.draw();
      }
    });
    this.observer.observe(container);
  }

  setData(data) {
    this.data = data;
    this.draw();
  }

  draw() {
    if (this.disposed || !this.container || this.width <= 0) return;
    const root = this.render();
    this.container.replaceChildren(root);
  }

  render() {
    return svg('svg', { viewBox: `0 0 ${this.width} ${this.height}` });
  }

  /**
   * Attach a value readout driven by pointer *and* arrow keys.
   *
   * A chart whose exact numbers can only be obtained by eyeballing a line against
   * an axis is a picture, not an instrument. Hover alone would leave the values
   * unreachable from the keyboard, so the container becomes a single tab stop and
   * ←/→ walk the series; Home/End jump to the ends, Escape clears.
   *
   * @param {(index:number)=>string|null} describe formats the readout for a point
   */
  enableReadout(describe) {
    if (!this.container || this.pointerHandlers) return;

    this.readout = document.createElement('div');
    this.readout.className = 'qf-chart-readout';
    this.readout.hidden = true;
    // `aria-live` so a keyboard user hears the value change as they walk the series.
    this.readout.setAttribute('role', 'status');
    this.readout.setAttribute('aria-live', 'polite');
    this.container.appendChild(this.readout);

    this.container.setAttribute('tabindex', '0');
    this.container.setAttribute(
      'aria-label',
      `${this.options.ariaLabel || 'График'} — стрелками влево и вправо по точкам`,
    );

    const count = () => (Array.isArray(this.data) ? this.data.length : 0);

    const show = (index) => {
      const total = count();
      if (!total) return;
      this.cursorIndex = Math.max(0, Math.min(total - 1, index));
      const text = describe(this.cursorIndex);
      if (text === null || text === undefined) return;
      this.readout.textContent = text;
      this.readout.hidden = false;
      this.draw();
    };

    const clear = () => {
      this.cursorIndex = -1;
      this.readout.hidden = true;
      this.draw();
    };

    const fromPointer = (event) => {
      const total = count();
      if (!total) return;
      const box = this.container.getBoundingClientRect();
      const fraction = (event.clientX - box.left) / Math.max(1, box.width);
      show(Math.round(fraction * (total - 1)));
    };

    const onKeydown = (event) => {
      const total = count();
      if (!total) return;
      const start = this.cursorIndex === -1 ? total - 1 : this.cursorIndex;
      switch (event.key) {
        case 'ArrowRight': event.preventDefault(); show(start + 1); break;
        case 'ArrowLeft': event.preventDefault(); show(start - 1); break;
        case 'Home': event.preventDefault(); show(0); break;
        case 'End': event.preventDefault(); show(total - 1); break;
        case 'Escape': clear(); break;
        default: break;
      }
    };

    this.pointerHandlers = {
      pointermove: fromPointer,
      pointerleave: clear,
      keydown: onKeydown,
      blur: clear,
      // Show the last point on focus so a keyboard user starts somewhere real.
      focus: () => show(count() - 1),
    };
    for (const [event, handler] of Object.entries(this.pointerHandlers)) {
      this.container.addEventListener(event, handler);
    }
  }

  dispose() {
    this.disposed = true;
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
    // Listeners must go with the chart: a handler surviving its container is the
    // leak this whole architecture exists to avoid.
    if (this.container && this.pointerHandlers) {
      for (const [event, handler] of Object.entries(this.pointerHandlers)) {
        this.container.removeEventListener(event, handler);
      }
    }
    this.pointerHandlers = null;
    this.readout = null;
    if (this.container) this.container.replaceChildren();
    this.container = null;
  }
}

/** Map values to pixels. Returns identity-safe functions for a flat series. */
function scale(values, size, { pad = 0, includeZero = false } = {}) {
  const finite = values.filter((v) => Number.isFinite(v));
  if (!finite.length) return { min: 0, max: 1, to: () => size / 2 };
  let min = Math.min(...finite);
  let max = Math.max(...finite);
  if (includeZero) {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }
  if (min === max) {
    // A flat series must draw as a flat line in the middle, not as a divide-by-zero.
    const delta = Math.abs(min) || 1;
    min -= delta * 0.1;
    max += delta * 0.1;
  }
  const usable = size - pad * 2;
  return {
    min,
    max,
    to: (value) => pad + usable - ((value - min) / (max - min)) * usable,
  };
}

function pathFrom(points) {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(' ');
}

/**
 * A line/area series. Used for equity.
 *
 * The zero baseline is drawn when the range crosses it, and the fill sits between
 * the line and that baseline — so direction relative to zero is visible without
 * colouring the line by outcome.
 */
export class LineChart extends Chart {
  render() {
    const { width, height } = this;
    const padLeft = this.options.padLeft ?? 8;
    const padRight = this.options.padRight ?? 8;
    const padTop = 8;
    const padBottom = this.options.showAxis ? 18 : 8;
    const points = (this.data || []).filter((p) => Number.isFinite(p.value));

    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      preserveAspectRatio: 'none',
      role: 'img',
      'aria-label': this.options.ariaLabel || 'График',
    });

    if (points.length < 2) return root;

    const innerWidth = width - padLeft - padRight;
    const innerHeight = height - padTop - padBottom;
    const y = scale(points.map((p) => p.value), innerHeight, { includeZero: this.options.includeZero });
    const step = innerWidth / (points.length - 1);
    const coords = points.map((p, i) => [padLeft + i * step, padTop + y.to(p.value)]);

    // A reference line at the series' own start value: "up or down from where I
    // began" is the question an equity curve answers.
    const baselineValue = this.options.baseline ?? points[0].value;
    if (Number.isFinite(baselineValue) && baselineValue >= y.min && baselineValue <= y.max) {
      const by = padTop + y.to(baselineValue);
      root.appendChild(svg('line', {
        class: 'qf-chart-baseline',
        x1: padLeft, x2: width - padRight, y1: by, y2: by,
      }));
    }

    if (this.options.area !== false) {
      const areaBase = Number.isFinite(baselineValue)
        ? padTop + y.to(Math.max(y.min, Math.min(y.max, baselineValue)))
        : padTop + innerHeight;
      root.appendChild(svg('path', {
        class: 'qf-chart-area',
        d: `${pathFrom(coords)} L${coords[coords.length - 1][0].toFixed(2)},${areaBase.toFixed(2)}`
          + ` L${coords[0][0].toFixed(2)},${areaBase.toFixed(2)} Z`,
      }));
    }

    root.appendChild(svg('path', { class: 'qf-chart-line', d: pathFrom(coords) }));

    // The last point gets a marker: "this is now" on a series that ends mid-panel
    // is otherwise ambiguous.
    const last = coords[coords.length - 1];
    root.appendChild(svg('circle', { class: 'qf-chart-marker', cx: last[0], cy: last[1], r: 2.5 }));

    if (this.options.showAxis) {
      const first = points[0];
      const final = points[points.length - 1];
      root.appendChild(svg('text', {
        class: 'qf-chart-axis', x: padLeft, y: height - 4, 'text-anchor': 'start',
      }, [document.createTextNode(fmt.shortDateTime(first.ts))]));
      root.appendChild(svg('text', {
        class: 'qf-chart-axis', x: width - padRight, y: height - 4, 'text-anchor': 'end',
      }, [document.createTextNode(fmt.shortDateTime(final.ts))]));
    }

    return root;
  }
}

/** Underwater plot: drawdown from peak, always ≤ 0, sharing the equity x-axis. */
export class UnderwaterChart extends Chart {
  render() {
    const { width, height } = this;
    const pad = 8;
    const points = (this.data || []).filter((p) => Number.isFinite(p.value));
    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      preserveAspectRatio: 'none',
      role: 'img',
      'aria-label': this.options.ariaLabel || 'Просадка от максимума',
    });
    if (points.length < 2) return root;

    const innerWidth = width - pad * 2;
    const innerHeight = height - pad * 2;
    // Anchored at zero on top: drawdown hangs downwards, which is the metaphor.
    const worst = Math.min(...points.map((p) => p.value), -0.01);
    const step = innerWidth / (points.length - 1);
    const toY = (value) => pad + (value / worst) * innerHeight;
    const coords = points.map((p, i) => [pad + i * step, toY(p.value)]);

    root.appendChild(svg('line', {
      class: 'qf-chart-baseline', x1: pad, x2: width - pad, y1: pad, y2: pad,
    }));
    root.appendChild(svg('path', {
      class: 'qf-chart-underwater',
      d: `${pathFrom(coords)} L${coords[coords.length - 1][0].toFixed(2)},${pad}`
        + ` L${coords[0][0].toFixed(2)},${pad} Z`,
    }));
    return root;
  }
}

/**
 * Signed bars with a zero line. Used for daily PnL.
 *
 * Never a pie: a pie cannot show a negative value, which is half of what a PnL
 * series is.
 */
export class BarChart extends Chart {
  render() {
    const { width, height } = this;
    const pad = 8;
    const bars = (this.data || []).filter((b) => Number.isFinite(b.value));
    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      role: 'img',
      'aria-label': this.options.ariaLabel || 'Столбцы',
    });
    if (!bars.length) return root;

    const innerWidth = width - pad * 2;
    const innerHeight = height - pad * 2;
    const y = scale(bars.map((b) => b.value), innerHeight, { includeZero: true });
    const zeroY = pad + y.to(0);
    const slot = innerWidth / bars.length;
    const barWidth = Math.max(1, Math.min(slot - 2, 18));

    root.appendChild(svg('line', {
      class: 'qf-chart-baseline', x1: pad, x2: width - pad, y1: zeroY, y2: zeroY,
    }));

    bars.forEach((bar, index) => {
      const valueY = pad + y.to(bar.value);
      const top = Math.min(valueY, zeroY);
      const barHeight = Math.max(1, Math.abs(valueY - zeroY));
      root.appendChild(svg('rect', {
        class: bar.value >= 0 ? 'qf-chart-bar-positive' : 'qf-chart-bar-negative',
        x: pad + index * slot + (slot - barWidth) / 2,
        y: top,
        width: barWidth,
        height: barHeight,
        rx: 1,
      }));
    });

    return root;
  }
}

/**
 * A step line. Used for confidence.
 *
 * Confidence updates discretely, so a smooth curve would draw values the strategy
 * never held. The step is the honest shape.
 */
export class StepChart extends Chart {
  render() {
    const { width, height } = this;
    const pad = 8;
    const points = (this.data || []).filter((p) => Number.isFinite(p.value));
    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      preserveAspectRatio: 'none',
      role: 'img',
      'aria-label': this.options.ariaLabel || 'Пошаговый график',
    });
    if (points.length < 2) return root;

    const innerWidth = width - pad * 2;
    const innerHeight = height - pad * 2;
    // Confidence is a 0..1 ratio; a fixed domain keeps two strategies comparable.
    const y = { to: (v) => pad + innerHeight - Math.max(0, Math.min(1, v)) * innerHeight };
    const step = innerWidth / (points.length - 1);

    const segments = [];
    points.forEach((point, index) => {
      const x = pad + index * step;
      const py = y.to(point.value);
      if (index === 0) segments.push(`M${x.toFixed(2)},${py.toFixed(2)}`);
      else {
        segments.push(`H${x.toFixed(2)}`);
        segments.push(`V${py.toFixed(2)}`);
      }
    });
    segments.push(`H${(pad + innerWidth).toFixed(2)}`);

    root.appendChild(svg('path', { class: 'qf-chart-step', d: segments.join(' ') }));
    return root;
  }
}

/** Histogram. The bin width is stated by the caller in the panel meta. */
export class Histogram extends Chart {
  render() {
    const { width, height } = this;
    const pad = 8;
    const bins = this.data || [];
    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      role: 'img',
      'aria-label': this.options.ariaLabel || 'Распределение',
    });
    if (!bins.length) return root;

    const innerWidth = width - pad * 2;
    const innerHeight = height - pad * 2;
    const peak = Math.max(...bins.map((b) => b.count), 1);
    const slot = innerWidth / bins.length;

    bins.forEach((bin, index) => {
      const barHeight = (bin.count / peak) * innerHeight;
      root.appendChild(svg('rect', {
        // Sign of the bin's own range, not of the count — a bin of losses is red
        // because the losses are, not because the bar is tall.
        class: (bin.from ?? 0) >= 0 ? 'qf-chart-bar-positive' : 'qf-chart-bar-negative',
        x: pad + index * slot + 1,
        y: pad + innerHeight - barHeight,
        width: Math.max(1, slot - 2),
        height: Math.max(barHeight, bin.count ? 1 : 0),
        rx: 1,
      }));
    });

    root.appendChild(svg('line', {
      class: 'qf-chart-baseline',
      x1: pad, x2: width - pad, y1: pad + innerHeight, y2: pad + innerHeight,
    }));
    return root;
  }
}

/**
 * A sparkline. No axes, no markers, no interaction — it is a shape, and the
 * numbers beside it carry the values.
 */
export class Sparkline extends Chart {
  render() {
    const { width, height } = this;
    const points = (this.data || []).filter((p) => Number.isFinite(p.value));
    const root = svg('svg', {
      viewBox: `0 0 ${width} ${height}`,
      preserveAspectRatio: 'none',
      'aria-hidden': 'true',
      focusable: 'false',
    });
    if (points.length < 2) return root;

    const pad = 2;
    const y = scale(points.map((p) => p.value), height - pad * 2);
    const step = (width - pad * 2) / (points.length - 1);
    const coords = points.map((p, i) => [pad + i * step, pad + y.to(p.value)]);
    root.appendChild(svg('path', { class: 'qf-chart-line', d: pathFrom(coords) }));
    return root;
  }
}

/**
 * A textual summary for a series — the chart's accessible equivalent.
 *
 * A canvas with no text alternative fails 1.1.1, and the old charts had neither
 * this nor a data-table option.
 */
export function seriesSummary(points, { currency = 'RUB', label = 'Серия' } = {}) {
  const values = (points || []).map((p) => p.value).filter(Number.isFinite);
  if (!values.length) return `${label}: нет данных.`;
  const first = values[0];
  const last = values[values.length - 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const change = last - first;
  return [
    `${label}: ${values.length} ${fmt.NBSP}точек.`,
    `Начало ${fmt.money(first, { currency })}, конец ${fmt.money(last, { currency })}.`,
    `Изменение ${fmt.money(change, { currency, signed: true })}.`,
    `Минимум ${fmt.money(min, { currency })}, максимум ${fmt.money(max, { currency })}.`,
  ].join(' ');
}

/**
 * A registry so a view can dispose every chart it created in one call.
 *
 * This is the mechanism that makes "no leak on view switch" structural rather
 * than a thing each view has to remember.
 */
export class ChartRegistry {
  constructor() {
    this.charts = new Map();
  }

  create(key, ChartClass, container, options) {
    this.destroy(key);
    const chart = new ChartClass(container, options);
    this.charts.set(key, chart);
    return chart;
  }

  get(key) {
    return this.charts.get(key) || null;
  }

  destroy(key) {
    const chart = this.charts.get(key);
    if (chart) {
      chart.dispose();
      this.charts.delete(key);
    }
  }

  destroyAll() {
    for (const chart of this.charts.values()) chart.dispose();
    this.charts.clear();
  }

  get size() {
    return this.charts.size;
  }
}
