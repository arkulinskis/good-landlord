/* core.js: the shared front-end engine (window.UI). Same in every app made from APP_MAKER/template;
   app-specific things live in web/app.js (brand, nav, footer) and web/pages/*.html (the pages).

   Pages:   UI.page(name, {title, nav, icon, auth, order, chrome}, mount)
              auth: null (anyone) | 'guest' (signed-out only) | 'user' | 'admin'
              nav: label for the header / phone tab bar (omit to keep it out of the menus)
              mount(view, ctx) draws into `view`; ctx = {args, me, go, api}. Return a Promise (the page
              is "ready" when it resolves) or {ready, destroy}. URLs are #name/arg1/arg2.
   Server:  UI.api(fn, ...args) -> Promise of the server function's return value. A reply of
              {ok: false, error} rejects with that message (shown as a toast unless you .catch it).
            UI.apiQuiet(fn, ...args) is the same without Anvil's loading spinner.
   Auth:    UI.auth('login'|'signup'|'reset'|'logout', {...}) -> Promise of {ok, me, message}
   Helpers: UI.esc, UI.icon, UI.toast, UI.modal, UI.confirm, UI.busy, UI.formData, UI.fmtDate, UI.ago,
            UI.store, UI.setTheme, UI.feedback, UI.go, UI.refresh
   Tests:   window.UI_READY is true when the current page has finished loading. */
(function () {
  'use strict';
  if (window.UI && window.UI.__v) return;
  var UI = window.UI = { __v: 1, pages: {}, me: null, config: { name: 'App', key: 'app', home: 'home', landing: 'landing' } };
  window.UI_READY = false;

  UI.configure = function (cfg) { Object.keys(cfg).forEach(function (k) { UI.config[k] = cfg[k]; }); };

  /* ------------------------------------------------------------------ small helpers */
  UI.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  UI.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  UI.initials = function (name) {
    var p = String(name || '?').trim().split(/\s+/);
    return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
  };
  UI.fmtDate = function (iso, opts) {
    if (!iso) return '';
    var d = iso.length <= 10 ? new Date(iso + 'T12:00:00') : new Date(iso);
    return d.toLocaleDateString(undefined, opts || { day: 'numeric', month: 'short', year: 'numeric' });
  };
  UI.fmtDateTime = function (iso) {
    return iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  };
  UI.ago = function (iso) {
    if (!iso) return '';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return 'just now';
    var steps = [[60, 'minute'], [24, 'hour'], [7, 'day'], [4.35, 'week'], [12, 'month'], [Infinity, 'year']], n = s / 60;
    for (var i = 0; i < steps.length; i++) {
      if (n < steps[i][0]) { n = Math.floor(n); return UI.plural(n, steps[i][1]) + ' ago'; }
      n = n / steps[i][0];
    }
    return '';
  };
  UI.store = {
    get: function (k, dflt) { try { var v = localStorage.getItem(UI.config.key + '.' + k); return v == null ? dflt : JSON.parse(v); } catch (e) { return dflt; } },
    set: function (k, v) { try { localStorage.setItem(UI.config.key + '.' + k, JSON.stringify(v)); } catch (e) {} }
  };
  UI.formData = function (form) {
    var out = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled) return;
      if (el.type === 'checkbox') out[el.name] = el.checked;
      else if (el.type === 'radio') { if (el.checked) out[el.name] = el.value; }
      else out[el.name] = el.value;
    });
    return out;
  };
  /* Disable a button while a Promise runs; returns the Promise. */
  UI.busy = function (btn, promise) {
    if (!btn) return promise;
    btn.disabled = true; btn.classList.add('is-busy');
    var done = function () { btn.disabled = false; btn.classList.remove('is-busy'); };
    promise.then(done, done);
    return promise;
  };

  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.7c2.2.6 3.5 2.4 3.5 5.3"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/>',
    bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    bug: '<rect x="7" y="8" width="10" height="12" rx="5"/><path d="M12 8V5M9 5.5 7.5 4M15 5.5 16.5 4M7 13H3M21 13h-4M7.5 18l-3 2M16.5 18l3 2M7.5 9.5l-3-2M16.5 9.5l3-2"/>',
    bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13"/><path d="M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    pin: '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13.5" r="3.5"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    filter: '<path d="M4 5h16l-6 7.5V19l-4 1.5v-8z"/>',
    more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>'
  };
  UI.ICONS = ICONS;
  UI.icon = function (name, cls) {
    return '<svg class="ui-ic ' + (cls || '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || ICONS.sparkle) + '</svg>';
  };

  /* ------------------------------------------------------------------ toasts, modals */
  UI.toast = function (msg, kind) {
    var box = document.querySelector('.ui-toasts');
    if (!box) { box = document.createElement('div'); box.className = 'ui ui-toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var t = document.createElement('div');
    t.className = 'ui-toast' + (kind ? ' ' + kind : '');
    t.innerHTML = (kind === 'error' ? UI.icon('info') : kind === 'ok' ? UI.icon('check') : '') + '<span>' + UI.esc(msg) + '</span>';
    box.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }, kind === 'error' ? 6500 : 3200);
  };
  UI.modal = function (html, opts) {
    opts = opts || {};
    var prev = document.activeElement;
    var wrap = document.createElement('div');
    wrap.className = 'ui ui-modal-wrap';
    wrap.innerHTML = '<div class="ui-modal' + (opts.wide ? ' wide' : '') + '" role="dialog" aria-modal="true">' +
      '<button class="ui-btn ghost icon ui-modal-x" data-close aria-label="Close">' + UI.icon('x') + '</button>' + html + '</div>';
    document.body.appendChild(wrap);
    document.documentElement.classList.add('ui-modal-open');
    function key(e) { if (e.key === 'Escape') close(); }
    function close() {
      if (!wrap.parentNode) return;
      wrap.remove(); document.removeEventListener('keydown', key);
      if (!document.querySelector('.ui-modal-wrap')) document.documentElement.classList.remove('ui-modal-open');
      if (opts.onclose) opts.onclose();
      if (prev && prev.focus) prev.focus();
    }
    document.addEventListener('keydown', key);
    wrap.addEventListener('mousedown', function (e) { if (e.target === wrap) close(); });
    wrap.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) close(); });
    var first = wrap.querySelector('input, textarea, select');
    setTimeout(function () { (first || wrap.querySelector('.ui-modal')).focus && (first || wrap.querySelector('.ui-modal')).focus(); }, 30);
    return { el: wrap.querySelector('.ui-modal'), close: close };
  };
  UI.confirm = function (o) {
    o = typeof o === 'string' ? { title: o } : (o || {});
    return new Promise(function (resolve) {
      var answered = false;
      var m = UI.modal('<h2>' + UI.esc(o.title || 'Are you sure?') + '</h2>' + (o.text ? '<p class="muted">' + UI.esc(o.text) + '</p>' : '') +
        '<div class="ui-row end" style="margin-top:20px"><button class="ui-btn ghost" data-close>' + UI.esc(o.cancel || 'Cancel') + '</button>' +
        '<button class="ui-btn ' + (o.danger ? 'danger solid' : 'primary') + '" data-ok>' + UI.esc(o.ok || 'OK') + '</button></div>',
      { onclose: function () { if (!answered) resolve(false); } });
      m.el.querySelector('[data-ok]').onclick = function () { answered = true; m.close(); resolve(true); };
    });
  };

  /* ------------------------------------------------------------------ theme */
  UI.theme = function () { return UI.store.get('theme', 'auto'); };
  UI.applyTheme = function (t) {
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
    else document.documentElement.removeAttribute('data-theme');
    var dark = t === 'dark' || (t !== 'light' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('ui-dark', !!dark);
  };
  UI.setTheme = function (t) { UI.store.set('theme', t); UI.applyTheme(t); };
  UI.applyTheme(UI.theme());
  if (window.matchMedia) {
    try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { UI.applyTheme(UI.theme()); }); } catch (e) {}
  }

  /* ------------------------------------------------------------------ server bridge */
  var bridge = null;
  function send(kind, payload) {
    if (!bridge) return Promise.reject(new Error('The app is still starting.'));
    var out;
    try { out = bridge(kind, JSON.stringify(payload || {})); } catch (e) { return Promise.reject(e); }
    return Promise.resolve(out).then(function (r) {
      r = typeof r === 'string' ? JSON.parse(r) : (r || {});
      if (r.error) {
        var err = new Error(r.error); err.uiApi = true; err.denied = !!r.denied;
        if (r.detail) console.error(kind, payload && payload.fn, r.detail);
        if (r.reload) setTimeout(function () { location.reload(); }, 2500);
        throw err;
      }
      return r.result;
    });
  }
  function apiCall(quiet, fn, args) {
    return send('call', { fn: fn, args: args, quiet: quiet }).then(function (res) {
      if (res && typeof res === 'object' && res.ok === false) {
        var err = new Error(res.error || 'That didn\'t work.'); err.uiApi = true; err.expected = true; err.result = res;
        throw err;
      }
      return res;
    });
  }
  UI.api = function (fn) { return apiCall(false, fn, Array.prototype.slice.call(arguments, 1)); };
  UI.apiQuiet = function (fn) { return apiCall(true, fn, Array.prototype.slice.call(arguments, 1)); };
  /* Errors nobody caught become a toast, so a failed action is never silent. */
  window.addEventListener('unhandledrejection', function (e) {
    if (e.reason && e.reason.uiApi) { e.preventDefault(); UI.toast(e.reason.message, 'error'); }
  });

  /* Sign in / up / out. On success it navigates: to where the visitor was heading (UI.after) or home
     after signing in, to the landing page after signing out. */
  UI.auth = function (kind, payload) {
    return send(kind, payload || {}).then(function (r) {
      if (r && r.ok === false) { var err = new Error(r.error); err.uiApi = true; err.expected = true; throw err; }
      if (r && 'me' in r && (r.me || kind === 'logout')) {
        UI.me = r.me || null;
        var target = r.me ? (UI.after || '#' + UI.config.home) : '#' + UI.config.landing;
        UI.after = null;
        if (location.hash === target) route(); else location.hash = target;
      }
      return r;
    });
  };
  /* Update the signed-in user's details (e.g. a new name) and redraw the header, without reloading the page. */
  UI.setMe = function (me) {
    UI.me = me || null;
    if (shellRoot) renderChrome(current.name);
  };

  /* ------------------------------------------------------------------ pages and routing */
  UI.page = function (name, opts, mount) {
    if (typeof opts === 'function') { mount = opts; opts = {}; }
    opts.name = name; opts.mount = mount;
    UI.pages[name] = opts;
  };
  UI.allowed = function (p) {
    if (!p) return false;
    if (p.auth === 'user') return !!UI.me;
    if (p.auth === 'admin') return !!(UI.me && UI.me.is_admin);
    if (p.auth === 'guest') return !UI.me;
    return true;
  };
  UI.navPages = function () {
    return Object.keys(UI.pages).map(function (k) { return UI.pages[k]; })
      .filter(function (p) { return p.nav && UI.allowed(p) && (!p.when || p.when()); })
      .sort(function (a, b) { return (a.order || 50) - (b.order || 50); });
  };
  UI.parseHash = function () {
    var h = (location.hash || '').replace(/^#!?\/?/, '');
    var parts = h.split('?')[0].split('/').filter(function (x) { return x !== ''; }).map(decodeURIComponent);
    return { name: parts[0] || '', args: parts.slice(1) };
  };
  UI.hashFor = function (name) {
    var args = Array.prototype.slice.call(arguments, 1).filter(function (a) { return a != null && a !== ''; });
    return '#' + [name].concat(args.map(encodeURIComponent)).join('/');
  };
  UI.go = function (name) {
    var h = UI.hashFor.apply(null, arguments);
    if (location.hash === h) route(); else location.hash = h;
  };
  UI.refresh = function () { route(); };
  UI.after = null;  // where to go after signing in

  var shellRoot = null, view = null, current = { name: null, destroy: null }, routeSeq = 0;

  function defaultPage() { return UI.me ? UI.config.home : UI.config.landing; }

  function route() {
    var r = UI.parseHash(), name = r.name || defaultPage(), p = UI.pages[name];
    if (!p) { name = defaultPage(); p = UI.pages[name]; r.args = []; }
    if (p.auth === 'guest' && UI.me) { p = UI.pages[UI.config.home]; name = UI.config.home; r.args = []; }
    if ((p.auth === 'user' || p.auth === 'admin') && !UI.me) {
      UI.after = location.hash && location.hash !== '#' ? location.hash : null;
      p = UI.pages.auth; name = 'auth'; r.args = [];
    }
    if (p.auth === 'admin' && !(UI.me && UI.me.is_admin)) {
      UI.toast('That page is for admins only.', 'error');
      p = UI.pages[UI.config.home]; name = UI.config.home; r.args = [];
    }
    var seq = ++routeSeq;
    window.UI_READY = false;
    if (current.destroy) { try { current.destroy(); } catch (e) { console.error(e); } }
    current = { name: name, args: r.args, destroy: null };
    if (shellRoot) {
      shellRoot.className = 'ui ui-shell page-' + name + (UI.me ? ' signed-in' : ' signed-out') + (p.chrome === false ? ' no-chrome' : '');
      renderChrome(name);
    }
    // A fresh element for every page, so listeners a page adds to `view` never pile up.
    var fresh = view.cloneNode(false);
    view.parentNode.replaceChild(fresh, view);
    view = fresh;
    window.scrollTo(0, 0);
    document.title = (p.title ? (typeof p.title === 'function' ? p.title(r.args) : p.title) + ' · ' : '') + UI.config.name;
    var ctx = { name: name, args: r.args, me: UI.me, go: UI.go, api: UI.api, page: p };
    var out;
    try { out = p.mount(view, ctx); } catch (e) { console.error(e); out = Promise.reject(e); }
    var ready = out && typeof out.then === 'function' ? out : (out && out.ready) || Promise.resolve();
    if (out && out.destroy) current.destroy = out.destroy;
    Promise.resolve(ready).then(function () { if (seq === routeSeq) window.UI_READY = true; },
      function (e) {
        if (seq !== routeSeq) return;
        console.error(e);
        if (!view.innerHTML) view.innerHTML = '<div class="ui-wrap"><div class="ui-empty">' + UI.icon('info') +
          '<h3>This page didn\'t load</h3><p class="muted">' + UI.esc(e && e.message || 'Something went wrong.') + '</p>' +
          '<button class="ui-btn" onclick="UI.refresh()">Try again</button></div></div>';
        window.UI_READY = true;
      });
  }
  UI.current = function () { return current; };

  /* The shell's parts come from web/app.js: UI.shell = {header(me, active), footer(me), tabbar(me, active)} */
  function renderChrome(active) {
    var S = UI.shell || {};
    var hd = shellRoot.querySelector('[data-ui-header]'), ft = shellRoot.querySelector('[data-ui-footer]'), tb = shellRoot.querySelector('[data-ui-tabbar]');
    if (hd) hd.innerHTML = S.header ? S.header(UI.me, active) : '';
    if (ft) ft.innerHTML = S.footer ? S.footer(UI.me, active) : '';
    if (tb) tb.innerHTML = S.tabbar ? S.tabbar(UI.me, active) : '';
  }
  UI.renderChrome = function () { if (shellRoot) renderChrome(current.name); };

  /* Called by client_code/Main.py (and by the local harness) once the page is up. */
  UI.start = function (node, bridgeFn, bootJson) {
    bridge = bridgeFn;
    var boot = typeof bootJson === 'string' ? JSON.parse(bootJson || '{}') : (bootJson || {});
    UI.me = boot.me || null;
    var host = node && node.matches && node.matches('[data-ui-app]') ? node : (node && node.querySelector('[data-ui-app]')) || node || document.body;
    host.innerHTML = '<div class="ui ui-shell">' +
      '<header class="ui-header" data-ui-header></header>' +
      '<main class="ui-main" data-ui-view></main>' +
      '<footer class="ui-footer" data-ui-footer></footer>' +
      '<nav class="ui-tabbar" data-ui-tabbar aria-label="Main"></nav></div>';
    shellRoot = host.firstChild;
    view = host.querySelector('[data-ui-view]');
    if (UI.shell && UI.shell.wire) UI.shell.wire(shellRoot);
    window.addEventListener('hashchange', route);
    route();
  };

  /* ------------------------------------------------------------------ feedback (footer + menu)
     All feedback goes to Prepsto. The widget tag in head.html (data-prepsto="CODE") slides its panel in;
     any [data-feedback] or [data-prepsto-open] element opens it. If the widget hasn't loaded, the panel opens in a new tab.
     There is no in-app feedback form any more: Admin -> Feedback only lists older messages (and app requests). */
  UI.feedback = function () {
    if (window.Prepsto && window.Prepsto.open) { window.Prepsto.open(); return; }
    var tag = document.querySelector('script[data-prepsto]');
    var code = tag && tag.getAttribute('data-prepsto');
    if (code && code.indexOf('__') !== 0) window.open('https://prepsto.com/#f/' + encodeURIComponent(code), '_blank', 'noopener');
    else UI.toast('Feedback is not set up yet.', 'error');
  };

  /* Shared clicks: [data-go="page/arg"], [data-feedback], [data-theme-set] anywhere in the app. */
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-go],[data-feedback],[data-theme-set]');
    if (!el) return;
    if (el.hasAttribute('data-go')) { e.preventDefault(); UI.go.apply(null, el.getAttribute('data-go').split('/')); }
    else if (el.hasAttribute('data-feedback')) { e.preventDefault(); UI.feedback(el.getAttribute('data-feedback') || null); }
    else if (el.hasAttribute('data-theme-set')) { e.preventDefault(); UI.setTheme(el.getAttribute('data-theme-set')); if (UI.shell && UI.shell.onTheme) UI.shell.onTheme(); }
  });
})();


/* app.js: this app's identity and frame: name, header, footer, phone tab bar.
   Pages live in web/pages/*.html. The engine (window.UI) is web/core.js. */
(function () {
  'use strict';
  UI.configure({
    name: 'Good Landlord',
    key: 'goodlandlord',          // prefix for this app's browser storage
    tagline: 'Fair numbers, fair records: for landlords and their tenants.',   // footer line
    home: 'home',                // first page after signing in
    landing: 'landing'           // first page for visitors who aren't signed in
  });

  var esc = UI.esc;

  function brand() {
    return '<a class="ui-brand" href="#" data-go="' + (UI.me ? UI.config.home : UI.config.landing) + '" aria-label="' + esc(UI.config.name) + ' home">' +
      '<img src="_/theme/icon.svg" alt="" width="32" height="32"><span>' + esc(UI.config.name) + '</span></a>';
  }

  function themeSwitch() {
    var t = UI.theme();
    return '<div class="ui-seg" role="group" aria-label="Appearance">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
      return '<button type="button" data-theme-set="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
    }).join('') + '</div>';
  }

  function userMenu(me) {
    return '<div class="ui-menu" data-menu hidden>' +
      '<div class="ui-menu-head"><strong>' + esc(me.name) + '</strong><span class="muted small">' + esc(me.email) + '</span></div>' +
      '<a href="#profile" data-go="profile">' + UI.icon('user') + 'Your profile</a>' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<div class="ui-menu-block"><span class="small muted">Appearance</span>' + themeSwitch() + '</div>' +
      '<button type="button" data-feedback>' + UI.icon('chat') + 'Submit feedback</button>' +
      '<button type="button" data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms</button>' +
      '<button type="button" data-signout>' + UI.icon('logout') + 'Sign out</button></div>';
  }

  UI.shell = {
    header: function (me, active) {
      var nav = UI.navPages();
      return '<div class="ui-header-in">' + brand() +
        (me ? '<nav class="ui-nav" aria-label="Main">' + nav.map(function (p) {
          return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
        }).join('') + '</nav>' : '') +
        '<div class="ui-header-right">' +
        (me ? '<button type="button" class="ui-avatar-btn" data-menu-toggle aria-label="Your account" aria-haspopup="true">' + esc(UI.initials(me.name)) + '</button>' + userMenu(me)
          : (active === 'auth' ? '' : '<a class="ui-btn ghost" href="#auth" data-go="auth">Sign in</a><a class="ui-btn primary" href="#auth/signup" data-go="auth/signup">Get started</a>')) +
        '</div></div>';
    },
    footer: function (me) {
      return '<div class="ui-footer-in"><div class="ui-footer-brand">' + brand() + '<p class="muted small">' + esc(UI.config.tagline) + '</p></div>' +
        '<div class="ui-footer-links">' +
        '<a href="#landing" data-go="landing">About</a>' +
        '<a href="https://prepsto.com/#f/ba8qvqf" target="_blank" rel="noopener" data-prepsto-open>Submit feedback</a>' +
        '<button type="button" data-lk-open="overview">Privacy &amp; Terms</button>' +
        '</div><p class="ui-footer-legal small muted">© ' + new Date().getFullYear() + ' ' + esc(UI.config.name) + '</p></div>';
    },
    tabbar: function (me, active) {
      var nav = UI.navPages();
      if (!me || nav.length < 2) return '';
      return nav.slice(0, 4).map(function (p) {
        return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
      }).join('') + '<a href="#profile" class="' + (active === 'profile' ? 'on' : '') + '">' + UI.icon('user') + '<span>You</span></a>';
    },
    wire: function (root) {
      root.addEventListener('click', function (e) {
        var t = e.target.closest('[data-menu-toggle]');
        var menu = root.querySelector('[data-menu]');
        if (t && menu) { menu.hidden = !menu.hidden; t.setAttribute('aria-expanded', String(!menu.hidden)); return; }
        if (e.target.closest('[data-signout]')) { UI.auth('logout').then(function () { UI.toast('Signed out. See you soon!'); }); }
        if (menu && !menu.hidden && !e.target.closest('[data-menu] .ui-seg')) menu.hidden = true;
      });
      document.addEventListener('keydown', function (e) {
        var menu = root.querySelector('[data-menu]');
        if (e.key === 'Escape' && menu) menu.hidden = true;
      });
    },
    onTheme: function () {  // redraw the menu's Auto/Light/Dark buttons and keep the menu open
      var menu = document.querySelector('[data-menu]'), open = menu && !menu.hidden;
      UI.renderChrome();
      if (open) document.querySelector('[data-menu]').hidden = false;
    }
  };
})();


/* ===== _gl.html ===== */
(function () {
  'use strict';
  var esc = UI.esc;
  var GL = window.GL = { data: null, cur: 'CAD' };

  // extra icons
  var I = UI.ICONS;
  I.coins = '<ellipse cx="9" cy="7" rx="6" ry="2.6"/><path d="M3 7v4c0 1.4 2.7 2.6 6 2.6s6-1.2 6-2.6V7"/><path d="M9 13.6V17c0 1.4 2.7 2.6 6 2.6s6-1.2 6-2.6v-4c0-1.4-2.7-2.6-6-2.6"/>';
  I.chart = '<path d="M4 20V4"/><path d="M4 20h16"/><path d="m7 15 4-5 3 3 5-7"/>';
  I.key = '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3M15 8l2 2"/>';
  I.wrench = '<path d="M14.5 6.5a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3z"/><path d="M14.5 6.5 17 4a4 4 0 0 0-2.5 2.5z"/>';
  I.seal = '<path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z"/><path d="m9 12 2 2 4-4"/>';
  I.link = '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>';
  I.download = '<path d="M12 4v11M7 10l5 5 5-5"/><path d="M5 20h14"/>';
  I.receipt = '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>';
  I.house = I.home;
  I.send = '<path d="M4 12 20 4l-6 16-3-7z"/><path d="m11 13 9-9"/>';
  I.percent = '<path d="M19 5 5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>';
  I.flame = '<path d="M12 21c-4 0-7-2.8-7-6.5 0-4 3.5-6 4-10 2.5 2 3.5 4 3.5 6 1-1 1.5-2.5 1.5-3.5 2 1.5 5 4.5 5 7.5 0 3.7-3 6.5-7 6.5z"/>';

  GL.DOORS = { red: '#b4502a', honey: '#e19a35', sage: '#6f8f58', blue: '#3f6f98', plum: '#7d4a6a', walnut: '#6b4a33' };
  GL.KINDS = [['house', 'House'], ['duplex', 'Duplex'], ['triplex', 'Triplex'], ['condo', 'Condo'], ['apartment', 'Apartment building'], ['townhouse', 'Townhouse'], ['cottage', 'Cottage'], ['other', 'Other']];
  GL.FREQ = [['monthly', 'Monthly'], ['semi_monthly', 'Twice a month'], ['biweekly', 'Every 2 weeks'], ['accelerated_biweekly', 'Every 2 weeks (accelerated)'], ['weekly', 'Weekly']];
  GL.STATUS = [['requested', 'Requested'], ['acknowledged', 'Seen'], ['scheduled', 'Scheduled'], ['in_progress', 'In progress'], ['done', 'Done'], ['declined', 'Declined']];
  GL.STATUS_LABEL = {}; GL.STATUS.forEach(function (s) { GL.STATUS_LABEL[s[0]] = s[1]; });
  GL.TASK_CATS = [['plumbing', 'Plumbing'], ['heating', 'Heating & cooling'], ['electrical', 'Electrical'], ['appliance', 'Appliance'], ['doors_windows', 'Doors & windows'],
    ['pests', 'Pests'], ['outdoor', 'Outdoor & yard'], ['safety', 'Safety (alarms, locks)'], ['cleaning', 'Cleaning'], ['other', 'Something else']];
  GL.TASK_CAT_LABEL = {}; GL.TASK_CATS.forEach(function (s) { GL.TASK_CAT_LABEL[s[0]] = s[1]; });
  GL.REGIONS = { ca: 'Canada', qc: 'Québec', us: 'United States', uk: 'United Kingdom', other: 'Elsewhere' };
  GL.TAX_FORM = {
    ca: 'These lines follow the CRA\'s Form T776 (Statement of Real Estate Rentals).',
    qc: 'These lines follow the CRA\'s Form T776; in Québec you also report rental income on form TP-128.',
    us: 'These lines follow the IRS Schedule E (Supplemental Income and Loss).',
    uk: 'These lines follow the SA105 UK property pages. Note: in the UK, mortgage interest gets a 20% tax credit instead of being deducted.',
    other: 'Most countries ask for the same lines: rents, then expenses by type.'
  };

  /* ------------------------------------------------------------------ data */
  GL.load = function (quiet) {
    return (quiet ? UI.apiQuiet : UI.api)('get_portfolio').then(function (d) {
      GL.data = d; GL.cur = d.prefs.currency || 'CAD';
      GL.cat = {}; d.categories.forEach(function (c) { GL.cat[c.id] = c; });
      GL.byId = {}; d.properties.forEach(function (p) { GL.byId[p.id] = p; });
      GL.today = GL.d(d.today);
      return d;
    });
  };
  GL.prop = function (id) { return GL.byId && GL.byId[id]; };
  GL.activeProps = function () { return GL.data.properties.filter(function (p) { return !p.archived; }); };
  GL.tenancyById = function (id) { return GL.data.tenancies.filter(function (t) { return t.id === id; })[0]; };

  /* ------------------------------------------------------------------ dates + money */
  GL.d = function (iso) { if (!iso) return null; if (iso instanceof Date) return iso; return iso.length <= 10 ? new Date(iso + 'T12:00:00') : new Date(iso); };
  GL.iso = function (dt) { var m = dt.getMonth() + 1, d = dt.getDate(); return dt.getFullYear() + '-' + (m < 10 ? '0' : '') + m + '-' + (d < 10 ? '0' : '') + d; };
  GL.addMonths = function (dt, n) { var x = new Date(dt.getTime()); var day = x.getDate(); x.setDate(1); x.setMonth(x.getMonth() + n); x.setDate(Math.min(day, new Date(x.getFullYear(), x.getMonth() + 1, 0).getDate())); return x; };
  GL.addYears = function (dt, n) { return GL.addMonths(dt, Math.round(n * 12)); };
  GL.ym = function (dt) { var m = dt.getMonth() + 1; return dt.getFullYear() + '-' + (m < 10 ? '0' : '') + m; };
  GL.monthName = function (ym, short) { var p = ym.split('-'); return new Date(+p[0], +p[1] - 1, 15).toLocaleDateString(undefined, short ? { month: 'short' } : { month: 'long', year: 'numeric' }); };
  GL.yearsBetween = function (a, b) { return (b - a) / (365.25 * 864e5); };
  GL.money = function (v, o) {
    o = o || {};
    v = +v || 0;
    var opts = { style: 'currency', currency: GL.cur, maximumFractionDigits: o.cents ? 2 : 0, minimumFractionDigits: o.cents ? 2 : 0 };
    if (o.short && Math.abs(v) >= 10000) { opts.notation = 'compact'; opts.maximumFractionDigits = Math.abs(v) >= 1e6 ? 2 : 0; opts.minimumFractionDigits = 0; }
    var s;
    try { s = new Intl.NumberFormat(undefined, opts).format(Math.abs(v)); } catch (e) { s = '$' + Math.round(Math.abs(v)).toLocaleString(); }
    if (v < 0) return '−' + s;
    return (o.sign && v > 0 ? '+' : '') + s;
  };
  GL.signed = function (v, o) { return '<span class="num ' + (v >= 0 ? 'gl-pos' : 'gl-neg') + '">' + GL.money(v, Object.assign({ sign: true }, o || {})) + '</span>'; };
  GL.pct = function (v, digits) { return (v >= 0 ? '' : '−') + Math.abs(v).toFixed(digits == null ? 1 : digits) + '%'; };

  /* ------------------------------------------------------------------ mortgage maths
     Canadian fixed-rate mortgages compound semi-annually; US ones monthly. Payments: monthly, twice a month,
     every 2 weeks, accelerated (half the monthly payment every 2 weeks) or weekly. */
  var PER = { monthly: 12, semi_monthly: 24, biweekly: 26, accelerated_biweekly: 26, weekly: 52 };
  function rateFor(rate, n, comp) { var r = (+rate || 0) / 100; if (r <= 0) return 0; return comp === 'monthly' ? Math.pow(1 + r / 12, 12 / n) - 1 : Math.pow(1 + r / 2, 2 / n) - 1; }
  GL.plan = function (m, overrides) {
    m = Object.assign({}, m, overrides || {});
    var n = PER[m.frequency] || 12, i = rateFor(m.rate, n, m.compounding), N = Math.max(1, Math.round((+m.amort_years || 25) * n)), L = +m.amount || 0, P;
    if (m.frequency === 'accelerated_biweekly') {
      var i12 = rateFor(m.rate, 12, m.compounding), N12 = Math.round((+m.amort_years || 25) * 12);
      P = (i12 ? L * i12 / (1 - Math.pow(1 + i12, -N12)) : L / N12) / 2;
    } else P = i ? L * i / (1 - Math.pow(1 + i, -N)) : L / N;
    var payoff = !L ? 0 : i ? Math.ceil(-Math.log(1 - L * i / P) / Math.log(1 + i) - 1e-9) : Math.ceil(L / P);
    return { m: m, n: n, i: i, N: N, L: L, P: P, payoff: payoff, start: GL.d(m.start_date) || new Date(), monthly: P * n / 12 };
  };
  GL.balanceAfter = function (p, k) {
    k = Math.max(0, Math.min(k, p.payoff));
    if (k >= p.payoff) return 0;
    var b = p.i ? p.L * Math.pow(1 + p.i, k) - p.P * (Math.pow(1 + p.i, k) - 1) / p.i : p.L - p.P * k;
    return Math.max(0, b);
  };
  GL.paidBy = function (p, date) {
    if (!date || date < p.start) return 0;
    var k;
    if (p.n === 12) {
      k = (date.getFullYear() - p.start.getFullYear()) * 12 + date.getMonth() - p.start.getMonth();
      if (date.getDate() < p.start.getDate()) k--;
    } else k = Math.floor((date - p.start) / 864e5 / (p.n === 26 ? 14 : p.n === 52 ? 7 : 365.25 / 24));
    return Math.max(0, Math.min(k, p.payoff));
  };
  GL.balanceAt = function (p, date) { return GL.balanceAfter(p, GL.paidBy(p, date)); };
  function paidAmount(p, k1, k2) {
    if (k2 <= k1) return 0;
    if (k2 >= p.payoff && p.payoff > 0) { var last = GL.balanceAfter(p, p.payoff - 1) * (1 + p.i); return p.P * (Math.min(k2, p.payoff) - k1 - 1) + last; }
    return p.P * (k2 - k1);
  }
  /* What was paid between two dates, split into interest and principal. */
  GL.paidBetween = function (p, d1, d2) {
    var k1 = GL.paidBy(p, d1), k2 = GL.paidBy(p, d2);
    var total = paidAmount(p, k1, k2), principal = GL.balanceAfter(p, k1) - GL.balanceAfter(p, k2);
    return { total: total, principal: principal, interest: Math.max(0, total - principal), count: Math.max(0, k2 - k1) };
  };
  GL.renewal = function (p) { return GL.addYears(p.start, +p.m.term_years || 5); };
  GL.mortgagesOf = function (propId) { return GL.data.mortgages.filter(function (m) { return m.property_id === propId; }).map(function (m) { return GL.plan(m); }); };

  /* ------------------------------------------------------------------ property numbers */
  GL.metrics = function (prop, opts) {
    opts = opts || {};
    var today = GL.today, yearAgo = GL.addMonths(today, -12);
    var plans = GL.mortgagesOf(prop.id);
    var balance = 0, loan = 0, mortMonthly = 0;
    plans.forEach(function (p) { balance += GL.balanceAt(p, today); loan += p.L; if (GL.balanceAt(p, today) > 0) mortMonthly += p.monthly; });
    var tens = GL.data.tenancies.filter(function (t) { return t.property_id === prop.id && t.status === 'active'; });
    var rent = tens.reduce(function (s, t) { return s + t.rent; }, 0);
    var led = GL.data.ledger.filter(function (e) { return e.property_id === prop.id; });
    var first = null, inc12 = 0, otherInc12 = 0, opex12 = 0, incAll = 0, opexAll = 0, capAll = 0;
    led.forEach(function (e) {
      var d = GL.d(e.date), cap = e.category === 'capital';
      if (!first || d < first) first = d;
      if (e.kind === 'income') incAll += e.amount; else if (cap) capAll += e.amount; else opexAll += e.amount;
      if (d > yearAgo && d <= today) {
        if (e.kind === 'income') { inc12 += e.amount; if (e.category !== 'rent') otherInc12 += e.amount; }
        else if (!cap) opex12 += e.amount;
      }
    });
    var covered = first ? Math.max(1, Math.min(12, Math.round(GL.yearsBetween(first, today) * 12) || 1)) : 12;
    var opexMonthly = opex12 / covered, otherMonthly = otherInc12 / covered;
    var cashMonthly = rent + otherMonthly - opexMonthly - mortMonthly;
    var bought = GL.d(prop.purchase_date) || first || today;
    var since = first && first > bought ? first : bought;
    var mortPaidRecorded = 0;
    plans.forEach(function (p) { mortPaidRecorded += GL.paidBetween(p, since, today).total; });
    var cfRecorded = first ? incAll - opexAll - mortPaidRecorded : 0;
    var invested = (+prop.down_payment || 0) + (+prop.closing_costs || 0) + (+prop.improvements || 0) + capAll;
    var value = opts.value != null ? opts.value : (+prop.current_value || +prop.purchase_price || 0);
    var sellPct = opts.sellPct != null ? opts.sellPct : (prop.selling_pct != null ? +prop.selling_pct : 5);
    var sellCost = value * sellPct / 100;
    var proceeds = value - sellCost - balance;
    var profit = proceeds - invested + cfRecorded;
    var years = Math.max(1 / 12, GL.yearsBetween(bought, today));
    var roi = invested > 0 ? profit / invested : 0;
    var annual = invested > 0 && 1 + roi > 0 ? Math.pow(1 + roi, 1 / years) - 1 : (invested > 0 ? -1 : 0);
    var noi = (rent + otherMonthly - opexMonthly) * 12;
    return { prop: prop, plans: plans, balance: balance, loan: loan, mortMonthly: mortMonthly, tenancies: tens, rent: rent, opexMonthly: opexMonthly,
      otherMonthly: otherMonthly, cashMonthly: cashMonthly, inc12: inc12, opex12: opex12, covered: covered, first: first, since: since,
      cfRecorded: cfRecorded, capAll: capAll, invested: invested, value: value, sellPct: sellPct, sellCost: sellCost, proceeds: proceeds,
      equity: value - balance, profit: profit, roi: roi, annual: annual, years: years, bought: bought,
      capRate: value > 0 ? noi / value : 0, cashOnCash: invested > 0 ? cashMonthly * 12 / invested : 0,
      appreciationGain: value - (+prop.purchase_price || 0), paydown: loan - balance,
      gap: plans.length ? ((+prop.purchase_price || 0) - loan) - (+prop.down_payment || 0) : 0 };
  };
  GL.verdict = function (annual, profit) {
    if (profit < 0 && annual < 0) return { key: 'bad', label: 'Losing money', glow: .15, text: 'If you sold today, you\'d get back less than you put in.' };
    if (annual < .04) return { key: 'meh', label: 'Modest', glow: .45, text: 'You\'re ahead, but slower than a safe savings account would grow.' };
    if (annual < .08) return { key: 'good', label: 'A good deal', glow: .8, text: 'A solid return on the money you put in.' };
    return { key: 'great', label: 'A great deal', glow: 1, text: 'Your money is working hard: well above what the stock market typically returns.' };
  };
  /* Year-by-year if you keep it: value, debt, cash flow, and profit if sold that year. */
  GL.project = function (mt, o) {
    var rows = [], cum = 0, today = GL.today;
    var a = o.appr / 100, g = o.rentGrowth / 100, e = o.costGrowth / 100, s = o.sellPct / 100;
    for (var y = 0; y <= o.years; y++) {
      var at = GL.addYears(today, y), prev = GL.addYears(today, y - 1);
      var bal = 0, paid = 0, interest = 0;
      mt.plans.forEach(function (p) { bal += GL.balanceAt(p, at); if (y > 0) { var pb = GL.paidBetween(p, prev, at); paid += pb.total; interest += pb.interest; } });
      var cf = 0;
      if (y > 0) cf = 12 * ((mt.rent + mt.otherMonthly) * Math.pow(1 + g, y - 1) - mt.opexMonthly * Math.pow(1 + e, y - 1)) - paid;
      cum += cf;
      var val = o.value * Math.pow(1 + a, y);
      var profit = val * (1 - s) - bal - mt.invested + mt.cfRecorded + cum;
      var yrs = mt.years + y, roi = mt.invested > 0 ? profit / mt.invested : 0;
      rows.push({ y: y, date: at, value: val, balance: bal, equity: val - bal, cf: cf, cum: cum, profit: profit, interest: interest,
        annual: mt.invested > 0 && 1 + roi > 0 ? Math.pow(1 + roi, 1 / Math.max(yrs, 1 / 12)) - 1 : -1 });
    }
    return rows;
  };

  /* ------------------------------------------------------------------ houses */
  GL.house = function (o) {
    o = o || {};
    var door = GL.DOORS[o.door] || GL.DOORS.red, glow = o.glow == null ? .8 : o.glow, w = o.size || 120, kind = o.kind || 'house';
    var win = function (x, y, ww, hh) {
      return '<rect class="trim" x="' + (x - 1.5) + '" y="' + (y - 1.5) + '" width="' + (ww + 3) + '" height="' + (hh + 3) + '" rx="2"/>' +
        '<rect class="glass" x="' + x + '" y="' + y + '" width="' + ww + '" height="' + hh + '" rx="1"/>' +
        '<rect class="glow" x="' + x + '" y="' + y + '" width="' + ww + '" height="' + hh + '" rx="1" opacity="' + glow.toFixed(2) + '"/>' +
        '<path d="M' + (x + ww / 2) + ' ' + y + 'v' + hh + 'M' + x + ' ' + (y + hh / 2) + 'h' + ww + '" stroke="var(--gl-trim)" stroke-width="1.2" opacity=".55"/>';
    };
    var smoke = o.smoke ? '<g class="smoke"><circle cx="86" cy="14" r="4"/><circle cx="86" cy="14" r="4"/><circle cx="86" cy="14" r="4"/></g>' : '';
    var body;
    if (kind === 'condo' || kind === 'apartment') {
      body = '<rect class="wall2" x="22" y="10" width="76" height="96" rx="3"/><rect class="roof" x="18" y="6" width="84" height="8" rx="2"/>';
      for (var r = 0; r < 4; r++) for (var c = 0; c < 3; c++) body += win(30 + c * 22, 20 + r * 19, 14, 12);
      body += '<rect x="51" y="92" width="18" height="14" rx="2" fill="' + door + '"/>';
    } else if (kind === 'duplex' || kind === 'triplex') {
      body = '<rect class="roof" x="80" y="12" width="9" height="20"/>' + smoke +
        '<rect class="wall" x="20" y="34" width="80" height="72"/><path class="roof" d="M12 38 60 6l48 32z"/>' +
        win(30, 44, 18, 16) + win(72, 44, 18, 16) + win(30, 70, 18, 16) +
        '<rect x="66" y="74" width="16" height="32" rx="2" fill="' + door + '"/><circle cx="78" cy="91" r="1.6" fill="var(--gl-glow)"/>' +
        (kind === 'triplex' ? win(51, 18, 18, 12) : win(53, 20, 14, 10));
    } else {
      body = '<rect class="roof" x="80" y="20" width="9" height="20"/>' + smoke +
        '<rect class="wall" x="20" y="50" width="80" height="56"/><path class="roof" d="M10 54 60 14l50 40z"/>' +
        win(29, 62, 18, 16) + win(73, 62, 18, 16) +
        '<rect x="52" y="76" width="16" height="30" rx="2" fill="' + door + '"/><circle cx="64" cy="92" r="1.6" fill="var(--gl-glow)"/>' +
        '<rect class="trim" x="48" y="104" width="24" height="3" rx="1.5" opacity=".6"/>';
    }
    return '<svg class="gl-house" viewBox="0 0 120 110" width="' + w + '" height="' + Math.round(w * 110 / 120) + '" aria-hidden="true">' + body + '</svg>';
  };
  GL.glowFor = function (cashMonthly) { return cashMonthly >= 0 ? Math.min(1, .55 + cashMonthly / 1500) : Math.max(.12, .45 + cashMonthly / 1500); };

  /* ------------------------------------------------------------------ charts (one axis; legend; hover tooltip) */
  function niceStep(span, n) { var raw = span / n, mag = Math.pow(10, Math.floor(Math.log10(raw || 1))), f = raw / mag; return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag; }
  function scaleY(min, max, h, top) {
    if (min === max) { max = min + 1; }
    var step = niceStep(max - min, 4), lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
    var f = function (v) { return top + h - (v - lo) / (hi - lo) * h; }; f.ticks = []; for (var t = lo; t <= hi + step / 2; t += step) f.ticks.push(t); return f;
  }
  function wireTip(box, svgW, xs, html) {
    var tip = document.createElement('div'); tip.className = 'gl-tip'; tip.hidden = true; box.appendChild(tip);
    var guide = box.querySelector('[data-guide]');
    function at(clientX) {
      var r = box.getBoundingClientRect(), x = (clientX - r.left) / r.width * svgW, best = 0;
      xs.forEach(function (v, i) { if (Math.abs(v - x) < Math.abs(xs[best] - x)) best = i; });
      tip.innerHTML = html(best); tip.hidden = false;
      tip.style.left = Math.max(70, Math.min(r.width - 70, xs[best] / svgW * r.width)) + 'px'; tip.style.top = '30px';
      if (guide) { guide.setAttribute('x1', xs[best]); guide.setAttribute('x2', xs[best]); guide.style.opacity = 1; }
    }
    box.addEventListener('pointermove', function (e) { at(e.clientX); });
    box.addEventListener('pointerdown', function (e) { at(e.clientX); });
    box.addEventListener('pointerleave', function () { tip.hidden = true; if (guide) guide.style.opacity = 0; });
  }
  /* Lines over time. series: [{label, color, values[], fill: index of series to fill down to}] */
  GL.lineChart = function (box, o) {
    var W = Math.max(280, box.clientWidth || 600), H = o.height || 240, L = 62, R = 14, T = 14, B = 28, ph = H - T - B, pw = W - L - R;
    var all = []; o.series.forEach(function (s) { all = all.concat(s.values); });
    var y = scaleY(Math.min(0, Math.min.apply(null, all)), Math.max.apply(null, all), ph, T);
    var n = o.labels.length, xs = o.labels.map(function (_, i) { return L + (n === 1 ? pw / 2 : i / (n - 1) * pw); });
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(o.title || 'Chart') + '">';
    y.ticks.forEach(function (t) { svg += '<line class="ax" x1="' + L + '" x2="' + (W - R) + '" y1="' + y(t) + '" y2="' + y(t) + '"/><text class="ax-t" x="' + (L - 8) + '" y="' + (y(t) + 4) + '" text-anchor="end">' + esc(GL.money(t, { short: true })) + '</text>'; });
    var every = Math.ceil(n / Math.max(2, Math.floor(pw / 70)));
    o.labels.forEach(function (lb, i) { if (i % every === 0 || (i === n - 1 && (n - 1) % every >= every * .6)) svg += '<text class="ax-t" x="' + xs[i] + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(lb) + '</text>'; });
    if (y.ticks[0] < 0) svg += '<line class="zero" x1="' + L + '" x2="' + (W - R) + '" y1="' + y(0) + '" y2="' + y(0) + '"/>';
    o.series.forEach(function (s) {
      if (s.fillTo != null) {
        var other = o.series[s.fillTo].values;
        svg += '<path d="M' + xs.map(function (x, i) { return x + ' ' + y(s.values[i]); }).join('L') + 'L' + xs.slice().reverse().map(function (x, j) { return x + ' ' + y(other[n - 1 - j]); }).join('L') + 'Z" fill="' + s.color + '" opacity=".13"/>';
      }
    });
    o.series.forEach(function (s) {
      svg += '<path d="M' + xs.map(function (x, i) { return x + ' ' + y(s.values[i]); }).join('L') + '" fill="none" stroke="' + s.color + '" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"' + (s.dash ? ' stroke-dasharray="5 4"' : '') + '/>';
    });
    svg += '<line data-guide x1="0" x2="0" y1="' + T + '" y2="' + (T + ph) + '" stroke="var(--c-faint)" stroke-width="1" style="opacity:0"/></svg>';
    box.innerHTML = '<div class="gl-chart">' + svg + '</div><div class="gl-key">' + o.series.map(function (s) {
      return '<span><i class="line" style="background:' + s.color + '"></i>' + esc(s.label) + '</span>'; }).join('') + (o.note ? '<span>' + esc(o.note) + '</span>' : '') + '</div>';
    wireTip(box.querySelector('.gl-chart'), W, xs, function (i) {
      return '<div class="muted">' + esc(o.tipLabels ? o.tipLabels[i] : o.labels[i]) + '</div>' + o.series.map(function (s) {
        return '<div><i style="display:inline-block;width:9px;height:9px;border-radius:3px;background:' + s.color + ';margin-right:6px"></i>' + esc(s.label) + ': <b>' + esc(GL.money(s.values[i])) + '</b></div>'; }).join('') +
        (o.extraTip ? o.extraTip(i) : '');
    });
  };
  /* Grouped or stacked bars. series: [{label, color, values[]}] */
  GL.barChart = function (box, o) {
    var W = Math.max(280, box.clientWidth || 600), H = o.height || 220, L = 58, R = 10, T = 12, B = 28, ph = H - T - B, pw = W - L - R;
    var n = o.labels.length, k = o.series.length, max = 0, min = 0;
    for (var i = 0; i < n; i++) {
      if (o.stacked) { var tot = 0; o.series.forEach(function (s) { tot += s.values[i]; }); max = Math.max(max, tot); }
      else o.series.forEach(function (s) { max = Math.max(max, s.values[i]); min = Math.min(min, s.values[i]); });
    }
    var y = scaleY(min, max, ph, T), slot = pw / n, gap = 2, bw = o.stacked ? Math.min(34, slot * .62) : Math.min(18, (slot * .7 - gap * (k - 1)) / k);
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="' + esc(o.title || 'Chart') + '">';
    y.ticks.forEach(function (t) { svg += '<line class="ax" x1="' + L + '" x2="' + (W - R) + '" y1="' + y(t) + '" y2="' + y(t) + '"/><text class="ax-t" x="' + (L - 8) + '" y="' + (y(t) + 4) + '" text-anchor="end">' + esc(GL.money(t, { short: true })) + '</text>'; });
    var xs = [], every = Math.ceil(n / Math.max(2, Math.floor(pw / 46)));
    for (i = 0; i < n; i++) {
      var cx = L + slot * i + slot / 2; xs.push(cx);
      if (o.stacked) {
        var base = 0;
        o.series.forEach(function (s, j) {
          var v = s.values[i]; if (v <= 0) return;
          var y1 = y(base + v), y0 = y(base), top = j === k - 1 || o.series.slice(j + 1).every(function (z) { return z.values[i] <= 0; });
          svg += barPath(cx - bw / 2, y1 + (base > 0 ? 0 : 0), bw, Math.max(0, y0 - y1 - (base > 0 ? gap : 0)), s.color, top);
          base += v;
        });
      } else {
        o.series.forEach(function (s, j) {
          var v = s.values[i], x = cx - (bw * k + gap * (k - 1)) / 2 + j * (bw + gap);
          var y1 = y(Math.max(0, v)), y0 = y(Math.min(0, v));
          svg += barPath(x, y1, bw, Math.max(0, y0 - y1), s.color, v >= 0);
        });
      }
      if (i % every === 0 || (i === n - 1 && (n - 1) % every >= every * .6)) svg += '<text class="ax-t" x="' + cx + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(o.labels[i]) + '</text>';
    }
    if (min < 0) svg += '<line class="zero" x1="' + L + '" x2="' + (W - R) + '" y1="' + y(0) + '" y2="' + y(0) + '"/>';
    svg += '<line data-guide x1="0" x2="0" y1="' + T + '" y2="' + (T + ph) + '" stroke="var(--c-faint)" stroke-width="1" style="opacity:0"/></svg>';
    box.innerHTML = '<div class="gl-chart">' + svg + '</div><div class="gl-key">' + o.series.map(function (s) {
      return '<span><i style="background:' + s.color + '"></i>' + esc(s.label) + '</span>'; }).join('') + '</div>';
    wireTip(box.querySelector('.gl-chart'), W, xs, function (i) {
      return '<div class="muted">' + esc(o.tipLabels ? o.tipLabels[i] : o.labels[i]) + '</div>' + o.series.map(function (s) {
        return '<div><i style="display:inline-block;width:9px;height:9px;border-radius:3px;background:' + s.color + ';margin-right:6px"></i>' + esc(s.label) + ': <b>' + esc(GL.money(s.values[i])) + '</b></div>'; }).join('') +
        (o.extraTip ? o.extraTip(i) : '');
    });
  };
  function barPath(x, y, w, h, color, roundTop) {
    if (h <= 0.5) return '';
    var r = Math.min(4, w / 2, h);
    if (!roundTop) return '<path d="M' + x + ' ' + y + 'h' + w + 'v' + (h - r) + 'q0 ' + r + ' -' + r + ' ' + r + 'h-' + (w - 2 * r) + 'q-' + r + ' 0 -' + r + ' -' + r + 'z" fill="' + color + '"/>';
    return '<path d="M' + x + ' ' + (y + h) + 'v-' + (h - r) + 'q0 -' + r + ' ' + r + ' -' + r + 'h' + (w - 2 * r) + 'q' + r + ' 0 ' + r + ' ' + r + 'v' + (h - r) + 'z" fill="' + color + '"/>';
  }
  GL.onResize = function (fn) {
    var t = null, w = innerWidth;
    function h() { if (Math.abs(innerWidth - w) < 8) return; w = innerWidth; clearTimeout(t); t = setTimeout(fn, 150); }
    addEventListener('resize', h);
    return function () { removeEventListener('resize', h); };
  };

  /* ------------------------------------------------------------------ shared bits */
  GL.statusChip = function (s) { return '<span class="gl-status gl-st-' + esc(s) + '">' + esc(GL.STATUS_LABEL[s] || s) + '</span>'; };
  GL.taskCard = function (k, showWhere) {
    var when = k.status === 'done' ? 'Done ' + UI.ago(k.done_at) + (k.days_open != null ? ' · took ' + GL.days(k.days_open) : '')
      : k.status === 'scheduled' && k.scheduled_for ? 'Scheduled for ' + UI.fmtDate(k.scheduled_for, { weekday: 'short', day: 'numeric', month: 'short' })
      : 'Asked ' + UI.ago(k.requested_at);
    return '<button type="button" class="gl-task" data-task-id="' + esc(k.id) + '"><span class="ui-row">' + GL.statusChip(k.status) +
      (k.priority === 'urgent' ? '<span class="small gl-prio-urgent">Urgent</span>' : '') + '<span class="small faint">#' + k.number + '</span></span>' +
      '<span class="t">' + esc(k.title) + '</span><span class="s">' + (showWhere ? esc(k.where) + ' · ' : '') + esc(when) + '</span></button>';
  };
  GL.days = function (d) { return d < 1 ? Math.max(1, Math.round(d * 24)) + ' h' : (Math.round(d * 10) / 10) + (d < 1.5 ? ' day' : ' days'); };
  GL.hours = function (h) { return h < 1 ? Math.max(1, Math.round(h * 60)) + ' minutes' : h < 48 ? Math.round(h) + (Math.round(h) === 1 ? ' hour' : ' hours') : Math.round(h / 24) + ' days'; };
  GL.badges = function (st) {
    var out = [];
    if (st.reply_hours != null) out.push(['clock', 'Usually replies in ' + GL.hours(st.reply_hours)]);
    if (st.fix_days != null) out.push(['wrench', 'Fixes things in ' + GL.days(st.fix_days)]);
    if (st.requests && st.answered === st.requests) out.push(['heart', 'Answered every request']);
    return out;
  };
  GL.copy = function (text) {
    var done = function () { UI.toast('Link copied', 'ok'); };
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).then(done, function () { UI.toast('Select the link and copy it.'); });
    UI.toast('Select the link and copy it.');
  };
  GL.tenantLink = function (token) { return location.href.split('#')[0].split('?')[0] + '#t/' + token; };

  /* ------------------------------------------------------------------ the record thread */
  var EV_ICON = { opened: 'seal', requested: 'wrench', acknowledged: 'check', scheduled: 'calendar', in_progress: 'wrench', done: 'check', declined: 'x',
    confirmed: 'heart', reopened: 'refresh', rent_paid: 'receipt', rent_removed: 'receipt', rent_changed: 'coins', ended: 'key', reopened_tenancy: 'key', link_reset: 'link' };
  GL.thread = function (entries, side) {
    var out = '', lastDay = '';
    entries.forEach(function (e) {
      var day = new Date(e.created).toDateString();
      if (day !== lastDay) { out += '<div class="gl-day">' + esc(UI.fmtDate(e.created, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })) + '</div>'; lastDay = day; }
      var time = new Date(e.created).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
      if (e.kind === 'message') {
        var mine = e.author_kind === side;
        out += '<div class="gl-msg ' + (mine ? 'mine' : 'theirs') + '" data-seq="' + e.seq + '"><div class="bub">' + esc(e.body) + '</div>' +
          '<div class="meta"><span>' + esc(mine ? 'You' : e.author_name) + ' · ' + esc(time) + '</span><span class="seal" title="Entry #' + e.seq + ', sealed with fingerprint ' + esc(e.hash) + '">#' + e.seq + ' · ' + esc(e.hash.slice(0, 6)) + '</span></div></div>';
      } else {
        var lines = e.body.split('\n'), who = e.author_kind === 'system' ? '' : '<b>' + esc(e.author_kind === side ? 'You' : e.author_name) + '</b> ';
        out += '<div class="gl-ev" data-seq="' + e.seq + '"' + (e.task_id ? ' data-task="' + esc(e.task_id) + '"' : '') + '>' + UI.icon(EV_ICON[e.event] || 'info') +
          '<div><p>' + who + esc(lines[0]) + (lines.length > 1 ? '<br><span style="color:var(--c-ink)">' + esc(lines.slice(1).join('\n')) + '</span>' : '') + '</p>' +
          '<div class="meta">' + esc(time) + ' · #' + e.seq + ' · ' + esc(e.hash.slice(0, 6)) + '</div></div></div>';
      }
    });
    return '<div class="gl-thread">' + out + '</div>';
  };
  GL.sealBox = function (seal) {
    if (!seal.intact) return '<div class="gl-seal broken">' + UI.icon('info') + '<span><b>The seal is broken at entry #' + seal.broken_at + '.</b> Something in the record changed after it was written. Please tell us through Submit feedback.</span></div>';
    return '<div class="gl-seal">' + UI.icon('seal') + '<span><b>Sealed record:</b> ' + UI.plural(seal.count, 'entry', 'entries') + ', nothing edited or deleted. Fingerprint <code>' + esc(seal.head) + '</code></span>' +
      '<button class="ui-btn sm ghost" data-verify style="margin-left:auto">' + UI.icon('refresh') + 'Check again</button></div>';
  };
  GL.recordText = function (o) {
    var L = [];
    L.push('GOOD LANDLORD: TENANCY RECORD');
    L.push(o.property.name + (o.unit ? ' · ' + o.unit : '') + (o.property.address ? ' · ' + o.property.address : ''));
    L.push('Tenant: ' + o.tenant + '    Landlord: ' + o.landlord);
    L.push('Downloaded ' + new Date().toString());
    L.push('Seal: ' + (o.seal.intact ? 'intact, ' + o.seal.count + ' entries, fingerprint ' + o.seal.head : 'BROKEN at entry #' + o.seal.broken_at));
    L.push('Each entry is sealed with a SHA-256 hash of its content and of the entry before it: changing or removing one breaks the chain.');
    L.push('');
    o.entries.forEach(function (e) {
      L.push('#' + e.seq + '  ' + new Date(e.created).toISOString().replace('T', ' ').slice(0, 19) + ' UTC  ' + (e.author_kind === 'system' ? 'Good Landlord' : e.author_name + ' (' + e.author_kind + ')') + (e.kind === 'event' ? '  [' + (e.event || 'event') + ']' : ''));
      e.body.split('\n').forEach(function (l) { L.push('    ' + l); });
      L.push('    seal ' + e.hash);
      L.push('');
    });
    if (o.tasks && o.tasks.length) {
      L.push('REQUESTS');
      o.tasks.slice().reverse().forEach(function (k) {
        L.push('#' + k.number + ' ' + k.title + '  [' + (GL.STATUS_LABEL[k.status] || k.status) + ']');
        L.push('    asked ' + (k.requested_at || '').slice(0, 10) + ' by ' + k.requested_name + (k.acknowledged_at ? ' · seen ' + k.acknowledged_at.slice(0, 10) : '') +
          (k.scheduled_for ? ' · scheduled ' + k.scheduled_for : '') + (k.done_at ? ' · done ' + k.done_at.slice(0, 10) : '') + (k.confirmed_at ? ' · confirmed ' + k.confirmed_at.slice(0, 10) : ''));
      });
    }
    return L.join('\n');
  };
  GL.download = function (name, text, type) {
    var blob = new Blob([text], { type: type || 'text/plain;charset=utf-8' }), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };

  /* ------------------------------------------------------------------ forms (modals) */
  function opt(list, val) { return list.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === String(val) ? ' selected' : '') + '>' + esc(o[1]) + '</option>'; }).join(''); }
  function field(label, html, cls, hint) { return '<label class="ui-field ' + (cls || '') + '"><span>' + label + '</span>' + html + (hint ? '<p class="ui-hint">' + hint + '</p>' : '') + '</label>'; }
  function num(name, val, attrs) { return '<input type="text" inputmode="decimal" name="' + name + '" value="' + esc(val == null || val === '' ? '' : val) + '" ' + (attrs || '') + '>'; }
  GL.opt = opt;
  function submitter(m, fn, payload) {
    var form = m.el.querySelector('form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(form), err = form.querySelector('.ui-error');
      if (err) err.remove();
      UI.busy(form.querySelector('[type=submit]'), UI.api(fn, payload ? payload(v) : v)).then(function (r) { m.close(); if (m.done) m.done(r); }, function (e2) {
        var box = document.createElement('div'); box.className = 'ui-error full'; box.textContent = e2.message; form.querySelector('.gl-form-grid').appendChild(box);
      });
    });
  }
  GL.forms = {};
  GL.forms.property = function (p, done) {
    p = p || { kind: 'house', units: 1, appreciation: 3, selling_pct: 5, door: 'red' };
    var m = UI.modal('<h2>' + (p.id ? 'Edit ' + esc(p.name) : 'Add a property') + '</h2><form><div class="gl-form-grid">' +
      field('Name', '<input type="text" name="name" maxlength="80" required value="' + esc(p.name || '') + '" placeholder="Maple Street Duplex">', 'full') +
      field('Address <em>(optional)</em>', '<input type="text" name="address" maxlength="160" value="' + esc(p.address || '') + '">', 'full') +
      field('Type', '<select name="kind">' + opt(GL.KINDS, p.kind) + '</select>') +
      field('Units', num('units', p.units || 1)) +
      field('Purchase price', num('purchase_price', p.purchase_price, 'placeholder="500000"')) +
      field('Bought on', '<input type="date" name="purchase_date" value="' + esc(p.purchase_date || '') + '">') +
      field('Down payment', num('down_payment', p.down_payment), '', 'Cash you put in at purchase.') +
      field('Closing costs', num('closing_costs', p.closing_costs), '', 'Transfer tax, notary or lawyer, inspection.') +
      field('Improvements since', num('improvements', p.improvements), '', 'Renovations not already in your ledger as capital.') +
      field('What it\'s worth today', num('current_value', p.current_value), '', 'Your best estimate. Tune it on the Deal check page.') +
      field('Expected growth per year', num('appreciation', p.appreciation, 'placeholder="3"'), '', 'In %, used for long-term projections.') +
      field('Selling costs', num('selling_pct', p.selling_pct, 'placeholder="5"'), '', 'In % of the price: agent, legal, moving.') +
      '<div class="ui-field full"><span>Door colour</span><div class="gl-doors">' + Object.keys(GL.DOORS).map(function (k) {
        return '<label title="' + k + '"><input type="radio" name="door" value="' + k + '"' + ((p.door || 'red') === k ? ' checked' : '') + '><span style="background:' + GL.DOORS[k] + '"></span></label>'; }).join('') + '</div></div>' +
      field('Notes <em>(only you see these)</em>', '<textarea name="notes" maxlength="2000">' + esc(p.notes || '') + '</textarea>', 'full') +
      '</div><div class="ui-row end" style="margin-top:18px"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('check') + (p.id ? 'Save' : 'Add property') + '</button></div></form>', { wide: true });
    m.done = done;
    submitter(m, 'save_property', function (v) { v.id = p.id || null; return v; });
    return m;
  };
  GL.forms.mortgage = function (mo, propId, done) {
    mo = mo || { frequency: 'monthly', compounding: GL.data.prefs.compounding || 'semiannual', amort_years: 25, term_years: 5 };
    var prop = GL.prop(propId || mo.property_id) || {};
    if (!mo.id && !mo.amount && prop.purchase_price) mo.amount = Math.max(0, prop.purchase_price - (prop.down_payment || 0));
    var m = UI.modal('<h2>' + (mo.id ? 'Edit mortgage' : 'Add a mortgage') + '</h2><p class="muted">' + esc(prop.name || '') + '. Payments are worked out from these numbers, so you don\'t add them to the ledger.</p><form><div class="gl-form-grid">' +
      field('Lender <em>(optional)</em>', '<input type="text" name="lender" maxlength="80" value="' + esc(mo.lender || '') + '">', 'full') +
      field('Amount borrowed', num('amount', mo.amount, 'required')) +
      field('Interest rate (%)', num('rate', mo.rate, 'required placeholder="4.79"')) +
      field('Started on', '<input type="date" name="start_date" required value="' + esc(mo.start_date || prop.purchase_date || '') + '">') +
      field('Payments', '<select name="frequency">' + opt(GL.FREQ, mo.frequency) + '</select>') +
      field('Amortisation (years)', num('amort_years', mo.amort_years), '', 'Years to pay it all off.') +
      field('Term (years)', num('term_years', mo.term_years), '', 'Until the rate is renewed.') +
      field('Interest compounding', '<select name="compounding">' + opt([['semiannual', 'Twice a year (Canadian fixed rate)'], ['monthly', 'Monthly (US, variable rates)']], mo.compounding) + '</select>', 'full') +
      '</div><div class="ui-row end" style="margin-top:18px">' + (mo.id ? '<button type="button" class="ui-btn danger" data-del-mortgage>' + UI.icon('trash') + 'Delete</button><span class="ui-spacer"></span>' : '') +
      '<button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('check') + 'Save</button></div></form>', { wide: true });
    m.done = done;
    submitter(m, 'save_mortgage', function (v) { v.id = mo.id || null; v.property_id = propId || mo.property_id; return v; });
    var del = m.el.querySelector('[data-del-mortgage]');
    if (del) del.onclick = function () { UI.confirm({ title: 'Delete this mortgage?', ok: 'Delete', danger: true }).then(function (y) { if (y) UI.api('delete_mortgage', mo.id).then(function () { m.close(); done && done(); }); }); };
    return m;
  };
  GL.forms.tenancy = function (t, propId, done) {
    t = t || { due_day: 1, start_date: GL.iso(new Date()) };
    var props = GL.activeProps();
    var m = UI.modal('<h2>' + (t.id ? 'Edit tenancy' : 'Add a tenant') + '</h2>' + (t.id ? '' : '<p class="muted">This opens a permanent record for you and your tenant, with a private link you can send them.</p>') +
      '<form><div class="gl-form-grid">' +
      (t.id ? '' : field('Property', '<select name="property_id">' + opt(props.map(function (p) { return [p.id, p.name]; }), propId) + '</select>')) +
      field('Unit <em>(optional)</em>', '<input type="text" name="unit" maxlength="40" value="' + esc(t.unit || '') + '" placeholder="Upstairs, #2…">', t.id ? 'full' : '') +
      field('Tenant name(s)', '<input type="text" name="tenant_name" maxlength="80" required value="' + esc(t.tenant_name || '') + '">', 'full') +
      field('Tenant email <em>(optional, only you see it)</em>', '<input type="email" name="tenant_email" maxlength="120" value="' + esc(t.tenant_email || '') + '">', 'full') +
      field('Monthly rent', num('rent', t.rent, 'required')) +
      field('Due on day', num('due_day', t.due_day), '', '1 to 28') +
      field('Lease starts', '<input type="date" name="start_date" value="' + esc(t.start_date || '') + '">') +
      field('Lease ends <em>(optional)</em>', '<input type="date" name="end_date" value="' + esc(t.end_date || '') + '">') +
      field('Deposit held <em>(optional)</em>', num('deposit', t.deposit), 'full') +
      '</div><div class="ui-row end" style="margin-top:18px"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('check') + (t.id ? 'Save' : 'Open the record') + '</button></div></form>', { wide: true });
    m.done = done;
    submitter(m, 'save_tenancy', function (v) { v.id = t.id || null; if (t.id) v.property_id = t.property_id; return v; });
    return m;
  };
  GL.forms.entry = function (e, defaults, done) {
    var isNew = !e; e = e || Object.assign({ kind: 'expense', category: 'repairs', date: GL.iso(new Date()) }, defaults || {});
    var props = GL.data.properties.filter(function (p) { return !p.archived || p.id === e.property_id; });
    var cats = GL.data.categories;
    function catOpts(kind) { return cats.filter(function (c) { return c.kind === kind; }).map(function (c) { return [c.id, c.label + (c.claim === 'capital' ? ' · capital' : c.claim === 'no' ? ' · not claimable' : '')]; }); }
    var m = UI.modal('<h2>' + (isNew ? 'Add to the ledger' : 'Edit entry') + '</h2><form><div class="gl-form-grid">' +
      '<div class="ui-field full"><div class="ui-seg" data-kind-seg><button type="button" data-k="expense" class="' + (e.kind === 'expense' ? 'on' : '') + '">Money out</button><button type="button" data-k="income" class="' + (e.kind === 'income' ? 'on' : '') + '">Money in</button></div></div>' +
      field('Property', '<select name="property_id">' + opt(props.map(function (p) { return [p.id, p.name]; }), e.property_id) + '</select>') +
      field('Category', '<select name="category" data-cat>' + opt(catOpts(e.kind), e.category) + '</select>', '', '<span data-cat-hint></span>') +
      field('Amount', num('amount', e.amount, 'required placeholder="0.00"')) +
      field('Date', '<input type="date" name="date" value="' + esc(e.date || '') + '">') +
      field('What for <em>(optional)</em>', '<input type="text" name="memo" maxlength="200" value="' + esc(e.memo || '') + '">', 'full') +
      '</div><div class="ui-row end" style="margin-top:18px">' + (isNew ? '' : '<button type="button" class="ui-btn danger" data-del-entry>' + UI.icon('trash') + 'Delete</button><span class="ui-spacer"></span>') +
      '<button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('check') + 'Save</button></div></form>', { wide: true });
    var sel = m.el.querySelector('[data-cat]'), hint = m.el.querySelector('[data-cat-hint]');
    function showHint() { var c = GL.cat[sel.value]; hint.textContent = c ? (c.hint || (c.claim === 'yes' ? 'Claimable this year.' : '')) : ''; }
    showHint(); sel.addEventListener('change', showHint);
    m.el.querySelector('[data-kind-seg]').addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-k]'); if (!b) return;
      m.el.querySelectorAll('[data-k]').forEach(function (x) { x.classList.toggle('on', x === b); });
      sel.innerHTML = opt(catOpts(b.getAttribute('data-k')), b.getAttribute('data-k') === 'income' ? 'rent' : 'repairs'); showHint();
    });
    m.done = done;
    var form = m.el.querySelector('form');
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var v = UI.formData(form), old = form.querySelector('.ui-error'); if (old) old.remove();
      if (e.tenancy_id) v.tenancy_id = e.tenancy_id;
      if (e.rent_month) v.rent_month = e.rent_month;
      var call = isNew ? UI.api('add_entry', v) : UI.api('update_entry', e.id, v);
      UI.busy(form.querySelector('[type=submit]'), call).then(function (r) { m.close(); done && done(r); }, function (er) {
        var box = document.createElement('div'); box.className = 'ui-error full'; box.textContent = er.message; form.querySelector('.gl-form-grid').appendChild(box); });
    });
    var del = m.el.querySelector('[data-del-entry]');
    if (del) del.onclick = function () { UI.confirm({ title: 'Delete this entry?', text: e.category === 'rent' && e.tenancy_id ? 'The tenancy record will note that this rent record was removed.' : '', ok: 'Delete', danger: true }).then(function (y) { if (y) UI.api('delete_entry', e.id).then(function () { m.close(); done && done(); }); }); };
    return m;
  };
  /* The task modal: timeline of dates + moves (landlord) or confirm (tenant). */
  GL.taskModal = function (k, o) {
    o = o || {};
    var order = ['requested', 'acknowledged', 'scheduled', 'in_progress', 'done'], idx = order.indexOf(k.status);
    var steps = '<div class="gl-steps">' + order.map(function (s, i) { return '<span class="' + (idx >= i ? 'on' : '') + '">' + esc(GL.STATUS_LABEL[s]) + '</span>'; }).join('') + '</div>';
    var dt = function (iso) { return iso ? esc(UI.fmtDateTime(iso)) : '<span class="faint">·</span>'; };
    var times = '<dl class="gl-times"><dt>Asked</dt><dd>' + dt(k.requested_at) + ' <span class="muted small">by ' + esc(k.requested_name) + '</span></dd>' +
      '<dt>Seen</dt><dd>' + dt(k.acknowledged_at) + '</dd>' +
      '<dt>Scheduled for</dt><dd>' + (k.scheduled_for ? esc(UI.fmtDate(k.scheduled_for, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })) : '<span class="faint">·</span>') + '</dd>' +
      '<dt>Work started</dt><dd>' + dt(k.started_at) + '</dd><dt>Done</dt><dd>' + dt(k.done_at) + (k.done_at && k.days_open != null ? ' <span class="muted small">(' + GL.days(k.days_open) + ' after asking)</span>' : '') + '</dd>' +
      '<dt>Tenant confirmed</dt><dd>' + dt(k.confirmed_at) + '</dd>' + (o.landlord && k.cost ? '<dt>Cost</dt><dd>' + esc(GL.money(k.cost, { cents: true })) + '</dd>' : '') + '</dl>';
    var actions = '';
    if (o.landlord) {
      actions = '<form data-move style="margin-top:18px" class="ui-stack"><h3 style="margin:0">Move it along</h3><div class="gl-moves">' +
        [['acknowledged', 'Seen it'], ['scheduled', 'Schedule'], ['in_progress', 'Working on it'], ['done', 'Done'], ['declined', 'Decline']].filter(function (s) { return s[0] !== k.status || s[0] === 'scheduled'; }).map(function (s) {
          return '<button type="button" class="ui-btn sm' + (s[0] === 'done' ? ' primary' : s[0] === 'declined' ? ' danger' : '') + '" data-to="' + s[0] + '">' + esc(s[1]) + '</button>'; }).join('') +
        (k.status === 'done' || k.status === 'declined' ? '<button type="button" class="ui-btn sm ghost" data-to="requested">Reopen</button>' : '') + '</div>' +
        '<div data-extra hidden class="gl-form-grid"><label class="ui-field" data-when hidden><span>Scheduled for</span><input type="date" name="scheduled_for" value="' + esc(k.scheduled_for || GL.iso(new Date(Date.now() + 2 * 864e5))) + '"></label>' +
        '<label class="ui-field" data-cost hidden><span>What it cost <em>(optional)</em></span><input type="text" inputmode="decimal" name="cost" value="' + esc(k.cost || '') + '"><p class="ui-hint">Goes into the ledger as a claimable repair.</p></label>' +
        '<label class="ui-field full"><span>Note for the record <em data-note-req>(optional)</em></span><textarea name="note" maxlength="1000" placeholder="Who is coming, what was done…"></textarea></label>' +
        '<div class="full ui-row end"><button type="button" class="ui-btn ghost" data-cancel-move>Cancel</button><button class="ui-btn primary" type="submit" data-go-move>Save</button></div></div>' +
        '<p class="ui-hint">Every move is written into the record with its date and can\'t be erased.</p></form>';
    } else if (o.tenant && k.status === 'done' && !k.confirmed_at) {
      actions = '<div class="ui-card flat" style="margin-top:18px;background:var(--c-good-soft)"><h3>Is it fixed?</h3><p class="muted small">Your answer goes into the record.</p>' +
        '<textarea data-tnote maxlength="1000" placeholder="Anything to add (optional)"></textarea><div class="ui-row" style="margin-top:10px"><button class="ui-btn primary" data-confirm="1">' + UI.icon('check') + 'Yes, it\'s fixed</button>' +
        '<button class="ui-btn" data-confirm="0">Not yet</button></div></div>';
    }
    var m = UI.modal('<div class="ui-row">' + GL.statusChip(k.status) + (k.priority === 'urgent' ? '<span class="small gl-prio-urgent">Urgent</span>' : '') + '<span class="small muted">#' + k.number + ' · ' + esc(GL.TASK_CAT_LABEL[k.category] || '') + '</span></div>' +
      '<h2 style="margin-top:10px">' + esc(k.title) + '</h2>' + (k.where ? '<p class="muted small">' + esc(k.where) + '</p>' : '') + (k.details ? '<p style="white-space:pre-wrap">' + esc(k.details) + '</p>' : '') +
      steps + times + actions, { wide: true });
    var form = m.el.querySelector('[data-move]'), to = null;
    if (form) {
      var extra = form.querySelector('[data-extra]');
      form.addEventListener('click', function (e) {
        var b = e.target.closest('[data-to]');
        if (b) {
          to = b.getAttribute('data-to');
          form.querySelectorAll('[data-to]').forEach(function (x) { x.classList.toggle('on', x === b); x.style.outline = x === b ? '2px solid var(--c-ink)' : ''; });
          extra.hidden = false; extra.querySelector('[data-when]').hidden = to !== 'scheduled'; extra.querySelector('[data-cost]').hidden = to !== 'done';
          form.querySelector('[data-note-req]').textContent = to === 'declined' ? '(required: why?)' : '(optional)';
          form.querySelector('[data-go-move]').textContent = 'Move to ' + GL.STATUS_LABEL[to];
          return;
        }
        if (e.target.closest('[data-cancel-move]')) { extra.hidden = true; to = null; }
      });
      form.addEventListener('submit', function (e) {
        e.preventDefault(); if (!to) return;
        var v = UI.formData(form);
        UI.busy(form.querySelector('[data-go-move]'), UI.api('set_task_status', k.id, to, to === 'scheduled' ? v.scheduled_for : null, v.note, to === 'done' ? v.cost : null)).then(function (r) {
          m.close(); UI.toast('Moved to ' + GL.STATUS_LABEL[to], 'ok'); o.done && o.done(r);
        });
      });
    }
    m.el.querySelectorAll('[data-confirm]').forEach(function (b) {
      b.onclick = function () {
        var fixed = b.getAttribute('data-confirm') === '1';
        UI.busy(b, UI.api('tenant_confirm', o.token, k.id, fixed, o.name || null, m.el.querySelector('[data-tnote]').value)).then(function () {
          m.close(); UI.toast(fixed ? 'Thanks! Noted in the record.' : 'Reopened. Your landlord will see it.', 'ok'); o.done && o.done();
        });
      };
    });
    return m;
  };
  GL.newTaskForm = function (o) {
    var m = UI.modal('<h2>' + esc(o.title || 'Ask for a repair') + '</h2><p class="muted">' + esc(o.lead || 'It goes into the record with today\'s date.') + '</p><form><div class="gl-form-grid">' +
      field('What needs doing?', '<input type="text" name="title" maxlength="120" required placeholder="The kitchen tap drips">', 'full') +
      field('Details <em>(optional)</em>', '<textarea name="details" maxlength="3000" placeholder="Where, since when, what you tried"></textarea>', 'full') +
      field('Type', '<select name="category">' + opt(GL.TASK_CATS, 'other') + '</select>') +
      field('How urgent?', '<select name="priority">' + opt([['low', 'Whenever is convenient'], ['normal', 'Soon'], ['urgent', 'Urgent (safety, no heat, water leak)']], 'normal') + '</select>') +
      '</div><div class="ui-row end" style="margin-top:18px"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('send') + esc(o.ok || 'Send request') + '</button></div></form>', { wide: true });
    var form = m.el.querySelector('form');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(form);
      UI.busy(form.querySelector('[type=submit]'), o.send(v)).then(function (r) { m.close(); o.done && o.done(r); });
    });
    return m;
  };
})();

/* ===== admin.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['overview', 'Overview', 'grid'], ['feedback', 'Feedback', 'inbox'], ['users', 'Users', 'users'], ['demo', 'Demo data', 'database']];

  UI.page('admin', { title: 'Admin', auth: 'admin' }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'overview';
    var fbFilter = 'new';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Admin</h1><p class="muted">Only admins see this page.</p></div></div>' +
      '<nav class="ui-tabs">' + TABS.map(function (t) {
        return '<a href="#admin/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + '</a>';
      }).join('') + '</nav><div data-body><div class="ui-skel"></div></div></div>';
    var body = view.querySelector('[data-body]');

    function overview() {
      return UI.api('admin_overview').then(function (d) {
        var stat = function (n, label, go) { return '<a class="ui-card ui-stat" href="#admin/' + go + '" style="text-decoration:none;color:inherit"><b>' + n + '</b><span>' + label + '</span></a>'; };
        body.innerHTML = '<div class="ad-stats">' + stat(d.users, 'people signed up', 'users') + stat(d.admins, UI.plural(d.admins, 'admin').replace(/^\d+ /, ''), 'users') +
          stat(d.feedback_new, 'new feedback', 'feedback') + stat(d.landlords, 'landlords with a property', 'overview') +
          stat(d.properties, 'properties', 'overview') + stat(d.tenancies, 'tenancy records', 'overview') + stat(d.messages, 'record entries', 'overview') + '</div>' +
          '<p class="muted small" style="margin-top:18px">Tenancy records are private between each landlord and tenant, so admins only see counts. Demo rows are not counted.</p>' +
          '<p class="muted small" style="margin-top:18px">Demo data is <b>' + esc(d.demo.state) + '</b> (' + d.demo.counts.users + ' demo people). Manage it in the Demo data tab.</p>';
      });
    }

    function feedback() {
      return UI.api('list_feedback', null).then(function (d) {
        var items = d.items.filter(function (i) { return fbFilter === 'all' || i.status === fbFilter; });
        body.innerHTML = '<div class="ui-row" style="margin-bottom:16px"><div class="ui-seg">' + [['new', 'New'], ['read', 'Read'], ['done', 'Done'], ['all', 'All']].map(function (f) {
          var n = f[0] === 'all' ? d.items.length : d.counts[f[0]];
          return '<button data-filter="' + f[0] + '" class="' + (fbFilter === f[0] ? 'on' : '') + '">' + f[1] + ' (' + n + ')</button>';
        }).join('') + '</div></div>' +
          (items.length ? '<div class="ad-fb">' + items.map(function (i) {
            var c = i.context || {};
            return '<div class="ui-item" data-id="' + esc(i.id) + '"><div class="meta"><span class="ui-badge ' + (i.kind === 'bug' ? 'bad' : i.kind === 'idea' ? 'brand' : '') + '">' + esc(i.kind_label) + '</span>' +
              '<b>' + esc(i.name) + '</b>' + (i.email ? '<a href="mailto:' + esc(i.email) + '">' + esc(i.email) + '</a>' : '') + '<span>' + esc(UI.fmtDateTime(i.created)) + '</span></div>' +
              '<p class="msg">' + esc(i.message) + '</p>' +
              '<div class="ctx">' + esc([c.page, c.screen, c.theme, c.browser].filter(Boolean).join(' · ')) + '</div>' +
              '<textarea data-note placeholder="Private note (only admins see it)">' + esc(i.note) + '</textarea>' +
              '<div class="ui-row" style="margin-top:10px">' + ['new', 'read', 'done'].map(function (s) {
                return '<button class="ui-btn sm' + (i.status === s ? ' primary' : '') + '" data-status="' + s + '">' + s[0].toUpperCase() + s.slice(1) + '</button>';
              }).join('') + '<span class="ui-spacer"></span><button class="ui-btn sm danger" data-del-fb>' + UI.icon('trash') + 'Delete</button></div></div>';
          }).join('') + '</div>'
            : '<div class="ui-empty">' + UI.icon('inbox') + '<h3>No ' + (fbFilter === 'all' ? '' : fbFilter + ' ') + 'messages</h3><p>New feedback goes to Prepsto (prepsto.com). Older messages and requests from the app show up here.</p></div>');
      });
    }

    function users(query) {
      return UI.api('list_users', query || null).then(function (d) {
        body.innerHTML = '<form class="ui-row" data-search style="margin-bottom:14px"><input type="search" name="q" placeholder="Search by name or email" value="' + esc(query || '') + '" style="max-width:360px">' +
          '<button class="ui-btn" type="submit">' + UI.icon('search') + 'Search</button><span class="muted small">' + UI.plural(d.total, 'person', 'people') + '</span></form>' +
          '<table class="ad-users"><thead><tr><th>Name</th><th>Email</th><th>Joined</th><th>Admin</th><th>Active</th></tr></thead><tbody>' +
          d.users.map(function (u) {
            return '<tr data-id="' + esc(u.id) + '"><td><b>' + esc(u.name) + '</b></td><td class="email">' + esc(u.email) + '</td><td class="joined muted">' + esc(UI.fmtDate(u.joined)) + '</td>' +
              '<td><label class="ui-check"><input type="checkbox" data-admin' + (u.is_admin ? ' checked' : '') + '> Admin</label></td>' +
              '<td><label class="ui-check"><input type="checkbox" data-enabled' + (u.enabled ? ' checked' : '') + '> Active</label></td></tr>';
          }).join('') + '</tbody></table>';
      });
    }

    function demo() {
      return UI.api('admin_overview').then(function (d) {
        var c = d.demo.counts;
        body.innerHTML = '<div class="ui-card ui-narrow" style="margin:0"><h3>Demo data</h3>' +
          '<p class="muted">Example people and content, so the app never looks empty for the first visitors. Demo rows are flagged, so removing them never touches real data. Once removed, it stays removed until you load it again.</p>' +
          '<p>Status: <b>' + esc(d.demo.state) + '</b> · ' + Object.keys(c).map(function (k) { return c[k] + ' ' + esc(k); }).join(', ') + '</p>' +
          '<div class="ui-row"><button class="ui-btn primary" data-demo="load">' + UI.icon('refresh') + (d.demo.state === 'loaded' ? 'Reload demo data' : 'Load demo data') + '</button>' +
          '<button class="ui-btn danger" data-demo="remove">' + UI.icon('trash') + 'Remove demo data</button></div></div>';
      });
    }

    var DRAW = { overview: overview, feedback: feedback, users: users, demo: demo };

    view.addEventListener('click', function (e) {
      var f = e.target.closest('[data-filter]');
      if (f) { fbFilter = f.getAttribute('data-filter'); feedback(); return; }
      var st = e.target.closest('[data-status]');
      if (st) {
        var card = st.closest('[data-id]');
        UI.api('set_feedback_status', card.getAttribute('data-id'), st.getAttribute('data-status'), card.querySelector('[data-note]').value).then(function () { UI.toast('Saved', 'ok'); feedback(); });
        return;
      }
      var del = e.target.closest('[data-del-fb]');
      if (del) {
        UI.confirm({ title: 'Delete this message?', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_feedback', del.closest('[data-id]').getAttribute('data-id')).then(feedback);
        });
        return;
      }
      var dm = e.target.closest('[data-demo]');
      if (dm) {
        var load = dm.getAttribute('data-demo') === 'load';
        UI.confirm({ title: load ? 'Load the demo data?' : 'Remove the demo data?', text: load ? 'Demo people and content are added (any old demo rows are replaced).' : 'Every demo row is deleted. Real data stays.', ok: load ? 'Load' : 'Remove', danger: !load })
          .then(function (yes) { if (yes) UI.busy(dm, UI.api(load ? 'demo_load' : 'demo_remove')).then(function () { UI.toast('Done', 'ok'); demo(); }); });
      }
    });
    view.addEventListener('change', function (e) {
      var row = e.target.closest('tr[data-id]');
      if (!row) return;
      var id = row.getAttribute('data-id'), box = e.target;
      var fn = box.hasAttribute('data-admin') ? 'set_admin' : box.hasAttribute('data-enabled') ? 'set_enabled' : null;
      if (fn) UI.api(fn, id, box.checked).then(function () { UI.toast('Saved', 'ok'); }, function (err) { box.checked = !box.checked; UI.toast(err.message, 'error'); });
    });
    view.addEventListener('submit', function (e) {
      if (e.target.matches('[data-search]')) { e.preventDefault(); users(UI.formData(e.target).q); }
    });
    return DRAW[tab]();
  });
})();

/* ===== auth.html ===== */
(function () {
  var esc = UI.esc;
  var GOOGLE_G = '<svg viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>' +
    '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>' +
    '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>' +
    '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>';
  function pw(name, auto) {
    return '<div class="au-pw"><input type="password" name="' + name + '" autocomplete="' + auto + '" required minlength="8">' +
      '<button type="button" data-show>Show</button></div>';
  }
  UI.page('auth', { title: 'Sign in', auth: 'guest' }, function (view, ctx) {
    var mode = ['signup', 'reset'].indexOf(ctx.args[0]) >= 0 ? ctx.args[0] : 'login';
    function draw(msg, isErr) {
      var heading = { login: 'Welcome back', signup: 'Create your account', reset: 'Reset your password' }[mode];
      var sub = { login: 'Sign in to continue to ' + esc(UI.config.name) + '.', signup: 'It\'s free and takes a few seconds.',
        reset: 'We\'ll email you a link to choose a new password.' }[mode];
      view.innerHTML = '<div class="au-wrap"><div class="ui-card au-card">' +
        '<h1>' + heading + '</h1><p class="muted">' + sub + '</p>' +
        (mode !== 'reset' ? '<div class="ui-seg" role="tablist"><button type="button" data-mode="login" class="' + (mode === 'login' ? 'on' : '') + '">Sign in</button>' +
          '<button type="button" data-mode="signup" class="' + (mode === 'signup' ? 'on' : '') + '">Create account</button></div>' : '<div style="height:14px"></div>') +
        '<form class="ui-stack" data-form="' + mode + '" novalidate>' +
        (mode === 'signup' ? '<label class="ui-field"><span>Your name</span><input type="text" name="name" autocomplete="name" required maxlength="60"></label>' : '') +
        '<label class="ui-field"><span>Email</span><input type="email" name="email" autocomplete="email" required></label>' +
        (mode === 'login' ? '<label class="ui-field"><span>Password</span>' + pw('password', 'current-password') + '</label>' : '') +
        (mode === 'signup' ? '<label class="ui-field"><span>Password <em>(at least 8 characters)</em></span>' + pw('password', 'new-password') + '</label>' +
          (window.LegalKit ? '<div>' + LegalKit.consentField() + '</div>' : '') : '') +
        '<div data-msg role="alert"' + (msg ? ' class="' + (isErr ? 'ui-error' : 'ui-note') + '">' + esc(msg) : ' hidden>') + '</div>' +
        '<button class="ui-btn primary block" type="submit">' + { login: 'Sign in', signup: 'Create account', reset: 'Send the link' }[mode] + '</button></form>' +
        (mode !== 'reset' ? '<div class="au-or">or</div><button type="button" class="ui-btn block au-google" data-google>' + GOOGLE_G + 'Continue with Google</button>' : '') +
        '<div class="au-links">' + (mode === 'login' ? '<a data-mode="reset">Forgot your password?</a>' : '<a data-mode="login">' + UI.icon('back') + ' Back to sign in</a>') +
        '<a href="#landing" data-go="landing">About ' + esc(UI.config.name) + '</a></div></div></div>';
      var first = view.querySelector('input');
      if (first && !msg) first.focus();
    }
    view.addEventListener('click', function (e) {
      var m = e.target.closest('[data-mode]');
      if (m) { e.preventDefault(); mode = m.getAttribute('data-mode'); history.replaceState(null, '', '#auth' + (mode === 'login' ? '' : '/' + mode)); draw(); return; }
      var g = e.target.closest('[data-google]');
      if (g) { google(g); return; }
      var s = e.target.closest('[data-show]');
      if (s) { var i = s.parentNode.querySelector('input'); i.type = i.type === 'password' ? 'text' : 'password'; s.textContent = i.type === 'password' ? 'Show' : 'Hide'; }
    });
    view.addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target, v = UI.formData(form);
      var problem = !/^\S+@\S+\.\S+$/.test(v.email || '') ? 'Please enter a valid email address.'
        : mode !== 'reset' && (v.password || '').length < (mode === 'signup' ? 8 : 1) ? (mode === 'signup' ? 'Please choose a password of at least 8 characters.' : 'Please enter your password.')
        : mode === 'signup' && (v.name || '').trim().length < 2 ? 'Please tell us your name.' : null;
      if (problem) { say(problem, true); return; }
      if (mode === 'signup' && window.LegalKit && !LegalKit.consentChecked(form)) return;  // the kit shows its own message
      UI.busy(form.querySelector('[type=submit]'), UI.auth(mode, v)).then(function (r) {
        if (mode === 'reset' || (r && !r.me)) { mode = 'login'; draw(r && r.message, false); restore({ email: v.email }); }
        else UI.toast(mode === 'signup' ? 'Welcome to ' + UI.config.name + '!' : 'Welcome back!', 'ok');
      }, function (err) { say(err.message, true); });
    });
    // Sign-up asks for the Privacy & Terms tick here too (ticking it is remembered for the new account).
    function google(btn) {
      var form = view.querySelector('form'), v = mode === 'signup' ? UI.formData(form) : {};
      if (mode === 'signup' && window.LegalKit && !LegalKit.consentChecked(form)) return;
      UI.busy(btn, UI.auth('google', { name: (v.name || '').trim() })).then(function () {
        UI.toast(mode === 'signup' ? 'Welcome to ' + UI.config.name + '!' : 'Welcome back!', 'ok');
      }, function (err) { say(err.message, true); });
    }
    function say(msg, isErr) {
      var box = view.querySelector('[data-msg]');
      box.className = isErr ? 'ui-error' : 'ui-note'; box.textContent = msg; box.hidden = false;
    }
    function restore(v) {
      ['name', 'email'].forEach(function (k) { var i = view.querySelector('[name=' + k + ']'); if (i && v[k]) i.value = v[k]; });
    }
    draw();
  });
})();

/* ===== deal.html ===== */
(function () {
  var esc = UI.esc;
  function slider(name, label, min, max, step, val, ends) {
    return '<div class="dl-slider"><div class="top"><label for="dl-' + name + '">' + label + '</label><output data-out="' + name + '"></output></div>' +
      '<input type="range" id="dl-' + name + '" data-s="' + name + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + val + '">' +
      (ends ? '<div class="ends"><span>' + ends[0] + '</span><span>' + ends[1] + '</span></div>' : '') + '</div>';
  }
  function chips(active) {
    return '<nav class="dl-chips" aria-label="Choose a property">' + GL.activeProps().map(function (p) {
      return '<a href="#deal/' + esc(p.id) + '" class="' + (p.id === active ? 'on' : '') + '">' + GL.house({ door: p.door, kind: p.kind, size: 26 }) + esc(p.name) + '</a>';
    }).join('') + '<a href="#deal/calculator" class="' + (active === 'calculator' ? 'on' : '') + '">' + UI.icon('percent') + 'Calculator</a></nav>';
  }

  UI.page('deal', { title: 'Deal check', nav: 'Deal check', icon: 'chart', auth: 'user', order: 30 }, function (view, ctx) {
    var stop = null, S = {};
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:300px"></div></div>';

    function head(sub) { return '<div class="ui-page-head"><div><h1>Deal check</h1><p class="muted">' + sub + '</p></div></div>'; }

    function drawProperty(p) {
      var m0 = GL.metrics(p);
      S = { value: Math.round(m0.value / 1000) * 1000 || 0, sell: m0.sellPct, appr: +p.appreciation, years: 10, rent: 2, cost: 2.5, renew: null };
      var vmax = Math.max(100000, Math.round(m0.value * 1.6 / 10000) * 10000), vmin = Math.max(0, Math.round(m0.value * .5 / 10000) * 10000);
      view.innerHTML = '<div class="ui-wrap">' + head('Is ' + esc(p.name) + ' a good deal? Slide the numbers and see.') + chips(p.id) +
        '<div class="dl-grid">' +
        '<section class="ui-card dl-card"><h2>If you sold today</h2><p class="muted small">What you\'d walk away with, against everything you put in.</p>' +
          slider('value', 'Sale price', vmin, vmax, 1000, S.value, [GL.money(vmin, { short: true }), GL.money(vmax, { short: true })]) +
          slider('sell', 'Selling costs', 0, 10, .5, S.sell, ['0%', '10%']) +
          '<div data-verdict></div><div class="dl-big" data-today></div><h3 style="margin:18px 0 0;font-size:1.05rem">Where it comes from</h3><div class="dl-why" data-why></div>' +
          '<p class="ui-hint" data-gap></p>' +
          '<div class="ui-row" style="margin-top:12px"><button class="ui-btn sm" data-keep>' + UI.icon('check') + 'Keep these estimates</button></div></section>' +
        '<section class="ui-card dl-card"><h2>If you keep it</h2><p class="muted small">Grow the value, pay down the mortgage, collect rent.</p>' +
          '<div class="dl-presets" data-presets>' + [[-1, 'Prices fall'], [2, 'Cautious'], [3.5, 'Typical'], [6, 'Hot market']].map(function (x) { return '<button data-preset="' + x[0] + '">' + x[1] + ' ' + x[0] + '%</button>'; }).join('') + '</div>' +
          slider('appr', 'Value grows per year', -3, 10, .25, S.appr, ['−3%', '10%']) +
          slider('years', 'Keep it for', 1, 30, 1, S.years, ['1 year', '30 years']) +
          '<div class="gl-form-grid">' + slider('rent', 'Rent rises per year', 0, 6, .5, S.rent) + slider('cost', 'Costs rise per year', 0, 6, .5, S.cost) + '</div>' +
          '<div data-future class="dl-big"></div><div data-proj style="margin-top:14px"></div>' +
          '<h3 style="margin:16px 0 0;font-size:1.05rem">What if prices grow faster or slower?</h3><p class="muted small" style="margin:2px 0 0">Profit if you sell after <span data-out="years2"></span>. Tap one to try it.</p><div class="dl-sens" data-sens></div>' +
          '<table class="dl-miles" data-miles></table></section>' +
        '</div>' +
        '<section class="ui-card dl-card dl-mort" id="dl-mortgage" style="margin-top:18px" data-mort></section>' +
        '<section class="ui-card dl-card" style="margin-top:18px"><h2>Quick ratios</h2><p class="muted small">Rules of thumb investors use. None of them tells the whole story.</p><div class="dl-ratios" data-ratios></div></section>' +
        '</div>';
      mortgage(p);
      update(p);
      if (ctx.args[1] === 'mortgage') setTimeout(function () { var el = view.querySelector('#dl-mortgage'); if (el) el.scrollIntoView({ behavior: 'smooth' }); }, 60);
    }

    function update(p) {
      var m = GL.metrics(p, { value: S.value, sellPct: S.sell });
      var out = function (k, v) { view.querySelectorAll('[data-out="' + k + '"]').forEach(function (o) { o.textContent = v; }); };
      out('value', GL.money(S.value)); out('sell', S.sell + '%'); out('appr', (S.appr > 0 ? '+' : '') + S.appr + '%'); out('years', UI.plural(+S.years, 'year')); out('years2', UI.plural(+S.years, 'year'));
      out('rent', S.rent + '%'); out('cost', S.cost + '%');
      view.querySelectorAll('[data-preset]').forEach(function (b) { b.classList.toggle('on', +b.getAttribute('data-preset') === +S.appr); });
      var v = GL.verdict(m.annual, m.profit);
      view.querySelector('[data-verdict]').innerHTML = '<div class="dl-verdict ' + v.key + '">' + GL.house({ door: p.door, kind: p.kind, glow: v.glow, smoke: v.key === 'great' || v.key === 'good' }) +
        '<div><h3>' + esc(v.label) + '</h3><p>' + esc(v.text) + '</p></div></div>';
      view.querySelector('[data-today]').innerHTML =
        '<div><span>You\'d walk away with</span><b>' + esc(GL.money(m.proceeds)) + '</b></div>' +
        '<div><span>Profit</span><b>' + GL.signed(m.profit) + '</b></div>' +
        '<div><span>Return on your money</span><b>' + esc(GL.pct(m.roi * 100, 0)) + '</b></div>' +
        '<div><span>Per year (over ' + esc(m.years.toFixed(1)) + ' yrs)</span><b>' + esc(GL.pct(m.annual * 100)) + '</b></div>';
      var parts = [['Price growth', m.appreciationGain], ['Mortgage paid down', m.paydown], ['Cash flow' + (m.first ? ' since ' + UI.fmtDate(GL.iso(m.since), { month: 'short', year: 'numeric' }) : ''), m.cfRecorded],
        ['Buying & improving', -((+p.closing_costs || 0) + (+p.improvements || 0) + m.capAll)], ['Selling costs', -m.sellCost]];
      if (Math.abs(m.gap) > 1) parts.push(['Down payment vs loan', m.gap]);
      var mx = Math.max.apply(null, parts.map(function (x) { return Math.abs(x[1]); })) || 1;
      view.querySelector('[data-why]').innerHTML = parts.map(function (x) {
        var w = Math.abs(x[1]) / mx * 50;
        return '<div class="r"><span>' + esc(x[0]) + '</span><span class="track"><span class="bar" style="' + (x[1] >= 0 ? 'left:50%;background:var(--gl-s1)' : 'right:50%;background:var(--gl-s2)') + ';width:' + w + '%"></span></span><span class="n">' + GL.signed(x[1]) + '</span></div>';
      }).join('');
      view.querySelector('[data-gap]').textContent = m.first ? 'Cash flow counts what you recorded in the ledger, minus mortgage payments over the same months.' : 'No ledger entries yet, so cash flow isn\'t counted. Record rent and costs on the Money page.';

      // the future
      var rows = GL.project(m, { years: +S.years, appr: +S.appr, rentGrowth: +S.rent, costGrowth: +S.cost, sellPct: +S.sell, value: S.value });
      var last = rows[rows.length - 1];
      view.querySelector('[data-future]').innerHTML =
        '<div><span>Worth in ' + UI.plural(+S.years, 'year') + '</span><b>' + esc(GL.money(last.value, { short: true })) + '</b></div>' +
        '<div><span>Still owed</span><b>' + esc(GL.money(last.balance, { short: true })) + '</b></div>' +
        '<div><span>Profit if sold then</span><b>' + GL.signed(last.profit, { short: true }) + '</b></div>' +
        '<div><span>Per year overall</span><b>' + esc(GL.pct(last.annual * 100)) + '</b></div>';
      var labels = rows.map(function (r) { return String(r.date.getFullYear()); });
      GL.lineChart(view.querySelector('[data-proj]'), { title: 'Value and mortgage over time', labels: labels, height: 220,
        series: [{ label: 'Value', color: 'var(--gl-s1)', values: rows.map(function (r) { return r.value; }), fillTo: 1 }, { label: 'Mortgage owed', color: 'var(--gl-s2)', values: rows.map(function (r) { return r.balance; }) }],
        note: 'Shaded: your equity', extraTip: function (i) { return '<div>Equity: <b>' + esc(GL.money(rows[i].equity)) + '</b></div><div>Profit if sold: <b>' + esc(GL.money(rows[i].profit)) + '</b></div>'; } });
      var sens = [-2, -1, 0, 1, 2, 3, 4, 5, 6, 8].map(function (a) {
        var r = GL.project(m, { years: +S.years, appr: a, rentGrowth: +S.rent, costGrowth: +S.cost, sellPct: +S.sell, value: S.value });
        return [a, r[r.length - 1].profit];
      });
      var smax = Math.max.apply(null, sens.map(function (s) { return Math.abs(s[1]); })) || 1;
      view.querySelector('[data-sens]').innerHTML = sens.map(function (s) {
        var t = Math.min(1, Math.abs(s[1]) / smax), col = s[1] >= 0 ? 'var(--gl-s1)' : 'var(--gl-s2)';
        return '<button data-preset="' + s[0] + '" class="' + (+S.appr === s[0] ? 'on' : '') + '" style="background:color-mix(in srgb, ' + col + ' ' + Math.round(8 + t * 30) + '%, var(--c-surface))" title="' + esc(GL.money(s[1])) + '">' +
          '<b>' + (s[0] > 0 ? '+' : '') + s[0] + '%</b><span>' + esc(GL.money(s[1], { short: true, sign: true })) + '</span></button>';
      }).join('');
      var ms = [1, 5, 10, 15, 20, 25, 30].filter(function (y) { return y <= +S.years; });
      if (ms[ms.length - 1] !== +S.years) ms.push(+S.years);
      view.querySelector('[data-miles]').innerHTML = '<thead><tr><th>After</th><th>Equity</th><th>Cash flow / yr</th><th>Profit if sold</th></tr></thead><tbody>' + ms.map(function (y) {
        var r = rows[y]; return '<tr><td>' + UI.plural(y, 'year') + '</td><td>' + esc(GL.money(r.equity, { short: true })) + '</td><td>' + GL.signed(r.cf, { short: true }) + '</td><td>' + GL.signed(r.profit, { short: true }) + '</td></tr>';
      }).join('') + '</tbody>';
      // ratios
      var rentY = m.rent * 12;
      view.querySelector('[data-ratios]').innerHTML =
        '<div><span class="small muted">Cap rate</span><b>' + esc(GL.pct(m.capRate * 100)) + '</b><p>Yearly rent minus costs (no mortgage), over the value. 4 to 6% is common in cities.</p></div>' +
        '<div><span class="small muted">Cash-on-cash</span><b>' + esc(GL.pct(m.cashOnCash * 100)) + '</b><p>A year of cash flow over the money you put in.</p></div>' +
        '<div><span class="small muted">Rent to value</span><b>' + esc(GL.pct(S.value ? rentY / 12 / S.value * 100 : 0, 2)) + '</b><p>Monthly rent over the value. The old "1% rule" is rare today.</p></div>';
    }

    function mortgage(p) {
      var box = view.querySelector('[data-mort]'), plans = GL.mortgagesOf(p.id);
      if (!plans.length) { box.innerHTML = '<h2>Mortgage</h2><p class="muted">No mortgage added for this property.</p><button class="ui-btn primary" data-add-mort>' + UI.icon('plus') + 'Add the mortgage</button>'; return; }
      var pl = plans[0], today = GL.today, bal = GL.balanceAt(pl, today), sofar = GL.paidBetween(pl, pl.start, today), ren = GL.renewal(pl), renDays = Math.round((ren - today) / 864e5);
      if (S.renew == null) S.renew = +pl.m.rate;
      var balRen = GL.balanceAt(pl, ren), leftYears = Math.max(1, (+pl.m.amort_years) - (+pl.m.term_years));
      box.innerHTML = '<div class="ui-row between"><h2 style="margin:0">Mortgage' + (plans.length > 1 ? ' (first of ' + plans.length + ')' : '') + '</h2><button class="ui-btn sm" data-edit-mort="' + esc(pl.m.id) + '">' + UI.icon('edit') + 'Edit</button></div>' +
        '<p class="muted small">' + esc((pl.m.lender ? pl.m.lender + ' · ' : '') + GL.money(pl.L) + ' at ' + pl.m.rate + '% over ' + pl.m.amort_years + ' years, ' + (pl.m.compounding === 'monthly' ? 'compounded monthly' : 'compounded twice a year')) + '</p>' +
        '<dl><div><dt>Each payment</dt><dd>' + esc(GL.money(pl.P, { cents: true })) + '</dd></div><div><dt>Per month</dt><dd>' + esc(GL.money(pl.monthly)) + '</dd></div><div><dt>Owed today</dt><dd>' + esc(GL.money(bal)) + '</dd></div>' +
        '<div><dt>Interest paid so far</dt><dd>' + esc(GL.money(sofar.interest)) + '</dd></div><div><dt>Principal paid so far</dt><dd>' + esc(GL.money(sofar.principal)) + '</dd></div>' +
        '<div><dt>' + (renDays >= 0 ? 'Renews in' : 'Renewed') + '</dt><dd>' + (renDays >= 0 ? UI.plural(renDays, 'day') : esc(UI.fmtDate(GL.iso(ren)))) + '</dd></div></dl>' +
        '<div data-amort></div>' +
        (renDays >= 0 && balRen > 0 ? '<div class="ui-card flat" style="margin-top:14px;background:var(--c-surface-2);border:0"><h3 style="margin:0">What if the rate changes at renewal?</h3>' +
          '<p class="muted small" style="margin:4px 0 0">On ' + esc(UI.fmtDate(GL.iso(ren))) + ' you\'ll still owe about ' + esc(GL.money(balRen)) + ', with ' + leftYears + ' years left.</p>' +
          slider('renew', 'Rate at renewal', 1, 10, .05, S.renew, ['1%', '10%']) + '<div data-renew class="dl-big"></div></div>' : '');
      var years = [], ints = [], prins = [];
      var y0 = pl.start.getFullYear(), yEnd = GL.addMonths(pl.start, Math.round(pl.payoff * 12 / pl.n)).getFullYear();
      for (var y = y0; y <= yEnd; y++) {
        var x = GL.paidBetween(pl, new Date(y - 1, 11, 31, 23), new Date(y, 11, 31, 23));
        years.push(String(y)); ints.push(x.interest); prins.push(x.principal);
      }
      GL.barChart(box.querySelector('[data-amort]'), { title: 'Interest and principal paid each year', labels: years, stacked: true, height: 200,
        series: [{ label: 'Principal (builds equity)', color: 'var(--gl-s1)', values: prins }, { label: 'Interest (claimable)', color: 'var(--gl-s2)', values: ints }],
        extraTip: function (i) { return '<div>Owed at year end: <b>' + esc(GL.money(GL.balanceAt(pl, new Date(+years[i], 11, 31, 23)))) + '</b></div>'; } });
      renew(pl);
    }
    function renew(pl) {
      var box = view.querySelector('[data-renew]'); if (!box) return;
      var ren = GL.renewal(pl), balRen = GL.balanceAt(pl, ren), leftYears = Math.max(1, (+pl.m.amort_years) - (+pl.m.term_years));
      var np = GL.plan(Object.assign({}, pl.m, { amount: balRen, rate: S.renew, amort_years: leftYears, start_date: GL.iso(ren) }));
      var diff = np.monthly - pl.monthly;
      view.querySelectorAll('[data-out="renew"]').forEach(function (o) { o.textContent = (+S.renew).toFixed(2) + '%'; });
      box.innerHTML = '<div><span>New payment per month</span><b>' + esc(GL.money(np.monthly)) + '</b></div><div><span>Change</span><b>' + (Math.abs(diff) < 1 ? 'No change' : GL.signed(-diff) + ' <span class="small muted">' + (diff > 0 ? 'more' : 'less') + '</span>') + '</b></div>';
    }

    function drawCalculator() {
      var c = UI.store.get('calc', { price: 500000, down: 20, rate: 4.79, amort: 25, frequency: 'monthly', compounding: GL.data.prefs.compounding || 'semiannual', rent: 2600, costs: 650 });
      view.innerHTML = '<div class="ui-wrap">' + head('Try a deal before you buy it, or test a refinance.') + chips('calculator') +
        '<div class="dl-grid"><section class="ui-card dl-card dl-calc"><h2>Mortgage and cash flow calculator</h2><form data-calc class="gl-form-grid">' +
        [['price', 'Price', c.price], ['down', 'Down payment (%)', c.down], ['rate', 'Interest rate (%)', c.rate], ['amort', 'Amortisation (years)', c.amort], ['rent', 'Monthly rent', c.rent], ['costs', 'Monthly costs (tax, insurance, upkeep)', c.costs]].map(function (f) {
          return '<label class="ui-field"><span>' + f[1] + '</span><input type="text" inputmode="decimal" name="' + f[0] + '" value="' + esc(f[2]) + '"></label>'; }).join('') +
        '<label class="ui-field"><span>Payments</span><select name="frequency">' + GL.opt(GL.FREQ, c.frequency) + '</select></label>' +
        '<label class="ui-field"><span>Compounding</span><select name="compounding">' + GL.opt([['semiannual', 'Twice a year (Canada)'], ['monthly', 'Monthly (US)']], c.compounding) + '</select></label></form></section>' +
        '<section class="ui-card dl-card"><h2>Result</h2><div class="dl-big" data-calc-out></div><div data-calc-chart style="margin-top:14px"></div></section></div></div>';
      calc();
    }
    function calc() {
      var form = view.querySelector('[data-calc]'); if (!form) return;
      var v = UI.formData(form), n = function (k) { return parseFloat(String(v[k]).replace(/[^0-9.\-]/g, '')) || 0; };
      UI.store.set('calc', v);
      var loan = n('price') * (1 - n('down') / 100);
      var pl = GL.plan({ amount: loan, rate: n('rate'), amort_years: n('amort') || 25, frequency: v.frequency, compounding: v.compounding, start_date: GL.iso(GL.today) });
      var total = pl.P * pl.payoff, interest = Math.max(0, total - loan), cash = n('rent') - n('costs') - pl.monthly;
      view.querySelector('[data-calc-out]').innerHTML = '<div><span>Each payment</span><b>' + esc(GL.money(pl.P, { cents: true })) + '</b></div><div><span>Per month</span><b>' + esc(GL.money(pl.monthly)) + '</b></div>' +
        '<div><span>Cash flow per month</span><b>' + GL.signed(cash) + '</b></div><div><span>Total interest</span><b>' + esc(GL.money(interest, { short: true })) + '</b></div>' +
        '<div><span>Borrowed</span><b>' + esc(GL.money(loan, { short: true })) + '</b></div><div><span>Cash-on-cash</span><b>' + esc(GL.pct(n('price') * n('down') / 100 > 0 ? cash * 12 / (n('price') * n('down') / 100) * 100 : 0)) + '</b></div>';
      var yrs = [], bal = [], paidI = [], cum = 0, years = Math.ceil(pl.payoff / pl.n);
      for (var y = 0; y <= years; y++) {
        var at = GL.addYears(pl.start, y); yrs.push('Yr ' + y); bal.push(GL.balanceAt(pl, at));
        if (y > 0) cum += GL.paidBetween(pl, GL.addYears(pl.start, y - 1), at).interest; paidI.push(cum);
      }
      GL.lineChart(view.querySelector('[data-calc-chart]'), { title: 'Balance and interest paid', labels: yrs, height: 210,
        series: [{ label: 'Still owed', color: 'var(--gl-s2)', values: bal }, { label: 'Interest paid so far', color: 'var(--gl-s1)', values: paidI, dash: true }] });
    }

    var current = null;
    function draw() {
      var props = GL.activeProps(), arg = ctx.args[0];
      if (arg === 'calculator' || (!props.length && GL.data)) { current = 'calculator'; drawCalculator(); return; }
      var p = GL.prop(arg) && !GL.prop(arg).archived ? GL.prop(arg) : props[0];
      current = p; drawProperty(p);
    }
    view.addEventListener('input', function (e) {
      var s = e.target.closest('[data-s]');
      if (s && current && current !== 'calculator') {
        var k = s.getAttribute('data-s'); S[k] = +s.value;
        if (k === 'renew') { renew(GL.mortgagesOf(current.id)[0]); return; }
        update(current); return;
      }
      if (e.target.closest('[data-calc]')) calc();
    });
    view.addEventListener('change', function (e) { if (e.target.closest('[data-calc]')) calc(); });
    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-preset]'))) { S.appr = +t.getAttribute('data-preset'); view.querySelector('[data-s="appr"]').value = S.appr; update(current); return; }
      if ((t = e.target.closest('[data-keep]'))) {
        UI.busy(t, UI.api('save_estimate', current.id, S.value, S.appr, S.sell)).then(function () { UI.toast('Saved as your estimates', 'ok'); return GL.load(); }).then(function () { current = GL.prop(current.id); });
        return;
      }
      if (e.target.closest('[data-add-mort]')) { GL.forms.mortgage(null, current.id, function () { GL.load().then(draw); }); return; }
      if ((t = e.target.closest('[data-edit-mort]'))) GL.forms.mortgage(GL.data.mortgages.filter(function (m) { return m.id === t.getAttribute('data-edit-mort'); })[0], current.id, function () { GL.load().then(draw); });
    });
    stop = GL.onResize(function () { if (current === 'calculator') calc(); else if (current) { update(current); mortgage(current); } });
    return { ready: GL.load().then(draw), destroy: function () { stop && stop(); } };
  });
})();

/* ===== home.html ===== */
(function () {
  var esc = UI.esc;
  function hello(name) {
    var h = new Date().getHours();
    return (h < 5 ? 'Good evening' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening') + ', ' + esc(name.split(' ')[0]);
  }
  function attention(d) {
    var items = [], today = GL.today, ym = GL.ym(today);
    d.tasks.filter(function (k) { return k.status === 'requested'; }).forEach(function (k) {
      items.push({ go: 'tenancy/' + k.tenancy_id, icon: 'wrench', cls: k.priority === 'urgent' ? 'bad' : '', t: (k.priority === 'urgent' ? 'Urgent: ' : 'New request: ') + k.title, s: k.where + ' · asked ' + UI.ago(k.requested_at) });
    });
    d.tenancies.filter(function (t) { return t.unread > 0; }).forEach(function (t) {
      items.push({ go: 'tenancy/' + t.id, icon: 'chat', cls: '', t: UI.plural(t.unread, 'new message') + ' from ' + t.tenant_name, s: t.last_message ? '"' + t.last_message.body.slice(0, 70) + (t.last_message.body.length > 70 ? '…' : '') + '"' : '' });
    });
    d.tenancies.filter(function (t) { return t.status === 'active'; }).forEach(function (t) {
      var paid = d.ledger.some(function (e) { return e.tenancy_id === t.id && e.category === 'rent' && e.rent_month === ym; });
      if (paid || today.getDate() < t.due_day) return;
      var late = today.getDate() - t.due_day;
      items.push({ go: 'money/rent', icon: 'receipt', cls: late > 5 ? 'bad' : 'warn', t: 'Rent not recorded: ' + t.tenant_name, s: GL.money(t.rent) + ' was due ' + (late === 0 ? 'today' : UI.plural(late, 'day') + ' ago') + ' · ' + t.property_name });
    });
    d.mortgages.forEach(function (m) {
      var p = GL.plan(m), r = GL.renewal(p), days = Math.round((r - today) / 864e5), prop = GL.prop(m.property_id);
      if (days >= 0 && days <= 150 && GL.balanceAt(p, today) > 0) items.push({ go: 'deal/' + m.property_id + '/mortgage', icon: 'percent', cls: days < 45 ? 'warn' : '', t: 'Mortgage renews in ' + UI.plural(days, 'day'), s: (prop ? prop.name + ' · ' : '') + 'try the "rate at renewal" slider' });
    });
    d.tasks.filter(function (k) { return k.status === 'scheduled' && k.scheduled_for; }).forEach(function (k) {
      var days = Math.round((GL.d(k.scheduled_for) - today) / 864e5);
      if (days >= 0 && days <= 7) items.push({ go: 'tenancy/' + k.tenancy_id, icon: 'calendar', cls: '', t: k.title + (days === 0 ? ' today' : days === 1 ? ' tomorrow' : ' in ' + days + ' days'), s: k.where });
    });
    return items;
  }

  UI.page('home', { title: 'Home', nav: 'Home', icon: 'home', auth: 'user', order: 10 }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:200px"></div><div class="ui-skel" style="height:120px;margin-top:16px"></div></div>';
    function empty(d) {
      view.innerHTML = '<div class="ui-wrap"><div class="hm-head"><div><div class="eyebrow">Welcome home</div><h1>' + hello(ctx.me.name) + '</h1></div></div>' +
        '<div class="ui-card hm-empty"><div><h2>Let\'s set up your first rental</h2><p class="muted">Add a property and its mortgage, and Good Landlord works out your cash flow, your equity and what you\'d make if you sold. Add tenants to give each one a private link for messages and repair requests.</p>' +
        '<div class="ui-row" style="margin-top:18px"><button class="ui-btn primary lg" data-add-prop>' + UI.icon('plus') + 'Add a property</button>' +
        '<button class="ui-btn lg" data-sample>' + UI.icon('sparkle') + 'Explore with a sample</button></div>' +
        '<p class="ui-hint" style="margin-top:12px">The sample adds three fictional rentals with tenants, rent and repairs to your account. You can clear it in one click.</p></div>' +
        GL.house({ door: 'red', glow: .9, smoke: true, size: 180 }) + '</div></div>';
    }
    function draw(d) {
      var props = GL.activeProps();
      if (!props.length && !d.properties.length) return empty(d);
      var ms = props.map(function (p) { return GL.metrics(p); });
      var sum = function (f) { return ms.reduce(function (s, m) { return s + f(m); }, 0); };
      var ym = GL.ym(GL.today);
      var expected = d.tenancies.filter(function (t) { return t.status === 'active'; }).reduce(function (s, t) { return s + t.rent; }, 0);
      var collected = d.ledger.filter(function (e) { return e.category === 'rent' && e.rent_month === ym; }).reduce(function (s, e) { return s + e.amount; }, 0);
      var cash = sum(function (m) { return m.cashMonthly; }), equity = sum(function (m) { return m.equity; }), profit = sum(function (m) { return m.profit; });
      var invested = sum(function (m) { return m.invested; });
      var att = attention(d), badges = GL.badges(d.stats);
      view.innerHTML = '<div class="ui-wrap">' +
        (d.has_sample ? '<div class="gl-banner">' + UI.icon('sparkle') + '<span style="flex:1;min-width:200px">You\'re exploring the <b>sample portfolio</b>. Everything here is fictional.</span><button class="ui-btn sm" data-clear-sample>Clear the sample</button></div>' : '') +
        '<div class="hm-head"><div><div class="eyebrow">' + esc(GL.today.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })) + '</div><h1>' + hello(ctx.me.name) + '</h1></div>' +
        '<div class="ui-row"><button class="ui-btn" data-add-entry>' + UI.icon('receipt') + 'Add expense</button><button class="ui-btn primary" data-add-prop>' + UI.icon('plus') + 'Property</button></div></div>' +
        '<div class="hm-street"><span class="moon" aria-hidden="true"></span><div class="row">' + props.map(function (p, i) {
          return '<button type="button" class="h" data-go="property/' + esc(p.id) + '" title="' + esc(p.name) + '">' + GL.house({ door: p.door, kind: p.kind, glow: GL.glowFor(ms[i].cashMonthly), smoke: ms[i].cashMonthly > 0, size: 104 }) + '<span class="lbl">' + esc(p.name) + '</span></button>';
        }).join('') + '<button type="button" class="h" data-add-prop title="Add a property"><span style="width:84px;height:94px;display:grid;place-items:center;border:2px dashed var(--c-faint);border-radius:16px;color:var(--c-muted)">' + UI.icon('plus') + '</span><span class="lbl">Add</span></button></div><div class="ground"></div></div>' +
        '<div class="gl-kpis">' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('receipt') + 'Rent this month</div><div class="val num">' + esc(GL.money(collected)) + '</div><div class="sub">of ' + esc(GL.money(expected)) + ' expected</div></div>' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('coins') + 'Cash flow per month</div><div class="val">' + GL.signed(cash) + '</div><div class="sub">after mortgage and typical costs</div></div>' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('key') + 'Your equity</div><div class="val num">' + esc(GL.money(equity, { short: true })) + '</div><div class="sub">value minus what you owe</div></div>' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('chart') + 'If you sold today</div><div class="val">' + GL.signed(profit, { short: true }) + '</div><div class="sub">profit on ' + esc(GL.money(invested, { short: true })) + ' put in</div></div>' +
        '</div>' +
        '<div class="hm-cols"><div><div class="ui-row between" style="margin-bottom:10px"><h2 style="margin:0;font-size:1.35rem">Your properties</h2><a href="#deal" class="small">Deal check ' + UI.icon('arrow') + '</a></div><div class="hm-props">' +
          props.map(function (p, i) {
            var m = ms[i];
            return '<a class="ui-card hm-prop" href="#property/' + esc(p.id) + '">' + GL.house({ door: p.door, kind: p.kind, glow: GL.glowFor(m.cashMonthly), size: 72 }) +
              '<div><h3>' + esc(p.name) + '</h3><div class="small muted">' + esc(p.address || GL.KINDS.filter(function (k) { return k[0] === p.kind; })[0][1]) + '</div>' +
              '<div class="nums"><span>Worth <b>' + esc(GL.money(m.value, { short: true })) + '</b></span><span>Owe <b>' + esc(GL.money(m.balance, { short: true })) + '</b></span><span>' + UI.plural(m.tenancies.length, 'tenancy', 'tenancies') + '</span></div></div>' +
              '<div class="cf"><b>' + GL.signed(m.cashMonthly) + '</b><span class="small muted">a month</span></div></a>';
          }).join('') +
          (d.properties.length > props.length ? '<p class="small muted">' + UI.plural(d.properties.length - props.length, 'archived property', 'archived properties') + ' not shown.</p>' : '') + '</div></div>' +
        '<div class="ui-stack"><div class="ui-card"><h3>Needs your attention</h3>' + (att.length ? '<div class="hm-att">' + att.slice(0, 8).map(function (a) {
            return '<a href="#' + esc(a.go) + '"><span class="dot ' + a.cls + '">' + UI.icon(a.icon) + '</span><span style="min-width:0"><b>' + esc(a.t) + '</b><span class="s">' + esc(a.s) + '</span></span></a>';
          }).join('') + '</div>' : '<p class="muted">All calm: no new requests, unread messages or late rent. ' + UI.icon('heart') + '</p>') + '</div>' +
          '<div class="ui-card"><h3>Your landlord badges</h3>' + (badges.length ? '<div class="hm-badges">' + badges.map(function (b) { return '<div>' + UI.icon(b[0]) + esc(b[1]) + '</div>'; }).join('') + '</div><p class="ui-hint">Tenants see these on their page. They come from how fast you answer and fix requests.</p>'
            : '<p class="muted small">Answer your tenants\' requests and badges appear here (and on their page).</p>') + '</div></div></div></div>';
    }
    view.addEventListener('click', function (e) {
      if (e.target.closest('[data-add-prop]')) { GL.forms.property(null, function (r) { UI.toast('Property added', 'ok'); UI.go('property', r.property.id); }); return; }
      if (e.target.closest('[data-add-entry]')) { GL.forms.entry(null, { property_id: GL.activeProps()[0] && GL.activeProps()[0].id }, function () { UI.toast('Saved', 'ok'); load(); }); return; }
      var s = e.target.closest('[data-sample]');
      if (s) { UI.busy(s, UI.api('load_sample')).then(function () { UI.toast('Sample loaded: have a look around!', 'ok'); load(); }); return; }
      var c = e.target.closest('[data-clear-sample]');
      if (c) UI.confirm({ title: 'Clear the sample?', text: 'The sample properties, tenants, records and ledger entries are removed. Anything you added yourself stays.', ok: 'Clear it', danger: true })
        .then(function (y) { if (y) UI.busy(c, UI.api('clear_sample')).then(function () { UI.toast('Sample cleared', 'ok'); load(); }); });
    });
    function load() { return GL.load().then(draw); }
    return load();
  });
})();

/* ===== landing.html ===== */
// Watch section: swap the video's cover for YouTube's player (privacy-enhanced) only when it's pressed.
  if (!window.__ytFilm) {
    window.__ytFilm = true;
    document.addEventListener('click', function (e) {
      var b = e.target && e.target.closest ? e.target.closest('[data-yt-film]') : null;
      if (!b) return;
      var f = document.createElement('iframe');
      f.src = 'https://www.youtube-nocookie.com/embed/' + b.getAttribute('data-yt-film') + '?autoplay=1&rel=0&playsinline=1';
      f.title = b.getAttribute('data-yt-title') || 'Video';
      f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      f.allowFullscreen = true;
      f.referrerPolicy = 'strict-origin-when-cross-origin';
      b.parentNode.replaceChild(f, b);
    });
  }
(function () {
  var COPY = {
    eyebrow: 'For landlords who want to be good ones',
    title: 'Know your numbers. <em>Keep your word.</em>',
    lead: 'Track rent and every claimable expense, see your cash flow and what you\'d really make if you sold, and give each tenant a private page where every message and repair request is dated and kept for good.',
    cta: 'Start free',
    proof: ['Free to use', 'Tenants need no account', 'Records nobody can delete'],
    stepsTitle: 'How it works',
    stepsLead: 'Ten minutes to set up, then a few taps a month.',
    steps: [['Add your rentals', 'Purchase price, mortgage, today\'s value. Good Landlord works out payments, interest and equity for you.'],
            ['Record money in and out', 'Mark rent paid in one tap; file each expense under a tax category so the year-end summary writes itself.'],
            ['Send each tenant their link', 'They write and ask for repairs there. You move requests along; every date is on record for both of you.']],
    featuresTitle: 'Everything a small landlord needs',
    features: [['coins', 'Claimable expenses', 'Categories that follow the rental tax forms (T776, Schedule E), with mortgage interest worked out for you.'],
               ['chart', 'Deal check', 'Slide the price, appreciation and years you keep it, and watch profit, equity and your yearly return change.'],
               ['percent', 'Mortgage calculator', 'Canadian or US compounding, any payment schedule, and a "rate at renewal" slider before your term ends.'],
               ['seal', 'A record nobody can rewrite', 'Messages are never edited or deleted, and each entry is sealed with a fingerprint of the one before it.'],
               ['wrench', 'Repairs with dates', 'Requested, seen, scheduled, done, confirmed: each step dated. Costs go straight into your ledger.'],
               ['heart', 'Badges tenants can see', 'Reply fast and fix things quickly, and your tenants see it: "usually replies in 3 hours".']],
    faq: [['Is it free?', 'Yes. Good Landlord is free to use, with no ads.'],
          ['Does my tenant need to sign up?', 'No. You send them a private link. Whoever has the link can read and write in that tenancy\'s record, so send it only to your tenant. You can make a new link at any time, which stops the old one.'],
          ['Can anyone delete or change a message?', 'No. There\'s no edit or delete button for anyone, landlord included. Each entry is sealed with a SHA-256 fingerprint of its text, its time and the entry before it, so a change made behind the scenes would show up as a broken seal. Both sides can download the whole record.'],
          ['Is this tax advice?', 'No. It sorts what you record into the usual rental-income lines so you (or your accountant) can fill the forms faster. Rules differ by country and situation.'],
          ['What does my tenant see?', 'Their own lease (rent, due day, deposit), the messages and requests, the rent you recorded as received, and your response badges. Never your other properties, costs or numbers.'],
          ['Can I try it first?', 'Yes. Open the tenant demo below without an account, or sign up and load the sample portfolio: three fictional rentals with tenants, rent, repairs and a mortgage renewal coming up.']],
    bandTitle: 'Be the landlord you\'d want to rent from.',
    bandLead: 'Free, private, and ready in minutes.'
  };

  // before: the shoebox. after: the same rental in the app. Drag the handle (a range input, so keys work too).
  function heroArt() {
    var mess = '<div class="side lp-mess" aria-hidden="true"><span class="ring" style="left:58%;top:58%"></span>' +
      '<div class="p rc" style="left:4%;top:16%;transform:rotate(-8deg)"><b>HOME HARDWARE</b>Faucet cartridge 18.49<br>Plumber tape 3.99<br>TOTAL 25.15<br>Oct 2?</div>' +
      '<div class="p rc hide-s" style="left:21%;top:52%;transform:rotate(6deg)"><b>Insurance?</b>Policy 88-221<br>renews ???<br>$1,140 / yr</div>' +
      '<div class="p st" style="left:30%;top:9%;transform:rotate(4deg)">Upstairs paid?? cash or e-transfer? ask</div>' +
      '<div class="p st pk hide-s" style="left:5%;top:62%;transform:rotate(-5deg)">Property tax due… March? April?</div>' +
      '<div class="sms" style="left:36%;top:44%;transform:rotate(-2deg)"><small>Tenant · 11:42 PM</small>the kitchen tap is dripping again??</div>' +
      '<div class="sms hide-s" style="left:30%;top:72%;transform:rotate(2deg)"><small>Tenant · 3 weeks later</small>did you get my text about the tap</div>' +
      '<span class="q" style="left:46%;top:24%">?</span></div>';
    var app = '<div class="side lp-app" aria-hidden="true"><div class="scene"><span class="sun"></span>' + GL.house({ door: 'red', kind: 'duplex', glow: .95, smoke: true }) + '<span class="gnd"></span></div>' +
      '<div class="tag t1"><span class="muted">Cash flow this month</span><b class="gl-pos">+$612</b></div>' +
      '<div class="tag t2"><div class="row">' + GL.statusChip('done') + '<span class="small faint">#4</span></div><b style="font-size:1rem">Kitchen tap drips</b><span class="muted">Asked Monday · fixed Wednesday · $25.15 claimed</span></div>' +
      '<div class="tag t3">' + UI.icon('seal') + 'Sealed record · 38 entries</div></div>';
    return '<div class="lp-ba" data-ba>' + mess + app +
      '<span class="lbl l" aria-hidden="true">The shoebox</span><span class="lbl r" aria-hidden="true">Good Landlord</span>' +
      '<input type="range" min="0" max="100" value="50" aria-label="Drag to compare the shoebox with the same rental in Good Landlord"><span class="handle"></span></div>';
  }

  UI.page('landing', { title: 'Welcome' }, function (view, ctx) {
    var me = ctx.me, C = COPY, esc = UI.esc;
    var primary = me ? '<a class="ui-btn primary lg" href="#home" data-go="home">Open the app ' + UI.icon('arrow') + '</a>'
      : '<a class="ui-btn primary lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + ' ' + UI.icon('arrow') + '</a>' +
        '<a class="ui-btn lg" href="#auth" data-go="auth">I have an account</a>';
    view.innerHTML =
      '<section class="lp-hero"><div class="ui-wrap"><div class="lp-pitch">' +
        '<div class="eyebrow">' + esc(C.eyebrow) + '</div><h1>' + C.title + '</h1><p class="lp-lead">' + esc(C.lead) + '</p>' +
        '<div class="lp-cta">' + primary + '<a class="ui-btn lg ghost" href="#t/demo-upstairs">' + UI.icon('key') + 'See the tenant side</a></div>' +
        '<div class="lp-proof">' + C.proof.map(function (p) { return '<span>' + UI.icon('check') + esc(p) + '</span>'; }).join('') + '</div>' +
      '</div>' + heroArt() + '</div></section>' +
      '<section class="lp-section ytf" id="watch"><div class="ui-wrap"><div class="ytf-in"><div class="ytf-copy"><div class="eyebrow"><svg viewBox="0 0 28 20" width="20" height="14" aria-hidden="true"><rect width="28" height="20" rx="5" fill="#FF0033"/><path d="M11.2 5.8v8.4l7.3-4.2z" fill="#fff"/></svg>Watch</div><h2>See Good Landlord in about a minute</h2><p>A short video tour of what Good Landlord does and how it works.</p><a class="ytf-link" href="https://www.youtube.com/watch?v=qv8jRRY0KG0" target="_blank" rel="noopener">Watch on YouTube &#8599;</a></div><div><div class="ytf-frame"><button type="button" class="ytf-cover" data-yt-film="qv8jRRY0KG0" data-yt-title="Good Landlord video" aria-label="Play the Good Landlord video (1:16)"><img src="_/theme/yt-cover.jpg" alt="" loading="lazy" decoding="async" width="960" height="540"><span class="ytf-play" aria-hidden="true"><svg viewBox="0 0 68 48" width="68" height="48"><path d="M66.5 7.7a8.5 8.5 0 0 0-6-6C55.3.3 34 .3 34 .3s-21.3 0-26.5 1.4a8.5 8.5 0 0 0-6 6C.1 13 .1 24 .1 24s0 11 1.4 16.3a8.5 8.5 0 0 0 6 6c5.2 1.4 26.5 1.4 26.5 1.4s21.3 0 26.5-1.4a8.5 8.5 0 0 0 6-6C67.9 35 67.9 24 67.9 24s0-11-1.4-16.3z" fill="#FF0033"/><path d="M45 24 27 14v20z" fill="#fff"/></svg></span><span class="ytf-len">1:16</span></button></div><p class="ytf-note">The video loads from YouTube when you press play.</p></div></div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Good for both sides of the door</h2><p>One place for the numbers only you see, and one fair record you share.</p></div><div class="lp-two">' +
        '<div class="ui-card"><div class="who">For you, the landlord</div><h3 style="margin-top:8px">Your rentals, in plain numbers</h3><ul>' +
          ['Rent roll: who paid, who\'s late, one tap to record it', 'Every expense sorted into claimable categories', 'Cash flow per property, after the mortgage', 'Profit if you sold today, and in 5, 10 or 20 years', 'Alerts for new requests, unread messages and renewals'].map(function (x) { return '<li>' + UI.icon('check') + esc(x) + '</li>'; }).join('') + '</ul></div>' +
        '<div class="ui-card"><div class="who">For your tenants</div><h3 style="margin-top:8px">A fair, permanent record</h3><ul>' +
          ['A private page, no account or app needed', 'Messages that can\'t be edited or deleted, by anyone', 'Repair requests with the date asked and the date fixed', 'Rent receipts and the lease details in one place', 'Download the whole record any time'].map(function (x) { return '<li>' + UI.icon('check') + esc(x) + '</li>'; }).join('') + '</ul>' +
          '<a class="ui-btn" href="#t/demo-upstairs" style="margin-top:16px">' + UI.icon('key') + 'Open the tenant demo</a></div></div></div></section>' +
      '<section class="lp-section" id="how"><div class="ui-wrap"><div class="lp-head"><h2>' + esc(C.stepsTitle) + '</h2><p>' + esc(C.stepsLead) + '</p></div>' +
        '<div class="lp-steps">' + C.steps.map(function (s) { return '<div class="ui-card lp-step"><h3>' + esc(s[0]) + '</h3><p class="muted">' + esc(s[1]) + '</p></div>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>' + esc(C.featuresTitle) + '</h2></div>' +
        '<div class="ui-grid">' + C.features.map(function (f) { return '<div class="ui-card lp-feature">' + UI.icon(f[0]) + '<h3>' + esc(f[1]) + '</h3><p>' + esc(f[2]) + '</p></div>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><h2>Questions</h2></div><div class="lp-faq">' +
        C.faq.map(function (q) { return '<details><summary>' + esc(q[0]) + '</summary><p>' + esc(q[1]) + '</p></details>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-band"><div><h2>' + esc(C.bandTitle) + '</h2><p>' + esc(C.bandLead) + '</p></div>' +
        (me ? '<a class="ui-btn lg" href="#home" data-go="home">Open the app</a>' : '<a class="ui-btn lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + '</a>') +
      '</div></div></section>';
    var ba = view.querySelector('[data-ba]');
    if (ba) ba.querySelector('input').addEventListener('input', function (e) { ba.style.setProperty('--x', e.target.value + '%'); });
  });
})();

/* ===== money.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['ledger', 'Ledger', 'coins'], ['rent', 'Rent roll', 'receipt'], ['tax', 'Tax summary', 'percent']];
  UI.page('money', { title: 'Money', nav: 'Money', icon: 'coins', auth: 'user', order: 20 }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'ledger';
    var f = { prop: ctx.args[1] || UI.store.get('money.prop', ''), year: '', kind: 'all', cat: '' };
    var rentMonth = null, taxYear = null;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Money</h1><p class="muted">Rent in, costs out, and what you can claim.</p></div>' +
      '<div class="ui-row"><button class="ui-btn primary" data-add>' + UI.icon('plus') + 'Add entry</button></div></div>' +
      '<nav class="ui-tabs">' + TABS.map(function (t) { return '<a href="#money/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + '</a>'; }).join('') + '</nav><div data-body><div class="ui-skel"></div></div></div>';
    var body = view.querySelector('[data-body]');

    function propSelect(val, allLabel) {
      return '<select data-f="prop"><option value="">' + esc(allLabel || 'All properties') + '</option>' + GL.opt(GL.data.properties.map(function (p) { return [p.id, p.name + (p.archived ? ' (archived)' : '')]; }), val) + '</select>';
    }
    function years() {
      var ys = {}; ys[GL.today.getFullYear()] = 1;
      GL.data.ledger.forEach(function (e) { ys[e.date.slice(0, 4)] = 1; });
      return Object.keys(ys).sort().reverse();
    }

    /* ---------------- ledger */
    function ledger() {
      var d = GL.data;
      if (!d.properties.length) { body.innerHTML = noProps(); return; }
      var rows = d.ledger.filter(function (e) {
        return (!f.prop || e.property_id === f.prop) && (!f.year || e.date.slice(0, 4) === f.year) && (f.kind === 'all' || e.kind === f.kind) && (!f.cat || e.category === f.cat);
      });
      var inc = 0, out = 0; rows.forEach(function (e) { if (e.kind === 'income') inc += e.amount; else out += e.amount; });
      var groups = {}, order = [];
      rows.forEach(function (e) { var k = e.date.slice(0, 7); if (!groups[k]) { groups[k] = []; order.push(k); } groups[k].push(e); });
      body.innerHTML = '<div class="mn-filters">' + propSelect(f.prop) +
        '<select data-f="year"><option value="">All years</option>' + GL.opt(years().map(function (y) { return [y, y]; }), f.year) + '</select>' +
        '<select data-f="cat"><option value="">All categories</option>' + GL.opt(d.categories.map(function (c) { return [c.id, c.label]; }), f.cat) + '</select>' +
        '<div class="ui-seg">' + [['all', 'All'], ['income', 'In'], ['expense', 'Out']].map(function (k) { return '<button data-kind="' + k[0] + '" class="' + (f.kind === k[0] ? 'on' : '') + '">' + k[1] + '</button>'; }).join('') + '</div>' +
        '<span class="ui-spacer"></span><button class="ui-btn sm" data-csv>' + UI.icon('download') + 'CSV</button></div>' +
        '<div class="mn-sum"><div class="gl-kpi"><div class="lbl">Money in</div><div class="val num">' + esc(GL.money(inc)) + '</div></div>' +
        '<div class="gl-kpi"><div class="lbl">Money out</div><div class="val num">' + esc(GL.money(out)) + '</div></div>' +
        '<div class="gl-kpi"><div class="lbl">Difference</div><div class="val">' + GL.signed(inc - out) + '</div><div class="sub">before mortgage payments</div></div></div>' +
        (order.length ? order.map(function (k) {
          var s = 0; groups[k].forEach(function (e) { s += e.kind === 'income' ? e.amount : -e.amount; });
          return '<div class="mn-month"><h4><span>' + esc(GL.monthName(k)) + '</span><span>' + GL.signed(s) + '</span></h4>' + groups[k].map(row).join('') + '</div>';
        }).join('') : '<div class="ui-empty">' + UI.icon('coins') + '<h3>Nothing here</h3><p>No entries match these filters.</p></div>');
    }
    function row(e) {
      var c = GL.cat[e.category] || { label: e.category }, p = GL.prop(e.property_id);
      var claim = c.claim === 'yes' ? '<span class="ui-badge sage">Claimable</span>' : c.claim === 'capital' ? '<span class="ui-badge honey">Capital</span>' : c.claim === 'no' ? '<span class="ui-badge">Not claimable</span>' : '';
      return '<button class="mn-row" data-entry="' + esc(e.id) + '"><span class="dt">' + esc(UI.fmtDate(e.date, { day: 'numeric', month: 'short' })) + '</span>' +
        '<span style="min-width:0"><b>' + esc(e.memo || c.label) + '</b><span class="c">' + esc(c.label) + ' · ' + esc(p ? p.name : '') + ' ' + claim + (e.task_id ? '<span class="ui-badge">From a request</span>' : '') + '</span></span>' +
        '<span class="amt ' + (e.kind === 'income' ? 'gl-pos' : '') + '">' + (e.kind === 'income' ? '+' : '−') + esc(GL.money(e.amount, { cents: true })) + '</span></button>';
    }
    function csv() {
      var lines = [['date', 'property', 'kind', 'category', 'claimable', 'amount', 'memo'].join(',')];
      var q = function (s) { s = String(s == null ? '' : s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
      GL.data.ledger.filter(function (e) { return (!f.prop || e.property_id === f.prop) && (!f.year || e.date.slice(0, 4) === f.year); }).forEach(function (e) {
        var c = GL.cat[e.category] || {}, p = GL.prop(e.property_id) || {};
        lines.push([e.date, q(p.name), e.kind, q(c.label), c.claim || '', (e.kind === 'income' ? '' : '-') + e.amount.toFixed(2), q(e.memo)].join(','));
      });
      GL.download('good-landlord-ledger' + (f.year ? '-' + f.year : '') + '.csv', lines.join('\n'), 'text/csv;charset=utf-8');
    }

    /* ---------------- rent roll */
    function rent() {
      var d = GL.data;
      rentMonth = rentMonth || GL.ym(GL.today);
      var tens = d.tenancies.filter(function (t) { return t.status === 'active' || d.ledger.some(function (e) { return e.tenancy_id === t.id && e.rent_month === rentMonth; }); });
      var expected = 0, got = 0;
      var parts = rentMonth.split('-'), y = +parts[0], mo = +parts[1];
      var rows = tens.map(function (t) {
        var paid = d.ledger.filter(function (e) { return e.tenancy_id === t.id && e.category === 'rent' && e.rent_month === rentMonth; })[0];
        expected += t.rent; if (paid) got += paid.amount;
        var due = new Date(y, mo - 1, t.due_day, 12), days = Math.round((GL.today - due) / 864e5), st;
        if (paid) st = '<span class="ui-badge good">' + UI.icon('check') + 'Paid ' + esc(UI.fmtDate(paid.date, { day: 'numeric', month: 'short' })) + '</span>';
        else if (days > 0) st = '<span class="ui-badge ' + (days > 5 ? 'bad' : 'warn') + '">Late ' + UI.plural(days, 'day') + '</span>';
        else if (days === 0) st = '<span class="ui-badge warn">Due today</span>';
        else st = '<span class="ui-badge">Due in ' + UI.plural(-days, 'day') + '</span>';
        return '<div class="mn-rent"><div><b>' + esc(t.tenant_name) + '</b><div class="small muted">' + esc(t.property_name + (t.unit ? ' · ' + t.unit : '')) + ' · day ' + t.due_day + '</div></div>' +
          '<div class="st">' + st + '</div><div class="ui-row">' + (paid ? '<button class="ui-btn sm ghost" data-entry="' + esc(paid.id) + '">' + esc(GL.money(paid.amount)) + '</button>'
            : '<button class="ui-btn sm primary" data-paid="' + esc(t.id) + '">' + UI.icon('check') + 'Paid ' + esc(GL.money(t.rent)) + '</button>') + '</div></div>';
      });
      body.innerHTML = '<div class="ui-row between" style="margin-bottom:14px"><div class="ui-row"><button class="ui-btn icon" data-month="-1" aria-label="Previous month">' + UI.icon('back') + '</button>' +
        '<h2 style="margin:0;font-size:1.4rem;min-width:170px;text-align:center">' + esc(GL.monthName(rentMonth)) + '</h2><button class="ui-btn icon" data-month="1" aria-label="Next month">' + UI.icon('arrow') + '</button></div>' +
        (rentMonth !== GL.ym(GL.today) ? '<button class="ui-btn sm ghost" data-month="0">This month</button>' : '') + '</div>' +
        '<div class="ui-card"><div class="ui-row between"><b>' + esc(GL.money(got)) + ' of ' + esc(GL.money(expected)) + ' collected</b><span class="muted small">' + (expected ? Math.round(got / expected * 100) : 0) + '%</span></div>' +
        '<div class="mn-bar" role="progressbar" aria-valuenow="' + Math.round(got) + '" aria-valuemax="' + Math.round(expected) + '"><span style="width:' + (expected ? Math.min(100, got / expected * 100) : 0) + '%"></span></div>' +
        '<p class="ui-hint">Marking rent as paid adds it to the ledger and writes a receipt into the tenant\'s record.</p></div>' +
        '<div class="ui-card" style="margin-top:14px">' + (rows.length ? rows.join('') : '<p class="muted" style="margin:0">No active tenancies. Add a tenant from a property page.</p>') + '</div>';
    }

    /* ---------------- tax summary */
    function tax() {
      var d = GL.data;
      taxYear = taxYear || String(GL.today.getFullYear());
      var rows = d.ledger.filter(function (e) { return e.date.slice(0, 4) === taxYear && (!f.prop || e.property_id === f.prop); });
      var by = {}; rows.forEach(function (e) { by[e.category] = (by[e.category] || 0) + e.amount; });
      var start = new Date(+taxYear, 0, 1, 12), end = new Date(+taxYear, 11, 31, 12), partial = end > GL.today;
      if (partial) end = GL.today;
      var interest = [];
      d.properties.forEach(function (p) {
        if (f.prop && p.id !== f.prop) return;
        GL.mortgagesOf(p.id).forEach(function (pl) { var x = GL.paidBetween(pl, start, end); if (x.interest > 0.5) interest.push({ name: p.name, lender: pl.m.lender, v: x.interest, principal: x.principal }); });
      });
      var incomeRows = d.categories.filter(function (c) { return c.kind === 'income' && by[c.id]; });
      var expRows = d.categories.filter(function (c) { return c.claim === 'yes' && by[c.id]; });
      var totalInc = incomeRows.reduce(function (s, c) { return s + by[c.id]; }, 0);
      var totalInt = interest.reduce(function (s, x) { return s + x.v; }, 0);
      var totalExp = expRows.reduce(function (s, c) { return s + by[c.id]; }, 0) + totalInt;
      var cap = rows.filter(function (e) { return e.category === 'capital'; }), nc = rows.filter(function (e) { return e.category === 'personal'; });
      var principal = interest.reduce(function (s, x) { return s + x.principal; }, 0);
      var region = d.prefs.region || 'ca';
      var tr = function (label, v, extra) { return '<tr><td>' + label + (extra || '') + '</td><td class="n">' + esc(GL.money(v, { cents: true })) + '</td></tr>'; };
      body.innerHTML = '<div class="mn-filters">' + propSelect(f.prop) + '<select data-taxyear>' + GL.opt(years().map(function (y) { return [y, y]; }), taxYear) + '</select>' +
        '<span class="ui-spacer"></span><button class="ui-btn sm" data-print onclick="window.print()">' + UI.icon('download') + 'Print or save as PDF</button></div>' +
        '<div class="ui-card mn-tax"><div class="ui-row between"><h2 style="margin:0">Rental income ' + esc(taxYear) + '</h2>' + (partial ? '<span class="ui-badge honey">So far this year</span>' : '') + '</div>' +
        '<p class="muted small" style="margin-top:6px">' + esc(GL.TAX_FORM[region]) + ' <a href="#profile" data-go="profile">Change country</a></p>' +
        '<table><thead><tr><th>Income</th><th class="n">Amount</th></tr></thead><tbody>' + incomeRows.map(function (c) { return tr(esc(c.label), by[c.id]); }).join('') +
        '<tr class="tot"><td>Gross rental income</td><td class="n">' + esc(GL.money(totalInc, { cents: true })) + '</td></tr></tbody></table>' +
        '<h3>Claimable expenses</h3><table><tbody>' + expRows.map(function (c) { return tr(esc(c.label), by[c.id]); }).join('') +
        interest.map(function (x) { return tr('Mortgage interest · ' + esc(x.name), x.v, ' <span class="ui-badge sage mn-auto">worked out for you</span>'); }).join('') +
        '<tr class="tot"><td>Total claimable</td><td class="n">' + esc(GL.money(totalExp, { cents: true })) + '</td></tr></tbody></table>' +
        '<h3>Net rental income</h3><p style="font:650 2rem/1.1 var(--font-display);margin:0">' + GL.signed(totalInc - totalExp, { cents: true }) + '</p>' +
        '<p class="muted small">Gross income minus claimable expenses, before depreciation (capital cost allowance). ' + (totalInc - totalExp < 0 ? 'A rental loss can often reduce your other income\'s tax; ask your accountant.' : '') + '</p>' +
        (cap.length ? '<h3>Capital improvements (not claimed all at once)</h3><p class="muted small">These are depreciated over several years (capital cost allowance in Canada, depreciation in the US). Give this list to your accountant.</p><table><tbody>' +
          cap.map(function (e) { return tr(esc(e.memo || 'Improvement') + ' <span class="muted small">' + esc(UI.fmtDate(e.date)) + ' · ' + esc((GL.prop(e.property_id) || {}).name || '') + '</span>', e.amount); }).join('') + '</tbody></table>' : '') +
        ((nc.length || principal > 1) ? '<h3>Not claimable</h3><table><tbody>' + (principal > 1 ? tr('Mortgage principal repaid', principal, ' <span class="muted small">(it builds your equity instead)</span>') : '') +
          nc.map(function (e) { return tr(esc(e.memo || 'Not claimable'), e.amount); }).join('') + '</tbody></table>' : '') +
        '<p class="ui-hint" style="margin-top:20px">' + UI.icon('info') + ' A helpful summary of what you recorded, not tax advice. Rules differ by country and situation; check with an accountant before you file.</p></div>';
    }

    function noProps() { return '<div class="ui-empty">' + UI.icon('home') + '<h3>Add a property first</h3><p>Then record rent and expenses here.</p><a class="ui-btn primary" href="#home">Go to Home</a></div>'; }
    var DRAW = { ledger: ledger, rent: rent, tax: tax };
    function redraw() { DRAW[tab](); }

    view.addEventListener('change', function (e) {
      var s = e.target.closest('[data-f]');
      if (s) { f[s.getAttribute('data-f')] = s.value; if (s.getAttribute('data-f') === 'prop') UI.store.set('money.prop', s.value); redraw(); return; }
      if (e.target.matches('[data-taxyear]')) { taxYear = e.target.value; tax(); }
    });
    view.addEventListener('click', function (e) {
      var t;
      if ((t = e.target.closest('[data-kind]'))) { f.kind = t.getAttribute('data-kind'); ledger(); return; }
      if (e.target.closest('[data-csv]')) { csv(); return; }
      if (e.target.closest('[data-add]')) {
        if (!GL.data.properties.length) { UI.toast('Add a property first.'); return; }
        GL.forms.entry(null, { property_id: f.prop || (GL.activeProps()[0] || GL.data.properties[0]).id }, function () { UI.toast('Saved', 'ok'); GL.load().then(redraw); }); return;
      }
      if ((t = e.target.closest('[data-entry]'))) { GL.forms.entry(GL.data.ledger.filter(function (x) { return x.id === t.getAttribute('data-entry'); })[0], null, function () { GL.load().then(redraw); }); return; }
      if ((t = e.target.closest('[data-month]'))) {
        var step = +t.getAttribute('data-month'), p = rentMonth.split('-');
        rentMonth = step === 0 ? GL.ym(GL.today) : GL.ym(GL.addMonths(new Date(+p[0], +p[1] - 1, 15), step)); rent(); return;
      }
      if ((t = e.target.closest('[data-paid]'))) {
        var ten = GL.tenancyById(t.getAttribute('data-paid'));
        UI.busy(t, UI.api('mark_rent_paid', ten.id, rentMonth, ten.rent, null)).then(function () { UI.toast('Rent recorded for ' + ten.tenant_name, 'ok'); return GL.load().then(rent); });
      }
    });
    return GL.load().then(redraw);
  });
})();

/* ===== profile.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('profile', { title: 'Your profile', auth: 'user' }, function (view, ctx) {
    var me = ctx.me;
    view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="pf-head"><span class="ui-avatar">' + esc(UI.initials(me.name)) + '</span>' +
      '<div><h1>' + esc(me.name) + '</h1><div class="muted">' + esc(me.email) + (me.joined ? ' · member since ' + esc(UI.fmtDate(me.joined, { month: 'long', year: 'numeric' })) : '') + '</div></div></div>' +
      '<div class="pf-grid"><form class="ui-card ui-stack" data-name><h3>Your name</h3><label class="ui-field"><span>Shown to other people</span>' +
      '<input type="text" name="name" value="' + esc(me.name) + '" maxlength="60" required></label><button class="ui-btn primary" type="submit">Save</button></form>' +
      '<div class="ui-card ui-stack"><h3>Appearance</h3><p class="muted small">Follow your device, or pick one.</p><div data-theme-box></div>' +
      '<h3 style="margin-top:22px">Password</h3><p class="muted small">We\'ll email you a link to choose a new one.</p>' +
      '<button class="ui-btn" data-reset>' + UI.icon('mail') + 'Email me a reset link</button></div></div>' +
      '<form class="ui-card ui-stack" data-prefs style="margin-top:16px"><h3>Money and taxes</h3><p class="muted small" style="margin:0">Used for amounts, the tax summary and new mortgages.</p><div class="pf-grid" data-prefs-body><div class="ui-skel" style="min-height:46px"></div></div>' +
      '<button class="ui-btn primary" type="submit" style="justify-self:start">Save</button></form>' +
      '<div class="ui-card" style="margin-top:16px"><div class="pf-links">' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<button data-feedback>' + UI.icon('chat') + 'Submit feedback</button>' +
      '<button data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms, and your data</button>' +
      '<button data-signout-here>' + UI.icon('logout') + 'Sign out</button></div></div></div>';
    function themeBox() {
      var t = UI.theme();
      view.querySelector('[data-theme-box]').innerHTML = '<div class="ui-seg">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
        return '<button type="button" data-theme-pick="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
      }).join('') + '</div>';
    }
    themeBox();
    var prefsReady = GL.load().then(function (d) {
      var p = d.prefs;
      view.querySelector('[data-prefs-body]').innerHTML =
        '<label class="ui-field"><span>Currency</span><select name="currency">' + GL.opt([['CAD', 'Canadian dollar (CAD)'], ['USD', 'US dollar (USD)'], ['EUR', 'Euro (EUR)'], ['GBP', 'Pound sterling (GBP)'], ['AUD', 'Australian dollar (AUD)'], ['NZD', 'New Zealand dollar (NZD)'], ['CHF', 'Swiss franc (CHF)']], p.currency) + '</select></label>' +
        '<label class="ui-field"><span>Where your rentals are</span><select name="region">' + GL.opt(Object.keys(GL.REGIONS).map(function (k) { return [k, GL.REGIONS[k]]; }), p.region) + '</select></label>' +
        '<label class="ui-field"><span>Usual mortgage compounding</span><select name="compounding">' + GL.opt([['semiannual', 'Twice a year (Canadian fixed rate)'], ['monthly', 'Monthly (US, variable)']], p.compounding) + '</select></label>';
    });
    view.querySelector('[data-prefs]').addEventListener('submit', function (e) {
      e.preventDefault();
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('save_prefs', UI.formData(e.target))).then(function () { UI.toast('Saved', 'ok'); GL.load(true); });
    });
    view.addEventListener('click', function (e) {
      var t = e.target.closest('[data-theme-pick]');
      if (t) { UI.setTheme(t.getAttribute('data-theme-pick')); themeBox(); UI.renderChrome(); return; }
      if (e.target.closest('[data-reset]')) {
        UI.busy(e.target.closest('[data-reset]'), UI.auth('reset', { email: me.email })).then(function (r) { UI.toast(r.message, 'ok'); });
      }
      if (e.target.closest('[data-signout-here]')) UI.auth('logout');
    });
    view.querySelector('[data-name]').addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(e.target);
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('update_profile', v.name)).then(function (r) {
        UI.setMe(r.me); ctx.me = r.me; UI.toast('Saved', 'ok');
        view.querySelector('.pf-head h1').textContent = r.me.name;
      });
    });
    return prefsReady;
  });
})();

/* ===== property.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('property', { title: 'Property', auth: 'user' }, function (view, ctx) {
    var id = ctx.args[0], stopResize = null;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:260px"></div></div>';
    function draw() {
      var p = GL.prop(id);
      if (!p) { view.innerHTML = '<div class="ui-wrap"><div class="ui-empty">' + UI.icon('home') + '<h3>That property isn\'t here</h3><p>It may have been deleted.</p><a class="ui-btn" href="#home">Back home</a></div></div>'; return; }
      var m = GL.metrics(p), d = GL.data, kind = GL.KINDS.filter(function (k) { return k[0] === p.kind; })[0][1];
      var tens = d.tenancies.filter(function (t) { return t.property_id === id; });
      var led = d.ledger.filter(function (e) { return e.property_id === id; });
      var mort = m.plans;
      view.innerHTML = '<div class="ui-wrap">' +
        '<a href="#home" class="small" style="display:inline-flex;gap:6px;align-items:center;margin-bottom:12px">' + UI.icon('back') + 'All properties</a>' +
        (p.archived ? '<div class="gl-banner">' + UI.icon('info') + '<span style="flex:1">This property is archived: it\'s left out of your totals.</span><button class="ui-btn sm" data-unarchive>Bring it back</button></div>' : '') +
        '<div class="pp-head">' + GL.house({ door: p.door, kind: p.kind, glow: GL.glowFor(m.cashMonthly), smoke: m.cashMonthly > 0, size: 110 }) +
        '<div><div class="eyebrow">' + esc(kind) + ' · ' + UI.plural(p.units, 'unit') + (p.demo ? ' · sample' : '') + '</div><h1>' + esc(p.name) + '</h1><p class="muted" style="margin:4px 0 0">' + esc(p.address) +
        (p.purchase_date ? (p.address ? ' · ' : '') + 'bought ' + esc(UI.fmtDate(p.purchase_date, { month: 'long', year: 'numeric' })) + ' for ' + esc(GL.money(p.purchase_price)) : '') + '</p></div>' +
        '<div class="ui-row acts"><button class="ui-btn" data-edit>' + UI.icon('edit') + 'Edit</button><a class="ui-btn primary" href="#deal/' + esc(id) + '">' + UI.icon('chart') + 'Deal check</a></div></div>' +
        '<div class="gl-kpis">' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('home') + 'Worth today</div><div class="val num">' + esc(GL.money(m.value)) + '</div><div class="sub">' + (m.appreciationGain >= 0 ? '+' : '') + esc(GL.money(m.appreciationGain)) + ' since you bought</div></div>' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('percent') + 'Mortgage owed</div><div class="val num">' + esc(GL.money(m.balance)) + '</div><div class="sub">' + (mort.length ? esc(GL.money(m.mortMonthly)) + ' a month' : 'no mortgage added') + '</div></div>' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('key') + 'Equity</div><div class="val num">' + esc(GL.money(m.equity)) + '</div><div class="sub">' + (m.value ? Math.round(m.equity / m.value * 100) : 0) + '% of the value is yours</div></div>' +
          '<div class="gl-kpi"><div class="lbl">' + UI.icon('coins') + 'Cash flow</div><div class="val">' + GL.signed(m.cashMonthly) + '</div><div class="sub">a month: ' + esc(GL.money(m.rent)) + ' rent − ' + esc(GL.money(m.opexMonthly)) + ' costs − mortgage</div></div>' +
        '</div>' +
        '<div class="pp-grid"><div class="ui-stack">' +
          '<div class="ui-card"><div class="ui-row between"><h3 style="margin:0">Money in and out</h3><a class="small" href="#money/ledger/' + esc(id) + '">Full ledger ' + UI.icon('arrow') + '</a></div><p class="muted small">Last 12 months. The mortgage isn\'t in here: it\'s counted from your loan.</p><div data-chart></div>' +
            '<div class="pp-entries">' + led.slice(0, 6).map(function (e) {
              var c = GL.cat[e.category] || { label: e.category };
              return '<button data-entry="' + esc(e.id) + '"><span><b>' + esc(e.memo || c.label) + '</b><br><span class="c">' + esc(c.label) + ' · ' + esc(UI.fmtDate(e.date)) + '</span></span><span class="num ' + (e.kind === 'income' ? 'gl-pos' : '') + '" style="font-weight:800">' + (e.kind === 'income' ? '+' : '−') + esc(GL.money(e.amount, { cents: true })) + '</span></button>';
            }).join('') + '</div>' +
            '<div class="ui-row" style="margin-top:10px"><button class="ui-btn sm" data-add-entry="expense">' + UI.icon('plus') + 'Expense</button><button class="ui-btn sm" data-add-entry="income">' + UI.icon('plus') + 'Income</button></div></div>' +
          '<div class="ui-card"><div class="ui-row between"><h3 style="margin:0">Tenants</h3><button class="ui-btn sm primary" data-add-ten>' + UI.icon('plus') + 'Add tenant</button></div>' +
            (tens.length ? tens.map(function (t) {
              return '<div class="pp-ten"><div><h4>' + esc(t.tenant_name) + (t.unread ? ' <span class="ui-badge brand">' + t.unread + ' new</span>' : '') + (t.status === 'ended' ? ' <span class="ui-badge">Ended</span>' : '') + '</h4>' +
                '<div class="small muted">' + esc((t.unit ? t.unit + ' · ' : '') + GL.money(t.rent) + ' a month, due on day ' + t.due_day) + (t.open_tasks ? ' · ' + UI.plural(t.open_tasks, 'open request') : '') + '</div></div>' +
                '<div class="ui-row"><button class="ui-btn sm ghost" data-copy="' + esc(t.token) + '" title="Copy the tenant\'s private link">' + UI.icon('link') + '<span>Link</span></button><a class="ui-btn sm" href="#tenancy/' + esc(t.id) + '">' + UI.icon('chat') + 'Record</a></div></div>';
            }).join('') : '<p class="muted" style="margin-top:10px">No tenants yet. Adding one opens a permanent record and a private link for them.</p>') + '</div>' +
        '</div><div class="ui-stack">' +
          '<div class="ui-card pp-mort"><div class="ui-row between"><h3 style="margin:0">Mortgage</h3>' + (mort.length ? '' : '<button class="ui-btn sm primary" data-add-mort>' + UI.icon('plus') + 'Add</button>') + '</div>' +
            (mort.length ? mort.map(function (pl) {
              var mo = pl.m, bal = GL.balanceAt(pl, GL.today), yr = GL.paidBetween(pl, new Date(GL.today.getFullYear(), 0, 1), GL.today), ren = GL.renewal(pl);
              return '<dl><dt>Lender</dt><dd>' + esc(mo.lender || '·') + '</dd><dt>Rate</dt><dd>' + esc(mo.rate) + '%</dd><dt>Payment</dt><dd>' + esc(GL.money(pl.P, { cents: true })) + ' <span class="muted small">' + esc((GL.FREQ.filter(function (f) { return f[0] === mo.frequency; })[0] || ['', ''])[1].toLowerCase()) + '</span></dd>' +
                '<dt>Owed today</dt><dd>' + esc(GL.money(bal)) + '</dd><dt>Interest this year</dt><dd>' + esc(GL.money(yr.interest)) + ' <span class="muted small">claimable</span></dd>' +
                '<dt>Renews</dt><dd>' + esc(UI.fmtDate(GL.iso(ren))) + '</dd><dt>Paid off</dt><dd>' + esc(UI.fmtDate(GL.iso(GL.addMonths(pl.start, Math.round(pl.payoff * 12 / pl.n))), { month: 'short', year: 'numeric' })) + '</dd></dl>' +
                '<div class="ui-row" style="margin-top:12px"><button class="ui-btn sm" data-edit-mort="' + esc(mo.id) + '">' + UI.icon('edit') + 'Edit</button><a class="ui-btn sm ghost" href="#deal/' + esc(id) + '/mortgage">Calculator ' + UI.icon('arrow') + '</a></div>';
            }).join('<hr style="border:0;border-top:1px solid var(--c-line);margin:16px 0">') + '<button class="ui-btn sm ghost" data-add-mort style="margin-top:8px">' + UI.icon('plus') + 'Another loan</button>'
              : '<p class="muted" style="margin-top:10px">Add your mortgage to see your real cash flow, equity, and the interest you can claim.</p>') + '</div>' +
          (p.notes ? '<div class="ui-card"><h3>Notes</h3><p class="muted" style="white-space:pre-wrap;margin:0">' + esc(p.notes) + '</p></div>' : '') +
          '<div class="ui-card"><h3>Keep or let go</h3><p class="muted small">Archive a property you sold: it leaves your totals, its records stay.</p><div class="ui-row">' +
            (p.archived ? '<button class="ui-btn sm" data-unarchive>Unarchive</button>' : '<button class="ui-btn sm" data-archive>' + UI.icon('inbox') + 'Archive</button>') +
            '<button class="ui-btn sm danger" data-delete>' + UI.icon('trash') + 'Delete</button></div></div>' +
        '</div></div></div>';
      chart(led);
    }
    function chart(led) {
      var box = view.querySelector('[data-chart]'); if (!box) return;
      var months = [], inc = [], out = [];
      for (var i = 11; i >= 0; i--) months.push(GL.ym(GL.addMonths(GL.today, -i)));
      months.forEach(function (ym) {
        var a = 0, b = 0;
        led.forEach(function (e) { if (e.date.slice(0, 7) === ym) { if (e.kind === 'income') a += e.amount; else b += e.amount; } });
        inc.push(a); out.push(b);
      });
      GL.barChart(box, { title: 'Money in and out by month', labels: months.map(function (m) { return GL.monthName(m, true); }), tipLabels: months.map(function (m) { return GL.monthName(m); }),
        series: [{ label: 'Money in', color: 'var(--gl-s1)', values: inc }, { label: 'Money out', color: 'var(--gl-s2)', values: out }], height: 200 });
    }
    function reload() { return GL.load().then(draw); }
    view.addEventListener('click', function (e) {
      var p = GL.prop(id), t;
      if (e.target.closest('[data-edit]')) GL.forms.property(p, function () { UI.toast('Saved', 'ok'); reload(); });
      else if (e.target.closest('[data-add-mort]')) GL.forms.mortgage(null, id, function () { UI.toast('Mortgage saved', 'ok'); reload(); });
      else if ((t = e.target.closest('[data-edit-mort]'))) GL.forms.mortgage(GL.data.mortgages.filter(function (m) { return m.id === t.getAttribute('data-edit-mort'); })[0], id, function () { reload(); });
      else if (e.target.closest('[data-add-ten]')) GL.forms.tenancy(null, id, function (r) { UI.toast('Record opened', 'ok'); UI.go('tenancy', r.tenancy.id, 'share'); });
      else if ((t = e.target.closest('[data-add-entry]'))) GL.forms.entry(null, { property_id: id, kind: t.getAttribute('data-add-entry'), category: t.getAttribute('data-add-entry') === 'income' ? 'rent' : 'repairs' }, function () { UI.toast('Saved', 'ok'); reload(); });
      else if ((t = e.target.closest('[data-entry]'))) GL.forms.entry(GL.data.ledger.filter(function (x) { return x.id === t.getAttribute('data-entry'); })[0], null, function () { reload(); });
      else if ((t = e.target.closest('[data-copy]'))) GL.copy(GL.tenantLink(t.getAttribute('data-copy')));
      else if (e.target.closest('[data-archive]')) UI.api('archive_property', id, true).then(function () { UI.toast('Archived', 'ok'); reload(); });
      else if (e.target.closest('[data-unarchive]')) UI.api('archive_property', id, false).then(function () { UI.toast('Back in your totals', 'ok'); reload(); });
      else if (e.target.closest('[data-delete]')) UI.confirm({ title: 'Delete ' + p.name + '?', text: 'Its mortgage and ledger entries are deleted too. A property with tenancy records can only be archived.', ok: 'Delete', danger: true })
        .then(function (y) { if (y) UI.api('delete_property', id).then(function () { UI.toast('Deleted'); UI.go('home'); }); });
    });
    stopResize = GL.onResize(function () { chart(GL.data.ledger.filter(function (e) { return e.property_id === id; })); });
    return { ready: reload(), destroy: function () { stopResize && stopResize(); } };
  });
})();

/* ===== t.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('t', { title: 'Your home', chrome: false }, function (view, ctx) {
    var token = ctx.args[0] || '', D = null, timer = null, lastSeq = 0, tab = 'messages';
    var nameKey = 'tname.' + token.slice(0, 12);
    view.innerHTML = '<div class="tp-wrap"><div class="ui-skel" style="height:300px"></div></div>';
    function myName() { return UI.store.get(nameKey, '') || (D ? D.tenancy.tenant_name.split(' ')[0] : ''); }
    function top(title) { return '<div class="tp-top"><div class="in"><img src="_/theme/icon.svg" alt=""><b>' + esc(title) + '</b><span class="ui-spacer"></span><span class="small muted">Good Landlord</span></div></div>'; }
    function bad(msg) {
      view.innerHTML = top('Good Landlord') + '<div class="tp-wrap"><div class="ui-empty" style="margin-top:30px">' + UI.icon('link') + '<h3>This link doesn\'t open a home</h3><p>' + esc(msg) + '</p><a class="ui-btn" href="#landing">What is Good Landlord?</a></div></div>';
    }
    function draw(d) {
      D = d; GL.cur = d.currency || 'CAD';
      lastSeq = d.entries.length ? d.entries[d.entries.length - 1].seq : 0;
      var t = d.tenancy, first = t.tenant_name.split(' ')[0], badges = GL.badges(d.stats);
      var open = d.tasks.filter(function (k) { return k.status !== 'done' && k.status !== 'declined'; }), closed = d.tasks.filter(function (k) { return open.indexOf(k) < 0; });
      var toConfirm = d.tasks.filter(function (k) { return k.status === 'done' && !k.confirmed_at; });
      view.innerHTML = top(d.property.name + (t.unit ? ' · ' + t.unit : '')) + '<div class="tp-wrap">' +
        (t.demo ? '<div class="gl-banner tp-demo">' + UI.icon('sparkle') + '<span style="flex:1;min-width:200px">This is a <b>demo</b> of a tenant\'s page: the people are fictional. Try writing a message or asking for a repair.</span><a class="ui-btn sm" href="#landing">About Good Landlord</a></div>' : '') +
        '<div class="tp-hero">' + GL.house({ door: d.property.door, glow: .9, smoke: true }) + '<div><div class="eyebrow">Your home record</div><h1>Hi ' + esc(first) + '</h1>' +
        '<p class="muted" style="margin:0">Your landlord is <b>' + esc(d.landlord_name) + '</b>. Write here or ask for repairs: everything is dated, kept for good, and nobody (not even your landlord) can edit or delete it.</p>' +
        (badges.length ? '<div class="tp-badges">' + badges.map(function (b) { return '<span>' + UI.icon(b[0]) + esc(b[1]) + '</span>'; }).join('') + '</div>' : '') + '</div></div>' +
        GL.sealBox(d.seal) +
        (toConfirm.length ? '<div class="gl-banner" style="margin-top:14px">' + UI.icon('check') + '<span style="flex:1;min-width:200px"><b>' + esc(d.landlord_name.split(' ')[0]) + ' marked "' + esc(toConfirm[0].title) + '" as done.</b> Is it fixed?</span><button class="ui-btn sm primary" data-task-id="' + esc(toConfirm[0].id) + '">Answer</button></div>' : '') +
        '<div class="tp-grid"><section class="ui-card"><div class="ui-row between"><h2 style="margin:0;font-size:1.3rem">Messages</h2><button class="ui-btn sm" data-ask>' + UI.icon('wrench') + 'Ask for a repair</button></div>' +
          '<div style="margin-top:12px" data-thread>' + (d.entries.length ? GL.thread(d.entries, 'tenant') : '') + '</div>' +
          '<form class="gl-compose" data-compose><textarea name="body" maxlength="4000" placeholder="Write to ' + esc(d.landlord_name.split(' ')[0]) + '…" required></textarea><button class="ui-btn primary" type="submit">' + UI.icon('send') + 'Send</button></form>' +
          '<div class="tp-name">Writing as <input type="text" data-name maxlength="60" value="' + esc(myName()) + '" aria-label="Your name"><span>· messages can\'t be deleted, so take a breath before sending.</span></div></section>' +
        '<aside class="tp-side"><div class="ui-card"><div class="ui-row between"><h3 style="margin:0">Repairs &amp; requests</h3><button class="ui-btn sm primary" data-ask>' + UI.icon('plus') + 'Ask</button></div>' +
          '<div class="tc-tasks" style="display:grid;gap:8px;margin-top:12px">' + (open.length ? open.map(function (k) { return GL.taskCard(k); }).join('') : '<p class="muted small" style="margin:0">Nothing open. If something needs fixing, ask here: the date you asked is recorded.</p>') + '</div>' +
          (closed.length ? '<details style="margin-top:10px"><summary class="small muted" style="cursor:pointer">' + UI.plural(closed.length, 'finished request') + '</summary><div style="display:grid;gap:8px;margin-top:8px">' + closed.map(function (k) { return GL.taskCard(k); }).join('') + '</div></details>' : '') + '</div>' +
          '<div class="ui-card"><h3>Your lease</h3><dl class="tp-facts"><dt>Rent</dt><dd>' + esc(GL.money(t.rent, { cents: true })) + ' / month</dd><dt>Due</dt><dd>Day ' + t.due_day + ' of the month</dd>' +
            '<dt>Since</dt><dd>' + esc(UI.fmtDate(t.start_date)) + '</dd>' + (t.end_date ? '<dt>Until</dt><dd>' + esc(UI.fmtDate(t.end_date)) + '</dd>' : '') +
            (t.deposit ? '<dt>Deposit</dt><dd>' + esc(GL.money(t.deposit)) + '</dd>' : '') + '<dt>Address</dt><dd>' + esc(d.property.address || d.property.name) + '</dd></dl>' +
            (d.rent_payments.length ? '<p class="small muted" style="margin:14px 0 0">Rent your landlord recorded as received</p><div class="tp-rec">' + d.rent_payments.slice(0, 12).map(function (r) {
              return '<div><span>' + esc(GL.monthName(r.month)) + '</span><b>' + esc(GL.money(r.amount, { cents: true })) + ' · ' + esc(UI.fmtDate(r.date, { day: 'numeric', month: 'short' })) + '</b></div>'; }).join('') + '</div>' : '') + '</div>' +
          '<div class="ui-card"><h3>Keep a copy</h3><p class="muted small">Download the whole record with its dates and seal, for your files or a rental board.</p><button class="ui-btn sm" data-download>' + UI.icon('download') + 'Download the record</button></div>' +
        '</aside></div>' +
        '<div class="tp-foot">This page is private to your home: keep the link to yourself. · <button data-lk-open="overview">Privacy &amp; Terms</button> · <button data-feedback>Submit feedback</button></div></div>';
      var th = view.querySelector('[data-thread]');
      var lastEl = th.querySelector('.gl-thread > :last-child');
      if (lastEl && ctx.args[1] !== 'top') setTimeout(function () { if (view.isConnected && lastEl.getBoundingClientRect().top > innerHeight) lastEl.scrollIntoView({ block: 'nearest' }); }, 30);
    }
    function load(quiet) {
      return (quiet ? UI.apiQuiet : UI.api)('tenant_view', token, true).then(draw, function (e) { if (e.expected || e.uiApi) bad(e.message); else throw e; });
    }
    function poll() {
      UI.apiQuiet('tenant_view', token, true).then(function (d) {
        var seq = d.entries.length ? d.entries[d.entries.length - 1].seq : 0;
        if (seq === lastSeq || document.querySelector('.ui-modal-wrap')) return;
        var ta = view.querySelector('[data-compose] textarea'), draft = ta ? ta.value : '';
        draw(d); var ta2 = view.querySelector('[data-compose] textarea'); if (ta2) ta2.value = draft;
      }, function () {});
    }
    view.addEventListener('change', function (e) { if (e.target.matches('[data-name]')) UI.store.set(nameKey, e.target.value.trim()); });
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-compose]')) return;
      e.preventDefault();
      var f = e.target;
      UI.busy(f.querySelector('[type=submit]'), UI.api('tenant_post', token, myName(), f.body.value)).then(function () { UI.toast('Sent and sealed', 'ok'); return load(true); });
    });
    view.addEventListener('click', function (e) {
      var t;
      if (e.target.closest('[data-ask]')) GL.newTaskForm({ send: function (v) { return UI.api('tenant_request', token, myName(), v.title, v.details, v.category, v.priority); },
        done: function () { UI.toast('Request sent. The date is on record.', 'ok'); load(true); } });
      else if (e.target.closest('[data-download]')) GL.download('my-home-record-' + GL.iso(new Date()) + '.txt', GL.recordText({ property: D.property, unit: D.tenancy.unit, tenant: D.tenancy.tenant_name, landlord: D.landlord_name, seal: D.seal, entries: D.entries, tasks: D.tasks }));
      else if ((t = e.target.closest('[data-verify]'))) UI.busy(t, UI.apiQuiet('tenant_view', token, false)).then(function (d) { UI.toast(d.seal.intact ? 'Checked: all ' + d.seal.count + ' entries are intact.' : 'The seal is broken!', d.seal.intact ? 'ok' : 'error'); });
      else if ((t = e.target.closest('[data-task-id]')) || (t = e.target.closest('[data-task]'))) {
        var tid = t.getAttribute('data-task-id') || t.getAttribute('data-task'), k = D.tasks.filter(function (x) { return x.id === tid; })[0];
        if (k) GL.taskModal(Object.assign({}, k, { where: '' }), { tenant: true, token: token, name: myName(), done: function () { load(true); } });
      }
    });
    timer = setInterval(poll, 30000);
    return { ready: load(), destroy: function () { clearInterval(timer); } };
  });
})();

/* ===== tenancy.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('tenancy', { title: 'Tenancy record', auth: 'user' }, function (view, ctx) {
    var id = ctx.args[0], D = null, timer = null, lastSeq = 0;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:320px"></div></div>';
    function draw(d) {
      D = d; GL.cur = d.prefs.currency || GL.cur;
      var t = d.tenancy, open = d.tasks.filter(function (k) { return k.status !== 'done' && k.status !== 'declined'; }), closed = d.tasks.filter(function (k) { return open.indexOf(k) < 0; });
      lastSeq = d.entries.length ? d.entries[d.entries.length - 1].seq : 0;
      view.innerHTML = '<div class="ui-wrap"><a href="#tenants" class="small" style="display:inline-flex;gap:6px;align-items:center;margin-bottom:12px">' + UI.icon('back') + 'All tenants</a>' +
        '<div class="tc-head"><div><div class="eyebrow">' + esc(d.property.name + (t.unit ? ' · ' + t.unit : '')) + (t.demo ? ' · sample' : '') + '</div><h1>' + esc(t.tenant_name) + (t.status === 'ended' ? ' <span class="ui-badge">Ended</span>' : '') + '</h1></div>' +
        '<div class="ui-row"><button class="ui-btn primary" data-share>' + UI.icon('link') + 'Tenant\'s link</button><button class="ui-btn" data-download>' + UI.icon('download') + 'Download</button></div></div>' +
        GL.sealBox(d.seal) +
        '<div class="tc-grid"><section class="ui-card"><div class="tc-thread" data-thread>' + GL.thread(d.entries, 'landlord') + '</div>' +
        '<form class="gl-compose" data-compose><textarea name="body" maxlength="4000" placeholder="Write to ' + esc(t.tenant_name.split(' ')[0]) + '… (kept for good, can\'t be deleted)" required></textarea><button class="ui-btn primary" type="submit">' + UI.icon('send') + 'Send</button></form></section>' +
        '<aside class="tc-side"><div class="ui-card"><div class="ui-row between"><h3 style="margin:0">Requests</h3><button class="ui-btn sm" data-new-task>' + UI.icon('plus') + 'Task</button></div>' +
          '<div class="tc-tasks" style="margin-top:12px">' + (open.length ? open.map(function (k) { return GL.taskCard(k); }).join('') : '<p class="muted small" style="margin:0">No open requests.</p>') + '</div>' +
          (closed.length ? '<details style="margin-top:10px"><summary class="small muted" style="cursor:pointer">' + UI.plural(closed.length, 'finished request') + '</summary><div class="tc-tasks" style="margin-top:8px">' + closed.map(function (k) { return GL.taskCard(k); }).join('') + '</div></details>' : '') + '</div>' +
          '<div class="ui-card"><h3>Lease</h3><dl class="tc-facts"><dt>Rent</dt><dd>' + esc(GL.money(t.rent, { cents: true })) + ' / month</dd><dt>Due</dt><dd>Day ' + t.due_day + '</dd>' +
            '<dt>Started</dt><dd>' + esc(UI.fmtDate(t.start_date)) + '</dd><dt>Ends</dt><dd>' + (t.end_date ? esc(UI.fmtDate(t.end_date)) : 'Open-ended') + '</dd>' +
            (t.deposit ? '<dt>Deposit held</dt><dd>' + esc(GL.money(t.deposit)) + '</dd>' : '') + (t.tenant_email ? '<dt>Email</dt><dd style="overflow-wrap:anywhere">' + esc(t.tenant_email) + '</dd>' : '') +
            '<dt>Tenant\'s last visit</dt><dd>' + (t.tenant_last_visit ? esc(UI.ago(t.tenant_last_visit)) : 'Not yet') + '</dd></dl>' +
            (d.rent_payments.length ? '<p class="small muted" style="margin:14px 0 6px">Rent received</p><div class="tc-rent">' + d.rent_payments.slice(0, 12).map(function (r) { return '<span title="' + esc(GL.money(r.amount)) + ' on ' + esc(r.date) + '">' + esc(GL.monthName(r.month, true)) + ' ' + r.month.slice(2, 4) + '</span>'; }).join('') + '</div>' : '') +
            '<div class="ui-row" style="margin-top:14px"><button class="ui-btn sm" data-edit>' + UI.icon('edit') + 'Edit</button>' +
            (t.status === 'ended' ? '<button class="ui-btn sm" data-reopen>Reopen</button>' : '<button class="ui-btn sm" data-end>' + UI.icon('key') + 'End tenancy</button>') +
            (t.entries <= 1 && !t.tenant_last_visit ? '<button class="ui-btn sm danger" data-delete>' + UI.icon('trash') + 'Delete</button>' : '') + '</div></div>' +
        '</aside></div></div>';
      var th = view.querySelector('[data-thread]'); th.scrollTop = th.scrollHeight;
      if (ctx.args[1] === 'share') { ctx.args[1] = null; share(); }
    }
    function share() {
      var link = GL.tenantLink(D.tenancy.token), first = D.tenancy.tenant_name.split(' ')[0];
      var text = 'Hi ' + first + ', here is your private page for ' + D.property.name + (D.tenancy.unit ? ' (' + D.tenancy.unit + ')' : '') + ': ' + link + '\nWrite to me or ask for repairs there. Everything is kept for both of us and nobody can delete it.';
      var m = UI.modal('<h2>' + esc(first) + '\'s private link</h2><p class="muted">No account needed: whoever has this link can read and write in this record, so send it only to your tenant.</p>' +
        '<div class="gl-link"><input type="text" readonly value="' + esc(link) + '" data-link><button class="ui-btn primary" data-copy-link>' + UI.icon('copy') + 'Copy</button></div>' +
        '<p class="small muted" style="margin:14px 0 6px">A message you can paste into a text or email:</p><textarea readonly data-msg style="min-height:96px">' + esc(text) + '</textarea>' +
        '<div class="ui-row" style="margin-top:10px"><button class="ui-btn sm" data-copy-msg>' + UI.icon('copy') + 'Copy message</button>' +
        (D.tenancy.tenant_email ? '<a class="ui-btn sm" href="mailto:' + esc(D.tenancy.tenant_email) + '?subject=' + encodeURIComponent('Your page for ' + D.property.name) + '&body=' + encodeURIComponent(text) + '">' + UI.icon('mail') + 'Email it</a>' : '') +
        '<span class="ui-spacer"></span><button class="ui-btn sm danger" data-reset>' + UI.icon('refresh') + 'Make a new link</button></div>' +
        '<p class="ui-hint">Making a new link stops the old one working (handy if it was shared by mistake). The record itself stays.</p>');
      m.el.querySelector('[data-copy-link]').onclick = function () { m.el.querySelector('[data-link]').select(); GL.copy(link); };
      m.el.querySelector('[data-copy-msg]').onclick = function () { m.el.querySelector('[data-msg]').select(); GL.copy(text); };
      m.el.querySelector('[data-reset]').onclick = function () {
        UI.confirm({ title: 'Make a new link?', text: 'The old link stops working right away. You\'ll need to send the new one to your tenant.', ok: 'New link', danger: true }).then(function (y) {
          if (y) UI.api('reset_link', id).then(function () { m.close(); UI.toast('New link made', 'ok'); load().then(share); });
        });
      };
    }
    function load(quiet) { return (quiet ? UI.apiQuiet : UI.api)('get_tenancy', id).then(draw); }
    function poll() {
      UI.apiQuiet('get_tenancy', id).then(function (d) {
        var seq = d.entries.length ? d.entries[d.entries.length - 1].seq : 0;
        if (seq === lastSeq) return;
        var ta = view.querySelector('[data-compose] textarea'), draft = ta ? ta.value : '';
        if (document.querySelector('.ui-modal-wrap')) return;
        draw(d); var ta2 = view.querySelector('[data-compose] textarea'); if (ta2) ta2.value = draft;
      }, function () {});
    }
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-compose]')) return;
      e.preventDefault();
      var f = e.target, body = f.body.value;
      UI.busy(f.querySelector('[type=submit]'), UI.api('landlord_post', id, body)).then(function () { return load(true); });
    });
    view.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && e.target.closest('[data-compose]')) { e.preventDefault(); e.target.closest('form').requestSubmit(); }
    });
    view.addEventListener('click', function (e) {
      var t;
      if (e.target.closest('[data-share]')) share();
      else if (e.target.closest('[data-download]')) {
        GL.download('record-' + D.tenancy.tenant_name.replace(/[^a-z0-9]+/gi, '-').toLowerCase() + '-' + GL.iso(new Date()) + '.txt',
          GL.recordText({ property: D.property, unit: D.tenancy.unit, tenant: D.tenancy.tenant_name, landlord: D.landlord_name, seal: D.seal, entries: D.entries, tasks: D.tasks }));
      }
      else if ((t = e.target.closest('[data-verify]'))) UI.busy(t, UI.api('verify_record', id)).then(function (r) { UI.toast(r.seal.intact ? 'Checked: all ' + r.seal.count + ' entries are intact.' : 'The seal is broken!', r.seal.intact ? 'ok' : 'error'); D.seal = r.seal; });
      else if (e.target.closest('[data-new-task]')) GL.newTaskForm({ title: 'Add a task', lead: 'For work you plan yourself (inspections, servicing). Your tenant sees it in their record.', ok: 'Add task',
        send: function (v) { return UI.api('landlord_new_task', id, v.title, v.details, v.category, v.priority); }, done: function () { UI.toast('Task added', 'ok'); load(true); } });
      else if ((t = e.target.closest('[data-task-id]')) || (t = e.target.closest('[data-task]'))) {
        var tid = t.getAttribute('data-task-id') || t.getAttribute('data-task'), k = D.tasks.filter(function (x) { return x.id === tid; })[0];
        if (k) GL.taskModal(Object.assign({ where: '' }, k), { landlord: true, done: function () { load(true); } });
      }
      else if (e.target.closest('[data-edit]')) GL.load().then(function () { GL.forms.tenancy(D.tenancy, null, function () { UI.toast('Saved', 'ok'); load(true); }); });
      else if (e.target.closest('[data-end]')) UI.confirm({ title: 'End this tenancy?', text: 'It leaves the rent roll. The record stays readable for both of you, and the tenant can still write in it.', ok: 'End tenancy' })
        .then(function (y) { if (y) UI.api('end_tenancy', id, null).then(function () { load(true); }); });
      else if (e.target.closest('[data-reopen]')) UI.api('reopen_tenancy', id).then(function () { load(true); });
      else if (e.target.closest('[data-delete]')) UI.confirm({ title: 'Delete this record?', text: 'Only possible because nobody has used it yet.', ok: 'Delete', danger: true })
        .then(function (y) { if (y) UI.api('delete_tenancy', id).then(function () { UI.go('tenants'); }); });
    });
    timer = setInterval(poll, 30000);
    return { ready: load(), destroy: function () { clearInterval(timer); } };
  });
})();

/* ===== tenants.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('tenants', { title: 'Tenants', nav: 'Tenants', icon: 'users', auth: 'user', order: 40 }, function (view, ctx) {
    var tab = ctx.args[0] === 'requests' ? 'requests' : 'list';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:240px"></div></div>';
    function frame(inner, d) {
      var openN = d.tasks.filter(function (k) { return k.status !== 'done' && k.status !== 'declined'; }).length;
      var unread = d.tenancies.reduce(function (s, t) { return s + t.unread; }, 0);
      return '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Tenants</h1><p class="muted">Every conversation and request, kept for good and sealed against changes.</p></div>' +
        '<button class="ui-btn primary" data-add-ten>' + UI.icon('plus') + 'Add tenant</button></div>' +
        '<nav class="ui-tabs"><a href="#tenants" class="' + (tab === 'list' ? 'on' : '') + '">' + UI.icon('users') + 'Tenancies' + (unread ? ' <span class="count">' + unread + ' new</span>' : '') + '</a>' +
        '<a href="#tenants/requests" class="' + (tab === 'requests' ? 'on' : '') + '">' + UI.icon('wrench') + 'Requests' + (openN ? ' <span class="count">' + openN + ' open</span>' : '') + '</a></nav>' + inner + '</div>';
    }
    function list(d) {
      if (!d.tenancies.length) return '<div class="ui-empty">' + UI.icon('users') + '<h3>No tenants yet</h3><p>Add a tenant to open a shared, permanent record and get their private link.</p>' +
        (d.properties.length ? '<button class="ui-btn primary" data-add-ten>' + UI.icon('plus') + 'Add a tenant</button>' : '<a class="ui-btn primary" href="#home">Add a property first</a>') + '</div>';
      return d.properties.map(function (p) {
        var ts = d.tenancies.filter(function (t) { return t.property_id === p.id; });
        if (!ts.length) return '';
        ts.sort(function (a, b) { return (a.status === 'ended') - (b.status === 'ended'); });
        return '<div class="tn-group"><h3>' + GL.house({ door: p.door, kind: p.kind, size: 30 }) + esc(p.name) + '</h3><div class="tn-list">' + ts.map(function (t) {
          var lm = t.last_message;
          return '<div class="ui-card tn-card"' + (t.status === 'ended' ? ' style="opacity:.75"' : '') + '><div class="who"><span class="ui-avatar">' + esc(UI.initials(t.tenant_name)) + '</span><div style="flex:1;min-width:0"><h4>' + esc(t.tenant_name) + '</h4>' +
            '<div class="small muted">' + esc((t.unit ? t.unit + ' · ' : '') + GL.money(t.rent) + '/month') + '</div></div>' +
            (t.unread ? '<span class="ui-badge brand">' + t.unread + ' new</span>' : '') + (t.status === 'ended' ? '<span class="ui-badge">Ended</span>' : '') + '</div>' +
            (lm ? '<div class="last"><b>' + esc(lm.author_kind === 'landlord' ? 'You' : lm.author_name) + ':</b> ' + esc(lm.body) + ' <span class="faint">· ' + esc(UI.ago(lm.created)) + '</span></div>' : '<div class="last">No messages yet.' + (t.tenant_last_visit ? '' : ' Send them their link!') + '</div>') +
            '<div class="ui-row small muted">' + (t.open_tasks ? '<span class="ui-badge warn">' + UI.plural(t.open_tasks, 'open request') + '</span>' : '<span class="ui-badge good">No open requests</span>') +
            '<span>' + UI.plural(t.entries, 'entry', 'entries') + '</span>' + (t.tenant_last_visit ? '<span>· tenant visited ' + esc(UI.ago(t.tenant_last_visit)) + '</span>' : '<span>· link not opened yet</span>') + '</div>' +
            '<div class="ui-row"><a class="ui-btn primary sm" href="#tenancy/' + esc(t.id) + '">' + UI.icon('chat') + 'Open record</a><button class="ui-btn sm" data-copy="' + esc(t.token) + '">' + UI.icon('link') + 'Copy link</button></div></div>';
        }).join('') + '</div></div>';
      }).join('');
    }
    function board(d) {
      var monthAgo = new Date(GL.today.getTime() - 31 * 864e5);
      var cols = [['requested', 'New'], ['acknowledged', 'Seen'], ['scheduled', 'Scheduled'], ['in_progress', 'In progress'], ['done', 'Done (30 days)']];
      var st = d.stats, badges = GL.badges(st);
      return '<div class="tn-stats">' + (badges.length ? badges.map(function (b) { return '<span class="ui-badge brand">' + UI.icon(b[0]) + esc(b[1]) + '</span>'; }).join('') : '<span class="muted small">Your response badges appear once tenants send requests.</span>') + '</div>' +
        '<div class="tn-board">' + cols.map(function (c) {
          var ks = d.tasks.filter(function (k) { return k.status === c[0] && (c[0] !== 'done' || GL.d(k.done_at) > monthAgo); });
          if (c[0] === 'requested') ks.sort(function (a, b) { return (b.priority === 'urgent') - (a.priority === 'urgent'); });
          return '<div class="tn-col"><h4><span>' + c[1] + '</span><span>' + ks.length + '</span></h4>' + (ks.length ? ks.map(function (k) { return GL.taskCard(k, true); }).join('') : '<div class="empty">Nothing here.</div>') + '</div>';
        }).join('') + '</div><p class="ui-hint">Tap a request to move it along. Every move is written into that tenant\'s record with the date.</p>';
    }
    function draw(d) { view.innerHTML = frame(tab === 'list' ? list(d) : board(d), d); }
    function load() { return GL.load().then(draw); }
    view.addEventListener('click', function (e) {
      var t;
      if (e.target.closest('[data-add-ten]')) {
        if (!GL.activeProps().length) { UI.toast('Add a property first.'); return; }
        GL.forms.tenancy(null, GL.activeProps()[0].id, function (r) { UI.toast('Record opened', 'ok'); UI.go('tenancy', r.tenancy.id, 'share'); }); return;
      }
      if ((t = e.target.closest('[data-copy]'))) { GL.copy(GL.tenantLink(t.getAttribute('data-copy'))); return; }
      if ((t = e.target.closest('[data-task-id]'))) {
        var k = GL.data.tasks.filter(function (x) { return x.id === t.getAttribute('data-task-id'); })[0];
        GL.taskModal(k, { landlord: true, done: load });
      }
    });
    return load();
  });
})();
