/**
 * Safe DOM construction. There is no `innerHTML` in this application.
 *
 * The interface it replaces had 31 unescaped `innerHTML` interpolations across
 * `views/render.js` and `components.js`, with zero escaping helpers — and it
 * interpolated ticker strings into `onclick="loadTickerChart('${a.ticker}')"`,
 * i.e. a JavaScript string inside an HTML attribute inside a template literal,
 * from server data. Meanwhile the API key that guarded remote writes sat in
 * `sessionStorage`, readable by exactly that XSS.
 *
 * The fix is not an escaping helper — an escaping helper is something a developer
 * can forget. It is having no sink to escape *for*: everything below goes through
 * `document.createElement` and `textContent`, so a payload in a ticker, a strategy
 * name, a broker error or a database row is text by construction. There are also
 * no inline handlers anywhere; events are attached with `addEventListener`.
 */

/**
 * Create an element.
 *
 * `text` always lands in `textContent`. There is deliberately no `html` option.
 */
export function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  const {
    className, text, attrs, dataset, style, on, title, ariaLabel,
  } = options;

  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (title) node.title = String(title);
  if (ariaLabel) node.setAttribute('aria-label', String(ariaLabel));

  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      // Attribute *values* are safe via setAttribute, but an attribute *name*
      // starting with `on` would create a handler from data. Refuse those.
      if (/^on/i.test(key)) continue;
      node.setAttribute(key, value === true ? '' : String(value));
    }
  }

  if (dataset) {
    for (const [key, value] of Object.entries(dataset)) {
      if (value === null || value === undefined) continue;
      node.dataset[key] = String(value);
    }
  }

  // Only custom properties and a short allow-list of layout properties, so an
  // inline style cannot smuggle a `background: url(...)`.
  if (style) {
    for (const [key, value] of Object.entries(style)) {
      if (value === null || value === undefined) continue;
      if (key.startsWith('--')) node.style.setProperty(key, String(value));
      else if (ALLOWED_STYLE.has(key)) node.style.setProperty(key, String(value));
    }
  }

  if (on) {
    for (const [event, handler] of Object.entries(on)) {
      if (typeof handler === 'function') node.addEventListener(event, handler);
    }
  }

  append(node, children);
  return node;
}

const ALLOWED_STYLE = new Set([
  'width', 'height', 'min-width', 'max-width', 'grid-template-columns',
  'grid-column', 'grid-row', 'flex', 'gap', 'display',
]);

/** Append a child, a list, a string, or nothing. */
export function append(parent, children) {
  if (children === null || children === undefined || children === false) return parent;
  if (Array.isArray(children)) {
    for (const child of children) append(parent, child);
    return parent;
  }
  if (children instanceof Node) {
    parent.appendChild(children);
    return parent;
  }
  parent.appendChild(document.createTextNode(String(children)));
  return parent;
}

/** Empty a node. `replaceChildren()` also drops listeners on removed subtrees. */
export function clear(node) {
  if (node) node.replaceChildren();
  return node;
}

/**
 * Replace a region's contents in one operation.
 *
 * One renderer owns one node. Two renderers writing `#tickerGrid` with
 * incompatible markup, alternating on a 12-second poll with whichever ran last
 * winning, is a bug that only a single-owner rule prevents.
 */
export function render(node, children) {
  if (!node) return null;
  const fragment = document.createDocumentFragment();
  append(fragment, children);
  node.replaceChildren(fragment);
  return node;
}

export function text(value) {
  return document.createTextNode(value === null || value === undefined ? '' : String(value));
}

/** `<span>` with a class — the most common leaf in the interface. */
export function span(className, value, options = {}) {
  return el('span', { className, text: value, ...options });
}

/**
 * A numeric cell: right-aligned, tabular, and marked when its input is stale.
 *
 * Staleness is per cell. Marking the panel would imply that everything in it is
 * old, which is both wrong and how a single stale quote gets ignored.
 */
export function numericCell(value, { stale = false, title: hoverTitle = null, className = '' } = {}) {
  const classes = ['qf-num', className, stale ? 'qf-value--stale' : ''].filter(Boolean).join(' ');
  return el('span', { className: classes, text: value, title: hoverTitle });
}

/** `<svg>` needs the namespaced constructor; `createElement('svg')` yields HTML. */
export function svg(tag, attrs = {}, children = []) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (/^on/i.test(key)) continue;
    node.setAttribute(key, String(value));
  }
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child instanceof Node) node.appendChild(child);
  }
  return node;
}

/** A thin line icon from a path, in currentColor. One set, 1.5px, no fills. */
export function icon(pathData, { size = 18, className = 'qf-nav-icon' } = {}) {
  return svg('svg', {
    class: className,
    viewBox: '0 0 20 20',
    width: size,
    height: size,
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': '1.5',
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    'aria-hidden': 'true',
    focusable: 'false',
  }, [svg('path', { d: pathData })]);
}

/** Query helpers, so a typo in a selector fails loudly rather than silently. */
export function byId(id) {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Element #${id} not found`);
  return node;
}

export function maybeById(id) {
  return document.getElementById(id);
}

export function qs(selector, root = document) {
  return root.querySelector(selector);
}

export function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

/**
 * Add a class for a fixed duration, then remove it.
 *
 * Used for the directional tick flash. Returns a canceller so a re-render can
 * abandon a pending removal rather than touching a node that no longer exists.
 */
export function flash(node, className, duration = 600) {
  if (!node) return () => {};
  node.classList.add(className);
  const timer = window.setTimeout(() => node.classList.remove(className), duration);
  return () => {
    window.clearTimeout(timer);
    node.classList.remove(className);
  };
}

/**
 * A focus trap for a modal.
 *
 * Returns a release function. Restores focus to whatever had it before, which is
 * what makes a dialog usable from the keyboard rather than a one-way trip.
 */
export function trapFocus(container) {
  const previous = document.activeElement;
  const selector = [
    'a[href]', 'button:not([disabled])', 'input:not([disabled])',
    'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])',
  ].join(',');

  function onKeydown(event) {
    if (event.key !== 'Tab') return;
    const focusable = qsa(selector, container).filter((node) => node.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  container.addEventListener('keydown', onKeydown);
  const initial = qs(selector, container);
  if (initial) initial.focus();

  return () => {
    container.removeEventListener('keydown', onKeydown);
    if (previous && typeof previous.focus === 'function') previous.focus();
  };
}
