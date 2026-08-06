/**
 * URL routing and keyboard shortcuts.
 *
 * The old client had neither. Grepping `bot/ui/static/**` for `pushState`,
 * `location.hash` or `document.title` returned nothing: a view could not be
 * linked, bookmarked, restored after reload, or opened in a second tab, and an
 * alert could not deep-link to the screen it was about. For an operational tool
 * that is a functional gap, not a nicety.
 *
 * Shortcuts are fixed too. `app.js:167-178` called `preventDefault()` on bare
 * `r`/`R` and `1`–`8` with **no modifier guard**, so ⌘R/Ctrl+R page reload was
 * blocked and ⌘1–⌘8 tab switching was blocked, with no way to turn any of it off.
 */

const STORAGE_KEY = 'qf.lastRoute';

export class Router {
  constructor(routes, { defaultRoute = 'overview', titleSuffix = 'QuantFlow' } = {}) {
    /** `{ id: { path, title, mount } }` */
    this.routes = routes;
    this.defaultRoute = defaultRoute;
    this.titleSuffix = titleSuffix;
    this.current = null;
    this.listeners = new Set();
    this.onPopState = () => this.resolve(false);
  }

  start() {
    window.addEventListener('popstate', this.onPopState);
    // Restore the last view only when the URL says nothing. An explicit URL
    // always wins over a remembered preference.
    if (window.location.pathname === '/' && !window.location.hash) {
      const remembered = this.readRemembered();
      if (remembered && this.routes[remembered]) {
        this.navigate(remembered, { replace: true });
        return;
      }
    }
    this.resolve(false);
  }

  stop() {
    window.removeEventListener('popstate', this.onPopState);
    this.listeners.clear();
  }

  onChange(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  readRemembered() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }

  remember(id) {
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // Private mode or a full quota — a lost preference is not worth an error.
    }
  }

  /** Route id for the current URL, falling back to the default. */
  routeFromLocation() {
    const path = window.location.pathname.replace(/\/+$/, '') || '/';
    for (const [id, route] of Object.entries(this.routes)) {
      if (route.path === path) return id;
    }
    return this.defaultRoute;
  }

  /** Query parameters as a plain object — filters live in the URL, so a filtered
      view is shareable and survives a reload. */
  params() {
    return Object.fromEntries(new URLSearchParams(window.location.search).entries());
  }

  setParams(params, { replace = true } = {}) {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value === null || value === undefined || value === '') continue;
      search.set(key, String(value));
    }
    const query = search.toString();
    const url = `${window.location.pathname}${query ? `?${query}` : ''}`;
    if (replace) window.history.replaceState({}, '', url);
    else window.history.pushState({}, '', url);
    this.emit();
  }

  navigate(id, { replace = false, params = null } = {}) {
    const route = this.routes[id];
    if (!route) return;
    const search = params ? `?${new URLSearchParams(params).toString()}` : '';
    const url = `${route.path}${search}`;
    if (replace) window.history.replaceState({ id }, '', url);
    else window.history.pushState({ id }, '', url);
    this.resolve(true);
  }

  resolve(fromNavigation) {
    const id = this.routeFromLocation();
    const route = this.routes[id];
    const changed = this.current !== id;
    this.current = id;

    // `document.title` was never updated, so every browser tab and every history
    // entry read "QuantFlow — Paper Trading Platform".
    document.title = route && route.title
      ? `${route.title} · ${this.titleSuffix}`
      : this.titleSuffix;

    if (fromNavigation || changed) this.remember(id);
    this.emit(changed);
  }

  emit(changed = true) {
    const snapshot = { id: this.current, params: this.params(), changed };
    for (const listener of Array.from(this.listeners)) listener(snapshot);
  }
}

/**
 * Keyboard shortcuts.
 *
 * Three rules that were all broken:
 *
 * 1. **Never swallow a browser shortcut.** A handler fires only when no modifier
 *    is held, so ⌘R, Ctrl+R and ⌘1–⌘9 reach the browser untouched.
 * 2. **Never fire while the operator is typing.** Disabled inside input,
 *    textarea, select and contenteditable.
 * 3. **Documented and disableable.** `?` opens the list; the preference persists.
 */
export class Shortcuts {
  constructor() {
    this.bindings = new Map();
    this.enabled = this.readPreference();
    this.onKeydown = this.handle.bind(this);
  }

  readPreference() {
    try {
      return window.localStorage.getItem('qf.shortcuts') !== 'off';
    } catch {
      return true;
    }
  }

  setEnabled(value) {
    this.enabled = Boolean(value);
    try {
      window.localStorage.setItem('qf.shortcuts', this.enabled ? 'on' : 'off');
    } catch {
      /* ignore */
    }
  }

  /** `bind('g o', handler, 'Обзор')` or `bind('r', handler, 'Обновить')`. */
  bind(key, handler, description) {
    this.bindings.set(key, { handler, description });
    return () => this.bindings.delete(key);
  }

  list() {
    return Array.from(this.bindings.entries()).map(([key, value]) => ({
      key, description: value.description,
    }));
  }

  start() {
    window.addEventListener('keydown', this.onKeydown);
  }

  stop() {
    window.removeEventListener('keydown', this.onKeydown);
    this.bindings.clear();
  }

  static isTypingTarget(target) {
    if (!target) return false;
    if (target.isContentEditable) return true;
    const tag = target.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
  }

  handle(event) {
    if (!this.enabled) return;
    // The modifier guard. Its absence is what blocked ⌘R.
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (Shortcuts.isTypingTarget(event.target)) return;
    // A dialog owns the keyboard while it is open.
    if (document.querySelector('.qf-dialog')) return;

    const binding = this.bindings.get(event.key.toLowerCase());
    if (!binding) return;
    // preventDefault only for a key we actually handle, and only after every
    // guard above has passed.
    event.preventDefault();
    binding.handler(event);
  }
}
