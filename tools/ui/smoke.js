/* Smoke test (tools/ui_test.py runs it at 1280 px and at 390 px): every page address opens without errors, is not
   empty and doesn't scroll sideways, signed out (landing, the tenant demo, a bad tenant link, sign in / up), then as a
   new landlord (empty home, then the sample portfolio: home, a property, money tabs, deal check, tenants, a record,
   profile; plus the main dialogs open and close), then as admin (every Admin tab).
   Python/JS errors are caught by ui_test.py from the browser log. Resolves to {ok, log}. */
(async function () {
  const log = [], bad = [];
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 20000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s) => document.querySelector(s), $$ = (s) => Array.from(document.querySelectorAll(s));
  const errs = [];
  window.addEventListener('error', (e) => errs.push(String(e.message || e)));
  const visible = (el) => !!el && el.getClientRects().length > 0;
  function type(input, value) {
    input.focus(); input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function button(re, root) { return $$((root || '') + ' button').find((b) => re.test(b.textContent.trim()) && visible(b)); }
  function check(name, expect) {
    const main = $('.ui-main');
    const text = main ? main.innerText.trim() : '';
    const w = document.documentElement.scrollWidth, vw = screen.width <= 500 ? screen.width : window.innerWidth;
    const problems = [];
    if (text.length < 40) problems.push('empty page');
    if (expect && !new RegExp(expect.source, 'i').test(text)) problems.push('missing ' + expect);
    if (w > vw + 1) {
      const wide = $$('body *').filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.right > vw + 1; })
        .slice(0, 3).map((e) => e.tagName.toLowerCase() + '.' + String(e.className).split(' ').slice(0, 2).join('.'));
      problems.push('scrolls sideways (' + w + ' > ' + vw + ') ' + wide.join(' '));
    }
    if (errs.length) problems.push('errors: ' + errs.splice(0).join(' / '));
    if (problems.length) bad.push(name + ': ' + problems.join('; '));
    log.push((problems.length ? 'BAD  ' : 'ok   ') + name);
  }
  async function open(hash, expect) {
    if (location.hash !== hash) window.UI_READY = false;
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash, hash, 30000);
    await sleep(700);
    check(hash, expect);
  }
  async function dialog(name, opener, expect) {
    opener.click();
    const dlg = await until(() => $$('.modal, .anvil-modal').find((m) => visible(m) && m.innerText.trim().length > 10), 'dialog ' + name, 15000);
    await sleep(400);
    const text = dlg.innerText;
    const problems = [];
    if (expect && !expect.test(text)) problems.push('missing ' + expect);
    if (errs.length) problems.push('errors: ' + errs.splice(0).join(' / '));
    if (problems.length) bad.push('dialog ' + name + ': ' + problems.join('; '));
    log.push((problems.length ? 'BAD  ' : 'ok   ') + 'dialog ' + name);
    const close = $$('.modal button, .anvil-modal button').find((b) => /^(Cancel|Close)$/.test(b.textContent.trim()) && visible(b));
    if (close) close.click();
    await until(() => !$$('.modal, .anvil-modal').some(visible), 'dialog closed', 10000);
    await sleep(300);
  }
  async function signUp(name, email, password) {
    location.hash = '#auth/signup';
    await until(() => window.UI_READY && $$('.au-card input').length >= 3, 'sign-up form');
    await sleep(400);
    const inputs = $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]');
    type(inputs[0], name); type(inputs[1], email); type(inputs[2], password);
    const tick = $('.au-card input[type=checkbox]'); if (tick && !tick.checked) tick.click();
    button(/Create account/, '.au-card .anvil-role-btn-block').click();
    const end = Date.now() + 30000;
    while (Date.now() < end) {
      if (location.hash === '#home' && window.UI_READY) return true;
      const msg = $('.au-card .anvil-role-msg-error');
      if (msg && visible(msg) && msg.textContent.trim()) { log.push('sign-up said: ' + msg.textContent.trim()); return false; }
      await sleep(200);
    }
    log.push('sign-up: still on ' + location.hash);
    return false;
  }
  async function signIn(email, password) {
    location.hash = '#auth';
    await until(() => window.UI_READY && $$('.au-card input[type=password]').length, 'sign-in form');
    await sleep(400);
    type($('.au-card input[type=email]'), email); type($('.au-card input[type=password]'), password);
    button(/Sign in/, '.au-card .anvil-role-btn-block').click();
    await until(() => location.hash === '#home' && window.UI_READY, 'signed in as ' + email, 30000);
  }
  async function signOut() {
    $('.anvil-role-avatar button').click();
    await sleep(300);
    button(/Sign out/, '.ui-menu').click();
    await until(() => {
      const a = $('.anvil-role-avatar button');
      return location.hash === '#landing' && window.UI_READY && (!a || !visible(a));
    }, 'signed out');
  }
  try {
    // ---- signed out
    await open('#landing', /Keep your word/);
    await open('#t/demo-upstairs', /Your landlord is/);
    await open('#t/no-such-link', /doesn't open a home/);
    await open('#auth', /Sign in/);
    await open('#auth/signup', /Create account/);

    // ---- a new landlord: empty home, then the sample portfolio
    const ok = await signUp('Smoke Landlord', 'smoke' + Date.now() + '@example.com', 'Gl-' + Math.random().toString(36).slice(2) + '-Kq7');
    if (!ok) throw new Error('sign-up failed');
    await sleep(600);
    check('#home (empty)', /first rental/);
    button(/Explore with a sample/).click();
    await until(() => $$('.hm-street a.h').length >= 2 && window.UI_READY, 'the sample street', 40000);
    await sleep(800);
    check('#home (sample)', /Needs your attention/);
    const propHref = $('.hm-street a.h').getAttribute('href');
    const propId = decodeURIComponent(propHref.split('/')[1]);
    await open(propHref, /Money in and out/);
    await dialog('edit property', button(/^Edit$/), /Door colour/);
    await dialog('add expense', button(/^Expense$/), /Add to the ledger/);
    await open('#money/ledger', /Money in/);
    await open('#money/rent', /collected/);
    await open('#money/tax', /Claimable expenses/);
    await open('#deal', /If you sold today/);
    await open('#deal/' + encodeURIComponent(propId) + '/mortgage', /Quick ratios/);
    await open('#deal/calculator', /calculator/);
    await open('#tenants', /Open record/);
    const recHref = $('.tn-card a[href^="#tenancy/"]').getAttribute('href');
    await open('#tenants/requests', /In progress/);
    await open(recHref, /Lease/);
    const card = $('.tc-side .gl-task');
    if (card) await dialog('task', card, /Asked/); else bad.push('no task card on the record');
    await dialog('tenant link', button(/Tenant's link/), /private link/);
    await open('#profile', /Money and taxes/);
    await open('#landing', /Open the app/);
    await signOut();

    // ---- admin (ADMIN_EMAILS in Accounts.py): sign up the first time, sign in after that
    const adminPw = 'Gl-smoke-adm-93Kx-7q';
    if (!(await signUp('Admin Tester', 'arkulinskis@gmail.com', adminPw))) await signIn('arkulinskis@gmail.com', adminPw);
    for (const t of ['overview', 'feedback', 'users', 'demo']) await open('#admin/' + t, /Admin/);
    await signOut();
    log.push(bad.length ? 'PROBLEMS: ' + bad.join(' | ') : 'PASSED');
    return { ok: !bad.length, log: log };
  } catch (e) {
    log.push(String(e && e.message || e));
    if (bad.length) log.push('PROBLEMS: ' + bad.join(' | '));
    return { ok: false, log: log };
  }
})();
