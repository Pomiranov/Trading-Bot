/* QuantFlow — AppLayout + SidebarProvider */

const SidebarProvider = (() => {
  const STORAGE_KEY = 'qf_sidebar_collapsed';
  const bus = new EventTarget();

  const state = {
    mode: 'OPEN',       // OPEN | COLLAPSED
    mobileOpen: false,
    layout: 'dashboard', // dashboard | miniapp
  };

  function emit(type, detail = {}) {
    bus.dispatchEvent(new CustomEvent(type, { detail }));
  }

  function apply() {
    const body = document.body;
    body.classList.toggle('sidebar-collapsed', state.mode === 'COLLAPSED');
    body.classList.toggle('sidebar-open', state.mobileOpen);
    body.classList.toggle('layout-dashboard', state.layout === 'dashboard');
    body.classList.toggle('layout-miniapp', state.layout === 'miniapp');
    body.dataset.sidebarState = state.mode;
    body.dataset.appLayout = state.layout;
    const root = getComputedStyle(document.documentElement);
    const openW = root.getPropertyValue('--qf-sidebar-w').trim() || '240px';
    const collapsedW = root.getPropertyValue('--qf-sidebar-collapsed').trim() || '64px';
    document.documentElement.style.setProperty(
      '--qf-sidebar-current',
      state.mode === 'COLLAPSED' ? collapsedW : openW
    );
    emit('sidebar:change', { ...state });
  }

  function toggleCollapse() {
    state.mode = state.mode === 'COLLAPSED' ? 'OPEN' : 'COLLAPSED';
    localStorage.setItem(STORAGE_KEY, state.mode === 'COLLAPSED');
    apply();
    setTimeout(() => {
      window.QFChart?.resizeAll();
      window.MiniAppBridge?.resize?.();
    }, 320);
  }

  function toggleMobile() {
    state.mobileOpen = !state.mobileOpen;
    apply();
  }

  function closeMobile() {
    state.mobileOpen = false;
    apply();
  }

  function setLayout(layout) {
    state.layout = layout;
    apply();
    setTimeout(() => window.MiniAppBridge?.resize?.(), 100);
  }

  function init() {
    if (localStorage.getItem(STORAGE_KEY) === 'true') state.mode = 'COLLAPSED';
    apply();

    document.getElementById('sidebarToggle')?.addEventListener('click', toggleCollapse);
    document.getElementById('mobileMenuBtn')?.addEventListener('click', toggleMobile);
    document.getElementById('sidebarOverlay')?.addEventListener('click', closeMobile);
  }

  function on(fn) { bus.addEventListener('sidebar:change', e => fn(e.detail)); }

  return { init, toggleCollapse, toggleMobile, closeMobile, setLayout, get: () => ({ ...state }), on };
})();

const AppLayout = {
  enterDashboard() { SidebarProvider.setLayout('dashboard'); },
  enterMiniApp() { SidebarProvider.setLayout('miniapp'); SidebarProvider.closeMobile(); },
};

window.SidebarProvider = SidebarProvider;
window.AppLayout = AppLayout;