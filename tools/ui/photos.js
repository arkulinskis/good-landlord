/* Photo attachments, end to end (python -I tools/ui_test.py --only photos.js; needs the App Secret cloudflare_photos,
   which ui_test.py passes from ~/.goodlandlord/cloudflare_photos.txt, so the photos really go to the Cloudflare Worker).
   A new landlord adds a property + tenancy and a task with a photo; the tenant (private link) asks for a repair with
   photos (removing one preview on the way), opens it, adds one more; every photo must load back through its signed
   link and the seal must stay intact. Test files are made in the page (GLPhotos.testFiles), not the system picker. */
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
  function btn(re, root) { const b = button(re, root); if (!b) throw new Error('no button ' + re + ' on ' + location.hash + ': ' + $$('button').filter(visible).map((x) => x.textContent.trim()).filter(Boolean).slice(0, 12).join(' | ')); return b; }
  function mfind(re) { const m = modal(); return m && Array.from(m.querySelectorAll('button')).find((b) => re.test(b.textContent.trim()) && visible(b)); }
  function mbtn(re) { const b = mfind(re); if (!b) throw new Error('no dialog button ' + re); return b; }
  // ---- photo helpers
  async function makeFiles(n, hue) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const c = document.createElement('canvas'); c.width = 1200; c.height = 900;
      const g = c.getContext('2d');
      g.fillStyle = 'hsl(' + ((hue + i * 50) % 360) + ',55%,55%)'; g.fillRect(0, 0, 1200, 900);
      g.fillStyle = '#fff'; g.font = 'bold 120px sans-serif'; g.fillText('Photo ' + (i + 1), 300, 480);
      const b = await new Promise((r) => c.toBlob(r, 'image/jpeg', 0.9));
      out.push(new File([b], 'repair-' + i + '.jpg', { type: 'image/jpeg' }));
    }
    return out;
  }
  const modal = () => $$('.modal, .anvil-modal').find((m) => visible(m) && m.innerText.trim().length > 10);
  const thumbs = (root) => Array.from((root || document).querySelectorAll('.gl-ph img')).filter(visible);
  async function pick(root, n, hue) {
    window.GLPhotos.testFiles = await makeFiles(n, hue);
    const before = thumbs(root).length;
    btn(/^Add (more )?photos$/, '').click();
    await until(() => thumbs(root).length === before + n, n + ' preview(s)', 15000);
  }
  async function loaded(imgs, what) {
    await until(() => imgs.length && imgs.every((i) => i.complete && i.naturalWidth > 0), what + ' load from Cloudflare', 20000);
    log.push('ok   ' + what + ': ' + imgs.length + ' photo(s) shown (' + imgs[0].naturalWidth + 'x' + imgs[0].naturalHeight + ')');
  }
  function note(cond, what) { if (!cond) bad.push(what); log.push((cond ? 'ok   ' : 'BAD  ') + what); }

  try {
    const stamp = Date.now().toString(36);
    if (!(await signUp('Photo Landlord', 'photos-' + stamp + '@example.com', 'Pw-' + stamp + '-x9!Lq'))) throw new Error('sign-up failed');
    // a property and a tenancy
    btn(/^Add a property$/).click();
    let m = await until(modal, 'property dialog');
    type(m.querySelector('input'), 'Photo Test House');
    mbtn(/^Add property$/).click();
    await until(() => window.UI_READY && /^#property\//.test(location.hash) && !modal(), 'property page', 20000);
    await sleep(500);
    btn(/^Add tenant$/).click();
    m = await until(modal, 'tenancy dialog');
    const boxes = Array.from(m.querySelectorAll('input[type=text], input:not([type])')).filter(visible);
    type(boxes[0], 'Rae Photo'); type(boxes[1], '1500');
    mbtn(/^Open the record$/).click();
    await until(() => window.UI_READY && /^#tenancy\//.test(location.hash), 'tenancy record', 20000);
    await sleep(800);
    if (!modal()) btn(/Tenant's link/).click();
    m = await until(modal, 'share dialog');
    await sleep(300);
    const linkBox = Array.from(m.querySelectorAll('input, textarea')).find((i) => /#t\//.test(i.value));
    const token = linkBox.value.split('#t/')[1].trim();
    mbtn(/^Close$/).click();
    await until(() => !modal(), 'share closed');
    log.push('ok   tenancy made, tenant link #t/' + token.slice(0, 6) + '…');

    // landlord: a task with one photo
    btn(/^Task$/).click();
    m = await until(modal, 'new task dialog');
    note(!!mfind(/^Add photos$/), 'landlord task dialog offers photos');
    await pick(m, 1, 20);
    type(m.querySelector('input'), 'Smoke alarm check');
    mbtn(/^Add task$/).click();
    await until(() => !modal(), 'task saved', 30000);
    await until(() => window.UI_READY && thumbs($('.ui-main')).length >= 1, 'photo in the record', 20000);
    await loaded(thumbs($('.ui-main')), 'landlord record thread');
    check('landlord record with a photo', /Smoke alarm check/);

    // tenant: a repair request with two photos (one removed and one added on the way), then one more from the request view
    await signOut();
    window.UI_READY = false;
    location.hash = '#t/' + token;
    await until(() => window.UI_READY && location.hash === '#t/' + token, 'tenant page', 30000);
    await sleep(800);
    await loaded(thumbs($('.ui-main')), 'tenant sees the landlord photo');
    btn(/^Ask for a repair$/).click();
    m = await until(modal, 'repair dialog');
    await pick(m, 2, 200);
    m.querySelector('.gl-ph-rm').click();
    await until(() => thumbs(m).length === 1, 'a preview removed');
    await pick(m, 1, 300);
    type(m.querySelector('input'), 'Leaking tap');
    mbtn(/^Send request$/).click();
    await until(() => !modal(), 'request sent', 40000);
    await until(() => window.UI_READY && $$('.gl-task').some((t) => /Leaking tap/.test(t.innerText) && /2 photos/.test(t.innerText)), 'request card shows 2 photos', 20000);
    log.push('ok   tenant request sent with 2 photos');
    $$('.gl-task').find((t) => /Leaking tap/.test(t.innerText)).click();
    m = await until(modal, 'request view');
    await loaded(thumbs(m.querySelector('.tv-photos')), 'request view');
    note(thumbs(m.querySelector('.tv-photos')).length === 2, 'request view shows both photos');
    note(/sealed into the record/i.test(m.innerText), 'request view explains photos are permanent');
    await pick(m.querySelector('.tv-photo-add'), 1, 90);
    mbtn(/^Add 1 photo to the record$/).click();
    await until(() => !modal(), 'photo added', 40000);
    await until(() => window.UI_READY && /Added 1 photo to #/.test($('.ui-main').innerText), 'photo event in the record', 20000);
    check('tenant page after photos', /Leaking tap/);
    const seal = $('.ui-main').innerText;
    note(!/seal is broken|BROKEN/i.test(seal), 'the seal is intact with photos');
    return { ok: !bad.length, log: log.concat(bad.map((b) => 'FAIL ' + b)) };
  } catch (e) {
    log.push('FAIL ' + (e && e.message || e));
    return { ok: false, log: log.concat(bad) };
  }
})();
