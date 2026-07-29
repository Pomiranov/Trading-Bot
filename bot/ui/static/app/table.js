/**
 * One DataTable for every table in the product.
 *
 * The eight tables it replaces had sticky headers and nothing else: no sorting,
 * no filtering, no pagination, no virtualisation, no selected state, no keyboard
 * interaction, no per-table empty state — and in three of the eight, twelve
 * columns were right-aligned in the header while their bodies were left-aligned,
 * because the header used `.num` and the body emitted `class="mono"`.
 *
 * Alignment here is declared once per column and both halves read it, so header
 * and body cannot disagree. Rows are built with `createElement`/`textContent`, so
 * a payload in a ticker or a strategy name is text.
 */

import { clear, el, render } from './dom.js';
import { t } from './i18n.js';

/** Above this many rows, render a window instead of the whole set. */
const VIRTUALISE_ABOVE = 200;
/** Rows rendered outside the viewport on each side, to hide scroll latency. */
const OVERSCAN = 12;

let sequence = 0;

export class DataTable {
  /**
   * @param {object} config
   *   columns: [{ key, label, align, numeric, sortable, width, render(row), label:string,
   *               stale(row), title(row), responsive:boolean }]
   *   density: 'compact' | 'comfortable' | 'monitoring'
   *   caption: accessible description — mandatory, not decorative
   *   onSelect(row), onOpen(row): keyboard and pointer interaction
   *   storageKey: persists sort and density per table
   */
  constructor(container, config) {
    this.container = container;
    this.columns = config.columns;
    this.caption = config.caption;
    this.density = config.density || this.readPreference('density') || 'comfortable';
    this.onSelect = config.onSelect || null;
    this.onOpen = config.onOpen || null;
    this.rowKey = config.rowKey || ((row, index) => row.id ?? index);
    this.storageKey = config.storageKey || null;
    this.responsive = config.responsive !== false;
    this.emptyState = config.emptyState || null;

    const savedSort = this.readPreference('sort');
    this.sortKey = savedSort?.key || config.defaultSort || null;
    this.sortDescending = savedSort ? Boolean(savedSort.desc) : config.defaultSortDescending !== false;
    /** Server-side sorting: the caller re-fetches instead of sorting locally. */
    this.serverSort = Boolean(config.serverSort);
    this.onSortChange = config.onSortChange || null;

    this.rows = [];
    this.selectedKey = null;
    this.focusedIndex = -1;
    this.focusedColumn = 0;
    this.id = `qf-table-${++sequence}`;

    this.scrollHandler = null;
    this.keyHandler = null;
    this.build();
  }

  // ── Preferences ────────────────────────────────────────────────────────────

  readPreference(name) {
    if (!this.storageKey) return null;
    try {
      const raw = window.localStorage.getItem(`qf.table.${this.storageKey}.${name}`);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  writePreference(name, value) {
    if (!this.storageKey) return;
    try {
      window.localStorage.setItem(`qf.table.${this.storageKey}.${name}`, JSON.stringify(value));
    } catch {
      /* quota or private mode */
    }
  }

  // ── Construction ───────────────────────────────────────────────────────────

  build() {
    this.wrap = el('div', { className: 'qf-table-wrap' });
    this.table = el('table', {
      className: `qf-table qf-table--${this.density}${this.responsive ? ' qf-table--responsive' : ''}`,
      attrs: { id: this.id },
    });

    // A caption is the table's accessible name. All eight old tables lacked one,
    // so a screen-reader user met eight unlabelled grids.
    this.captionNode = el('caption', { text: this.caption });
    this.table.appendChild(this.captionNode);

    this.thead = el('thead');
    this.table.appendChild(this.thead);
    this.tbody = el('tbody');
    this.table.appendChild(this.tbody);

    this.wrap.appendChild(this.table);
    this.container.replaceChildren(this.wrap);

    this.renderHeader();
    this.attachKeyboard();
  }

  renderHeader() {
    const row = el('tr');
    for (const column of this.columns) {
      const th = el('th', {
        text: column.label,
        attrs: {
          // `scope="col"` is what associates a header with its column for
          // assistive tech; it was absent everywhere.
          scope: 'col',
          ...(column.sortable ? { 'aria-sort': this.ariaSortFor(column.key), tabindex: '0', role: 'columnheader' } : {}),
        },
        dataset: { align: column.align || (column.numeric ? 'end' : 'start'), key: column.key },
        style: column.width ? { width: column.width } : undefined,
      });

      if (column.sortable) {
        const activate = () => this.toggleSort(column.key);
        th.addEventListener('click', activate);
        th.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            activate();
          }
        });
      }
      row.appendChild(th);
    }
    render(this.thead, row);
  }

  ariaSortFor(key) {
    if (this.sortKey !== key) return 'none';
    return this.sortDescending ? 'descending' : 'ascending';
  }

  toggleSort(key) {
    if (this.sortKey === key) this.sortDescending = !this.sortDescending;
    else {
      this.sortKey = key;
      // Numeric columns default to descending: the biggest loss or the newest
      // trade is what an operator wants at the top.
      const column = this.columns.find((c) => c.key === key);
      this.sortDescending = Boolean(column && column.numeric);
    }
    this.writePreference('sort', { key: this.sortKey, desc: this.sortDescending });
    this.renderHeader();
    if (this.serverSort && this.onSortChange) {
      this.onSortChange(this.sortKey, this.sortDescending);
    } else {
      this.setRows(this.rows);
    }
  }

  setDensity(density) {
    this.density = density;
    this.table.className = `qf-table qf-table--${density}${this.responsive ? ' qf-table--responsive' : ''}`;
    this.writePreference('density', density);
    this.setRows(this.rows);
  }

  // ── Data ───────────────────────────────────────────────────────────────────

  setRows(rows) {
    this.rows = Array.isArray(rows) ? rows : [];
    const sorted = this.serverSort ? this.rows : this.sortRows(this.rows);
    this.visibleRows = sorted;

    if (!sorted.length) {
      this.renderEmpty();
      return;
    }

    if (sorted.length > VIRTUALISE_ABOVE) this.renderVirtual(sorted);
    else this.renderAll(sorted);
  }

  sortRows(rows) {
    if (!this.sortKey) return rows.slice();
    const column = this.columns.find((c) => c.key === this.sortKey);
    if (!column) return rows.slice();
    const direction = this.sortDescending ? -1 : 1;
    return rows.slice().sort((left, right) => {
      const a = left[this.sortKey];
      const b = right[this.sortKey];
      // Missing values sort last in both directions: an unmeasured row is not
      // "the smallest", and letting it float to the top of a descending sort
      // would put unknowns above real data.
      const aMissing = a === null || a === undefined || a === '';
      const bMissing = b === null || b === undefined || b === '';
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;
      if (bMissing) return -1;
      if (typeof a === 'number' && typeof b === 'number') return (a - b) * direction;
      return String(a).localeCompare(String(b), 'ru') * direction;
    });
  }

  renderEmpty() {
    const row = el('tr', {}, [
      el('td', {
        attrs: { colspan: String(this.columns.length) },
      }, [this.emptyState || el('div', { className: 'qf-state' }, [
        el('div', { className: 'qf-state-title', text: t('state.NO_EVENTS') }),
      ])]),
    ]);
    render(this.tbody, row);
  }

  renderAll(rows) {
    if (this.scrollHandler) {
      this.wrap.removeEventListener('scroll', this.scrollHandler);
      this.scrollHandler = null;
    }
    const fragment = document.createDocumentFragment();
    rows.forEach((row, index) => fragment.appendChild(this.buildRow(row, index)));
    clear(this.tbody);
    this.tbody.appendChild(fragment);
    this.restoreFocusMarker();
  }

  /**
   * Windowed rendering above 200 rows.
   *
   * Spacer rows above and below carry the scroll height, so the scrollbar stays
   * proportional and the DOM holds a screenful rather than a thousand rows. Row
   * height comes from the density token, read once per pass.
   */
  renderVirtual(rows) {
    const rowHeight = this.measureRowHeight();
    const viewport = this.wrap.clientHeight || 480;

    const paint = () => {
      const scrollTop = this.wrap.scrollTop;
      const firstVisible = Math.max(0, Math.floor(scrollTop / rowHeight) - OVERSCAN);
      const count = Math.ceil(viewport / rowHeight) + OVERSCAN * 2;
      const lastVisible = Math.min(rows.length, firstVisible + count);

      const fragment = document.createDocumentFragment();
      if (firstVisible > 0) {
        fragment.appendChild(el('tr', {
          attrs: { 'aria-hidden': 'true' },
          style: { height: `${firstVisible * rowHeight}px` },
        }, [el('td', { attrs: { colspan: String(this.columns.length) } })]));
      }
      for (let index = firstVisible; index < lastVisible; index += 1) {
        fragment.appendChild(this.buildRow(rows[index], index));
      }
      const trailing = rows.length - lastVisible;
      if (trailing > 0) {
        fragment.appendChild(el('tr', {
          attrs: { 'aria-hidden': 'true' },
          style: { height: `${trailing * rowHeight}px` },
        }, [el('td', { attrs: { colspan: String(this.columns.length) } })]));
      }
      clear(this.tbody);
      this.tbody.appendChild(fragment);
      this.restoreFocusMarker();
    };

    if (this.scrollHandler) this.wrap.removeEventListener('scroll', this.scrollHandler);
    let frame = null;
    this.scrollHandler = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = null;
        paint();
      });
    };
    this.wrap.addEventListener('scroll', this.scrollHandler, { passive: true });
    paint();
  }

  measureRowHeight() {
    const map = { compact: 28, comfortable: 36, monitoring: 44 };
    return map[this.density] || 36;
  }

  buildRow(row, index) {
    const key = String(this.rowKey(row, index));
    const tr = el('tr', {
      attrs: {
        'aria-selected': this.selectedKey === key ? 'true' : 'false',
        tabindex: '-1',
      },
      dataset: { key, index: String(index) },
    });

    for (const column of this.columns) {
      const align = column.align || (column.numeric ? 'end' : 'start');
      const stale = typeof column.stale === 'function' ? Boolean(column.stale(row)) : false;
      const content = column.render ? column.render(row) : row[column.key];
      const td = el('td', {
        dataset: {
          align,
          // Read by the mobile card layout as the cell's own label, so one
          // markup shape serves both the table and the card.
          label: column.label,
          numeric: column.numeric ? 'true' : undefined,
        },
        className: stale ? 'qf-value--stale' : undefined,
        title: typeof column.title === 'function' ? column.title(row) : undefined,
      });
      if (content instanceof Node) td.appendChild(content);
      else td.textContent = content === null || content === undefined ? '—' : String(content);
      tr.appendChild(td);
    }

    if (this.onSelect || this.onOpen) {
      tr.addEventListener('click', () => this.select(index));
      tr.addEventListener('dblclick', () => this.open(index));
    }
    return tr;
  }

  // ── Selection and keyboard ─────────────────────────────────────────────────

  select(index) {
    const rows = this.visibleRows || [];
    const row = rows[index];
    if (!row) return;
    this.focusedIndex = index;
    this.selectedKey = String(this.rowKey(row, index));
    this.restoreFocusMarker();
    if (this.onSelect) this.onSelect(row, index);
  }

  open(index) {
    const row = (this.visibleRows || [])[index];
    if (row && this.onOpen) this.onOpen(row, index);
  }

  restoreFocusMarker() {
    for (const tr of this.tbody.children) {
      if (!tr.dataset.key) continue;
      const isSelected = tr.dataset.key === this.selectedKey;
      tr.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      const isFocused = Number(tr.dataset.index) === this.focusedIndex;
      if (isFocused) tr.dataset.focused = 'true';
      else delete tr.dataset.focused;
    }
  }

  /**
   * Full keyboard traversal: ↑↓ row, ←→ cell, Enter open, Space select, Esc close.
   *
   * The table is a single tab stop with a roving focus inside it, so Tab does not
   * walk through 60 rows to reach the next control.
   */
  attachKeyboard() {
    this.wrap.setAttribute('tabindex', '0');
    this.wrap.setAttribute('role', 'group');
    this.wrap.setAttribute('aria-label', this.caption);

    this.keyHandler = (event) => {
      const rows = this.visibleRows || [];
      if (!rows.length) return;

      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          this.moveFocus(Math.min(rows.length - 1, this.focusedIndex + 1));
          break;
        case 'ArrowUp':
          event.preventDefault();
          this.moveFocus(Math.max(0, this.focusedIndex - 1));
          break;
        case 'ArrowRight':
          event.preventDefault();
          this.focusedColumn = Math.min(this.columns.length - 1, this.focusedColumn + 1);
          this.announceCell();
          break;
        case 'ArrowLeft':
          event.preventDefault();
          this.focusedColumn = Math.max(0, this.focusedColumn - 1);
          this.announceCell();
          break;
        case 'Home':
          event.preventDefault();
          this.moveFocus(0);
          break;
        case 'End':
          event.preventDefault();
          this.moveFocus(rows.length - 1);
          break;
        case 'Enter':
          event.preventDefault();
          this.open(this.focusedIndex);
          break;
        case ' ':
          event.preventDefault();
          this.select(this.focusedIndex);
          break;
        case 'Escape':
          this.selectedKey = null;
          this.restoreFocusMarker();
          if (this.onSelect) this.onSelect(null, -1);
          break;
        default:
          break;
      }
    };
    this.wrap.addEventListener('keydown', this.keyHandler);
  }

  moveFocus(index) {
    this.focusedIndex = index;
    // Virtualised rows may not be in the DOM yet; scroll first, then mark.
    const rowHeight = this.measureRowHeight();
    const target = index * rowHeight;
    if (target < this.wrap.scrollTop) this.wrap.scrollTop = target;
    else if (target + rowHeight > this.wrap.scrollTop + this.wrap.clientHeight) {
      this.wrap.scrollTop = target + rowHeight - this.wrap.clientHeight;
    }
    this.restoreFocusMarker();
    this.announceCell();
  }

  /**
   * Announce the focused cell to assistive tech.
   *
   * Column label plus value, so ←→ traversal is meaningful rather than silent.
   */
  announceCell() {
    const row = (this.visibleRows || [])[this.focusedIndex];
    if (!row) return;
    const column = this.columns[this.focusedColumn];
    if (!column) return;
    const tr = this.tbody.querySelector(`tr[data-index="${this.focusedIndex}"]`);
    const cell = tr ? tr.children[this.focusedColumn] : null;
    const value = cell ? cell.textContent : '';
    this.wrap.setAttribute('aria-activedescendant', '');
    window.dispatchEvent(new CustomEvent('qf:announce', {
      detail: { message: `${column.label}: ${value}` },
    }));
  }

  setBusy(busy) {
    this.wrap.setAttribute('aria-busy', busy ? 'true' : 'false');
  }

  /** Dispose. Removes the scroll and key listeners — an interval or listener
      surviving a view switch is the leak this whole architecture avoids. */
  dispose() {
    if (this.scrollHandler) this.wrap.removeEventListener('scroll', this.scrollHandler);
    if (this.keyHandler) this.wrap.removeEventListener('keydown', this.keyHandler);
    this.scrollHandler = null;
    this.keyHandler = null;
    this.rows = [];
    this.visibleRows = [];
    if (this.container) this.container.replaceChildren();
  }
}
