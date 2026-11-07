/* gl.js: the Good Landlord engine (moved unchanged from the JavaScript version's web/pages/_gl.html).
   The finance maths (mortgage plans with Canadian or US compounding, balances, interest/principal splits, property
   metrics, the deal verdict, year-by-year projections), the SVG houses, the two small SVG charts, the record text
   download. No page markup lives here: the pages are Python Forms (client_code), and the Python module gl.py is the
   bridge (GL.setData after every get_portfolio, the *VM functions return plain JSON-able numbers for the Forms,
   the draw* functions draw a chart into a Chart component's element). */
(function () {
  'use strict';
  var esc = function (s) { return window.UI && UI.esc ? UI.esc(s) : String(s == null ? '' : s); };
  var GL = window.GL = { data: null, cur: 'CAD' };
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

  /* ------------------------------------------------------------------ data (Python hands over get_portfolio's reply) */
  GL.setData = function (d) {
    GL.data = d; GL.cur = (d.prefs && d.prefs.currency) || 'CAD';
    GL.cat = {}; (d.categories || []).forEach(function (c) { GL.cat[c.id] = c; });
    GL.byId = {}; (d.properties || []).forEach(function (p) { GL.byId[p.id] = p; });
    GL.today = GL.d(d.today);
    return true;
  };
  GL.setCurrency = function (c) { GL.cur = c || 'CAD'; };
  GL.prop = function (id) { return GL.byId && GL.byId[id]; };
  GL.activeProps = function () { return GL.data.properties.filter(function (p) { return !p.archived; }); };
  GL.tenancyById = function (id) { return GL.data.tenancies.filter(function (t) { return t.id === id; })[0]; };

  /* ------------------------------------------------------------------ locale dates (the browser's own format) */
  GL.fmtDate = function (iso, opts) {
    if (!iso) return '';
    var d = iso.length <= 10 ? new Date(iso + 'T12:00:00') : new Date(iso);
    return d.toLocaleDateString(undefined, opts || { day: 'numeric', month: 'short', year: 'numeric' });
  };
  GL.fmtDateTime = function (iso) {
    return iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  };
  GL.fmtTime = function (iso) { return iso ? new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : ''; };
  GL.dayKey = function (iso) { return new Date(iso).toDateString(); };
  GL.ago = function (iso) {
    if (!iso) return '';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return 'just now';
    var steps = [[60, 'minute'], [24, 'hour'], [7, 'day'], [4.35, 'week'], [12, 'month'], [Infinity, 'year']], n = s / 60;
    for (var i = 0; i < steps.length; i++) {
      if (n < steps[i][0]) { n = Math.floor(n); return n + ' ' + steps[i][1] + (n === 1 ? '' : 's') + ' ago'; }
      n = n / steps[i][0];
    }
    return '';
  };
  GL.hourNow = function () { return new Date().getHours(); };
  GL.todayLong = function () { return GL.today.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' }); };
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
  GL.days = function (d) { return d < 1 ? Math.max(1, Math.round(d * 24)) + ' h' : (Math.round(d * 10) / 10) + (d < 1.5 ? ' day' : ' days'); };
  GL.hours = function (h) { return h < 1 ? Math.max(1, Math.round(h * 60)) + ' minutes' : h < 48 ? Math.round(h) + (Math.round(h) === 1 ? ' hour' : ' hours') : Math.round(h / 24) + ' days'; };
  GL.badges = function (st) {
    var out = [];
    if (st.reply_hours != null) out.push(['clock', 'Usually replies in ' + GL.hours(st.reply_hours)]);
    if (st.fix_days != null) out.push(['wrench', 'Fixes things in ' + GL.days(st.fix_days)]);
    if (st.requests && st.answered === st.requests) out.push(['heart', 'Answered every request']);
    return out;
  };

  /* Copy to the clipboard; resolves true when it worked (Python shows the toast). */
  GL.copy = function (text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return false; });
    return Promise.resolve(false);
  };
  GL.tenantLink = function (token) { return location.href.split('#')[0].split('?')[0] + '#t/' + token; };

  /* ------------------------------------------------------------------ the record as a text file */
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

  /* ------------------------------------------------------------------ view models for the Python Forms
     Each returns plain numbers / strings (dates as 'YYYY-MM-DD'), so Python reads them as dicts. The maths is the
     JavaScript version's, line for line; only the HTML building moved to the Forms. */
  function propOrNull(id) { var p = GL.prop(id); return p || null; }
  function plainMetrics(m) {
    var v = GL.verdict(m.annual, m.profit);
    return { value: m.value, balance: m.balance, loan: m.loan, mortMonthly: m.mortMonthly, mortgages: m.plans.length, tenancies: m.tenancies.length,
      rent: m.rent, opexMonthly: m.opexMonthly, otherMonthly: m.otherMonthly, cashMonthly: m.cashMonthly, cfRecorded: m.cfRecorded, capAll: m.capAll,
      invested: m.invested, sellPct: m.sellPct, sellCost: m.sellCost, proceeds: m.proceeds, equity: m.equity, profit: m.profit, roi: m.roi,
      annual: m.annual, years: m.years, capRate: m.capRate, cashOnCash: m.cashOnCash, appreciationGain: m.appreciationGain, paydown: m.paydown,
      gap: m.gap, first: m.first ? GL.iso(m.first) : null, since: GL.iso(m.since), glow: GL.glowFor(m.cashMonthly),
      verdict: { key: v.key, label: v.label, text: v.text, glow: v.glow } };
  }
  GL.metricsVM = function (id, opts) {
    var p = propOrNull(id); if (!p) return null;
    var o = {}; if (opts && opts.value != null) o.value = +opts.value; if (opts && opts.sellPct != null) o.sellPct = +opts.sellPct;
    return plainMetrics(GL.metrics(p, o));
  };
  GL.houseFor = function (o) { return GL.house(o || {}); };

  /* Home: mortgages renewing within 150 days (still owing). */
  GL.renewalsVM = function () {
    var today = GL.today, out = [];
    GL.data.mortgages.forEach(function (m) {
      var p = GL.plan(m), r = GL.renewal(p), days = Math.round((r - today) / 864e5);
      if (days >= 0 && days <= 150 && GL.balanceAt(p, today) > 0) out.push({ property_id: m.property_id, days: days });
    });
    return out;
  };

  /* Property page: one summary per loan. */
  GL.mortgagesVM = function (propId) {
    var today = GL.today;
    return GL.mortgagesOf(propId).map(function (pl) {
      var mo = pl.m, yr = GL.paidBetween(pl, new Date(today.getFullYear(), 0, 1), today), f = GL.FREQ.filter(function (x) { return x[0] === mo.frequency; })[0];
      return { id: mo.id, lender: mo.lender || '', rate: mo.rate, payment: pl.P, freq: f ? f[1].toLowerCase() : '', balance: GL.balanceAt(pl, today),
        interestYear: yr.interest, renews: GL.iso(GL.renewal(pl)), payoff: GL.iso(GL.addMonths(pl.start, Math.round(pl.payoff * 12 / pl.n))) };
    });
  };
  /* Property page: money in and out, last 12 months (bar chart). */
  GL.drawPropChart = function (box, propId) {
    var led = GL.data.ledger.filter(function (e) { return e.property_id === propId; });
    var months = [], inc = [], out = [];
    for (var i = 11; i >= 0; i--) months.push(GL.ym(GL.addMonths(GL.today, -i)));
    months.forEach(function (ym) {
      var a = 0, b = 0;
      led.forEach(function (e) { if (e.date.slice(0, 7) === ym) { if (e.kind === 'income') a += e.amount; else b += e.amount; } });
      inc.push(a); out.push(b);
    });
    GL.barChart(box, { title: 'Money in and out by month', labels: months.map(function (m) { return GL.monthName(m, true); }), tipLabels: months.map(function (m) { return GL.monthName(m); }),
      series: [{ label: 'Money in', color: 'var(--gl-s1)', values: inc }, { label: 'Money out', color: 'var(--gl-s2)', values: out }], height: 200 });
  };

  /* Money page, tax summary: mortgage interest and principal per loan for a year (up to today in the current year). */
  GL.taxInterestVM = function (year, propId) {
    var start = new Date(+year, 0, 1, 12), end = new Date(+year, 11, 31, 12), partial = end > GL.today;
    if (partial) end = GL.today;
    var rows = [];
    GL.data.properties.forEach(function (p) {
      if (propId && p.id !== propId) return;
      GL.mortgagesOf(p.id).forEach(function (pl) { var x = GL.paidBetween(pl, start, end); if (x.interest > 0.5) rows.push({ name: p.name, lender: pl.m.lender || '', v: x.interest, principal: x.principal }); });
    });
    return { rows: rows, partial: partial };
  };

  /* Deal check, "if you sold today" + "if you keep it" + ratios, for the slider values S
     {value, sell, appr, years, rent, cost}. */
  function dealRows(m, S, appr) {
    return GL.project(m, { years: +S.years, appr: appr == null ? +S.appr : appr, rentGrowth: +S.rent, costGrowth: +S.cost, sellPct: +S.sell, value: +S.value });
  }
  GL.dealStartVM = function (propId) {
    var p = propOrNull(propId); if (!p) return null;
    var m0 = GL.metrics(p);
    return { value: Math.round(m0.value / 1000) * 1000 || 0, sell: m0.sellPct, appr: +p.appreciation || 0,
      vmax: Math.max(100000, Math.round(m0.value * 1.6 / 10000) * 10000), vmin: Math.max(0, Math.round(m0.value * .5 / 10000) * 10000) };
  };
  GL.dealVM = function (propId, S) {
    var p = propOrNull(propId); if (!p) return null;
    var m = GL.metrics(p, { value: +S.value, sellPct: +S.sell });
    var v = GL.verdict(m.annual, m.profit);
    var parts = [['Price growth', m.appreciationGain], ['Mortgage paid down', m.paydown],
      ['Cash flow' + (m.first ? ' since ' + GL.fmtDate(GL.iso(m.since), { month: 'short', year: 'numeric' }) : ''), m.cfRecorded],
      ['Buying & improving', -((+p.closing_costs || 0) + (+p.improvements || 0) + m.capAll)], ['Selling costs', -m.sellCost]];
    if (Math.abs(m.gap) > 1) parts.push(['Down payment vs loan', m.gap]);
    var mx = Math.max.apply(null, parts.map(function (x) { return Math.abs(x[1]); })) || 1;
    var rows = dealRows(m, S), last = rows[rows.length - 1];
    var sens = [-2, -1, 0, 1, 2, 3, 4, 5, 6, 8].map(function (a) { var r = dealRows(m, S, a); return { a: a, profit: r[r.length - 1].profit }; });
    var smax = Math.max.apply(null, sens.map(function (s) { return Math.abs(s.profit); })) || 1;
    sens.forEach(function (s) { s.t = Math.min(1, Math.abs(s.profit) / smax); });
    var ms = [1, 5, 10, 15, 20, 25, 30].filter(function (y) { return y <= +S.years; });
    if (ms[ms.length - 1] !== +S.years) ms.push(+S.years);
    return {
      verdict: { key: v.key, label: v.label, text: v.text, glow: v.glow },
      today: { proceeds: m.proceeds, profit: m.profit, roi: m.roi, annual: m.annual, years: m.years },
      why: parts.map(function (x) { return { label: x[0], v: x[1], w: Math.abs(x[1]) / mx * 50 }; }),
      hasLedger: !!m.first,
      future: { value: last.value, balance: last.balance, profit: last.profit, annual: last.annual },
      sens: sens,
      miles: ms.map(function (y) { var r = rows[y]; return { y: y, equity: r.equity, cf: r.cf, profit: r.profit }; }),
      ratios: { cap: m.capRate, coc: m.cashOnCash, rtv: +S.value ? m.rent / +S.value : 0 }
    };
  };
  GL.drawDealChart = function (box, propId, S) {
    var p = propOrNull(propId); if (!p) return;
    var m = GL.metrics(p, { value: +S.value, sellPct: +S.sell }), rows = dealRows(m, S);
    GL.lineChart(box, { title: 'Value and mortgage over time', labels: rows.map(function (r) { return String(r.date.getFullYear()); }), height: 220,
      series: [{ label: 'Value', color: 'var(--gl-s1)', values: rows.map(function (r) { return r.value; }), fillTo: 1 }, { label: 'Mortgage owed', color: 'var(--gl-s2)', values: rows.map(function (r) { return r.balance; }) }],
      note: 'Shaded: your equity', extraTip: function (i) { return '<div>Equity: <b>' + esc(GL.money(rows[i].equity)) + '</b></div><div>Profit if sold: <b>' + esc(GL.money(rows[i].profit)) + '</b></div>'; } });
  };

  /* Deal check, the mortgage section (first loan of the property). */
  GL.mortgageVM = function (propId) {
    var plans = GL.mortgagesOf(propId);
    if (!plans.length) return null;
    var pl = plans[0], today = GL.today, sofar = GL.paidBetween(pl, pl.start, today), ren = GL.renewal(pl);
    return { count: plans.length, id: pl.m.id, lender: pl.m.lender || '', amount: pl.L, rate: +pl.m.rate, amort: +pl.m.amort_years, compounding: pl.m.compounding,
      payment: pl.P, monthly: pl.monthly, balance: GL.balanceAt(pl, today), interestSoFar: sofar.interest, principalSoFar: sofar.principal,
      renDays: Math.round((ren - today) / 864e5), renews: GL.iso(ren), balRen: GL.balanceAt(pl, ren), leftYears: Math.max(1, (+pl.m.amort_years) - (+pl.m.term_years)) };
  };
  GL.drawAmort = function (box, propId) {
    var pl = GL.mortgagesOf(propId)[0]; if (!pl) return;
    var years = [], ints = [], prins = [];
    var y0 = pl.start.getFullYear(), yEnd = GL.addMonths(pl.start, Math.round(pl.payoff * 12 / pl.n)).getFullYear();
    for (var y = y0; y <= yEnd; y++) {
      var x = GL.paidBetween(pl, new Date(y - 1, 11, 31, 23), new Date(y, 11, 31, 23));
      years.push(String(y)); ints.push(x.interest); prins.push(x.principal);
    }
    GL.barChart(box, { title: 'Interest and principal paid each year', labels: years, stacked: true, height: 200,
      series: [{ label: 'Principal (builds equity)', color: 'var(--gl-s1)', values: prins }, { label: 'Interest (claimable)', color: 'var(--gl-s2)', values: ints }],
      extraTip: function (i) { return '<div>Owed at year end: <b>' + esc(GL.money(GL.balanceAt(pl, new Date(+years[i], 11, 31, 23)))) + '</b></div>'; } });
  };
  GL.renewVM = function (propId, rate) {
    var pl = GL.mortgagesOf(propId)[0]; if (!pl) return null;
    var ren = GL.renewal(pl), balRen = GL.balanceAt(pl, ren), leftYears = Math.max(1, (+pl.m.amort_years) - (+pl.m.term_years));
    var np = GL.plan(Object.assign({}, pl.m, { amount: balRen, rate: +rate, amort_years: leftYears, start_date: GL.iso(ren) }));
    return { monthly: np.monthly, diff: np.monthly - pl.monthly };
  };

  /* Deal check, the calculator. c = {price, down, rate, amort, frequency, compounding, rent, costs} (numbers). */
  function calcPlan(c) {
    var loan = (+c.price || 0) * (1 - (+c.down || 0) / 100);
    return { loan: loan, pl: GL.plan({ amount: loan, rate: +c.rate || 0, amort_years: +c.amort || 25, frequency: c.frequency, compounding: c.compounding, start_date: GL.iso(GL.today || new Date()) }) };
  }
  GL.calcVM = function (c) {
    var x = calcPlan(c), pl = x.pl, loan = x.loan;
    var total = pl.P * pl.payoff, interest = Math.max(0, total - loan), cash = (+c.rent || 0) - (+c.costs || 0) - pl.monthly;
    var downCash = (+c.price || 0) * (+c.down || 0) / 100;
    return { payment: pl.P, monthly: pl.monthly, cash: cash, interest: interest, loan: loan, coc: downCash > 0 ? cash * 12 / downCash : 0 };
  };
  GL.drawCalc = function (box, c) {
    var pl = calcPlan(c).pl;
    var yrs = [], bal = [], paidI = [], cum = 0, years = Math.ceil(pl.payoff / pl.n);
    for (var y = 0; y <= years; y++) {
      var at = GL.addYears(pl.start, y); yrs.push('Yr ' + y); bal.push(GL.balanceAt(pl, at));
      if (y > 0) cum += GL.paidBetween(pl, GL.addYears(pl.start, y - 1), at).interest;
      paidI.push(cum);
    }
    GL.lineChart(box, { title: 'Balance and interest paid', labels: yrs, height: 210,
      series: [{ label: 'Still owed', color: 'var(--gl-s2)', values: bal }, { label: 'Interest paid so far', color: 'var(--gl-s1)', values: paidI, dash: true }] });
  };

  /* Small formatters with plain arguments (Python calls them a lot). */
  GL.fmt = function (v, cents, short, sign) { return GL.money(v, { cents: !!cents, short: !!short, sign: !!sign }); };
  var DATE_STYLES = { dm: { day: 'numeric', month: 'short' }, my: { month: 'long', year: 'numeric' }, mys: { month: 'short', year: 'numeric' },
    wdm: { weekday: 'short', day: 'numeric', month: 'short' }, wdmy: { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' },
    full: { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' } };
  GL.dateStyle = function (iso, style) { return GL.fmtDate(iso, DATE_STYLES[style]); };
  GL.recordFile = function (name, json) { GL.download(name, GL.recordText(JSON.parse(json))); };
  GL.todayIso = function () { return GL.iso(new Date()); };
  GL.plusDaysIso = function (n) { return GL.iso(new Date(Date.now() + n * 864e5)); };
  GL.daysBetween = function (a, b) { return Math.round((GL.d(b) - GL.d(a)) / 864e5); };
  GL.isoDaysAgo = function (n) { return GL.iso(new Date((GL.today || new Date()).getTime() - n * 864e5)); };

})();
