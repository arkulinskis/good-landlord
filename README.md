# Good Landlord

For small landlords who want to know their numbers and treat tenants fairly. Track rent and every claimable expense,
see cash flow, mortgage, equity and the profit a property would make if sold today or in 20 years, and give each tenant a
private link to a permanent, tamper-evident record of messages and repair requests (with the date each was asked and
done). Warm-home look: linen, terracotta and honey, Fraunces + Nunito Sans. Built on [Anvil](https://anvil.works).

- **App repo:** github.com/arkulinskis/good-landlord (branch `master`). Anvil pulls `master`.
- **Live:** https://good-landlord.anvil.app

## What it does

**For everyone:** a free **rental property calculator** at `#calculator` (no sign-up: payment, cash flow,
cash-on-cash, a plain-words verdict, rules of thumb (cap rate, debt cover, break-even rent, 1% rule), balance chart,
currency, and "Copy a link to these numbers": the inputs ride in the address, `#calculator/price=..&rent=..`), a landing page written for landlords and tenants (hero house at dusk, "good for both sides of the door",
how it works, features, FAQ), a **public tenant demo** at `#t/demo-upstairs`, sign-up with email and password or Google, a feedback
form, and the Privacy & Terms page.

**For landlords (signed in):**
- **Home** (`#home`): a street of their houses (windows glow brighter with cash flow, chimney smoke when positive), rent
  this month (collected vs expected), monthly cash flow, equity, profit if sold today; "Needs your attention" (new
  requests, unread messages, rent not recorded after the due day, mortgage renewals within 150 days, **lease ends within
  120 days with the "send the offer by" date (60 days' notice), renewal accepted / tenant wants to talk**, work scheduled this
  week); property cards; their response badges. Empty state: add a property or **load the sample portfolio** (three
  fictional rentals, four tenants, 14 months of ledger, conversations and requests), clearable in one click.
- **Property** (`#property/<id>`): value, mortgage owed, equity, cash flow; 12-month money in/out chart; recent entries;
  tenants with link + record buttons; mortgage summary (payment, owed, claimable interest this year, renewal, payoff);
  notes; edit (door colour!), archive, delete (only without tenancy records).
- **Money** (`#money/ledger|rent|tax`): ledger with filters (property, year, category, in/out) grouped by month, CSV
  export; **rent roll** per month (paid / due / late, one-tap "Paid", which also writes a receipt into the tenant's
  record); **tax summary** per year (income lines, claimable expenses by category, mortgage interest worked out from
  the loan, net rental income, capital improvements, not-claimable incl. principal), with a country hint (T776/TP-128,
  Schedule E, SA105), print/PDF.
- **Deal check** (`#deal/<id>[/mortgage]`, `#deal/calculator`): *If you sold today*: sale price + selling cost sliders,
  verdict with a glowing house (losing money / modest / good / great, from the yearly return), walk-away amount,
  profit, return, per-year return, and "where it comes from" (price growth, mortgage paid down, recorded cash flow,
  buying & improving, selling costs). *If you keep it*: appreciation slider + presets, years, rent and cost growth ->
  value vs debt chart with equity band, milestones table, 10 sensitivity tiles (profit at -2%..8% growth, tap to apply).
  *Mortgage*: payment, owed, interest/principal so far, renewal countdown, interest vs principal by year (stacked
  bars), **rate at renewal** slider. Quick ratios (cap rate, cash-on-cash, rent-to-value). "Keep these estimates" saves
  value/growth/selling %. Free **calculator** for deals not yet bought.
- **Tenants** (`#tenants`, `#tenants/requests`): tenancy cards (last message, unread, open requests, copy link, open
  record) and a requests board (New / Seen / Scheduled / In progress / Done in 30 days).
- **Tenancy record** (`#tenancy/<id>[/share]`): the sealed thread (messages + every request move, rent receipt and
  change, with dates and fingerprints), composer (Ctrl+Enter), "Check again" seal verification, requests (move along:
  seen / schedule with date / working / done with cost -> ledger / decline with reason / reopen), lease facts, rent
  received chips, share dialog (link, ready-to-paste message, mailto, make a new link), download as .txt, edit, end /
  reopen, delete only if never used. Polls every 30 s.
- **Profile**: currency (CAD, USD, EUR, GBP, AUD, NZD, CHF), country (tax hint), default mortgage compounding.

**For tenants** (`#t/<token>`, no account, no app header): hello + landlord name + response badges, seal status, "Is it
fixed?" banner when a request was marked done, messages + composer ("writing as" name kept in the browser), ask for a
repair (type, urgency), request list with dates, lease facts and rent receipts, download the record. Polls every 30 s.

**Repair photos** (Cloudflare R2, private): up to 6 photos when asking for a repair or adding a task, and "Add photos"
on any request afterwards (both sides: the problem, the fix, the receipt). The browser shrinks each photo (2000 px JPEG,
which also strips its GPS location) and uploads it straight to the `goodlandlord-photos` Worker with a link the server
signed (no bytes through Anvil). The Worker stores the file's SHA-256 and never overwrites; the server seals those
fingerprints into the record entry, so removing or swapping a photo breaks the seal. Photos show in the request view,
under their record entry and as a count on request cards; every view link is signed for that tenancy only and expires
within two hours. The downloaded record lists each photo's SHA-256. Off in demo/sample tenancies and without the App
Secret `cloudflare_photos`. Worker + bucket: `tools/cloudflare/` (`python -I tools/cloudflare/deploy.py`).

**Condition reports and renewal offers** (2026-11-20, server `Agreements.py`, no table of their own: they ARE record
entries, so they're dated and sealed): either side writes a **move-in or move-out condition report** room by room (Good /
Worn / Damaged / Missing + note; a move-out report starts from the move-in rooms and lists every room that got worse); the
other side answers once, "I agree" or "I don't agree" + what isn't right. The landlord **plans a renewal** (rent change
slider, new start and end dates, note, "+$X a year vs one empty month" maths, a notice-date hint) and sends the offer
into the record; the tenant sees a banner with Accept / I'd like to talk; an accepted offer is applied with one button
(rent + lease end change, noted in the record). Tenancy page: card "Move-in, move-out & renewal"; tenant page: card
"Condition reports" + banners. Demo: a move-in report the Patels agreed to, an accepted offer for Sam, the Patels' lease
ending in 75 days (Admin -> Demo data -> reload to see them on an existing live demo).

**The record rules:** no server function edits or deletes a message; each entry stores SHA-256(prev hash | seq | time |
author kind | author name | body | event | task number [| photos:sorted SHA-256s]); `Record.verify` recomputes the chain. Only Admin -> Demo data
removes demo rows, and an unused tenancy (opening entry only, never visited) can be deleted.

**For admins** (`#admin`; your admin email (App Secret `admin_emails`) becomes an admin on first sign-in):
- **Feedback inbox:** New / Read / Done, private notes.
- **Users:** search, make admin, disable an account.
- **Overview:** landlords, properties, tenancy records and entries (counts only; admins don't read records).
- **Demo data:** the public demo landlord Maya Chen and her tenancies (fixed links `#t/demo-upstairs`, `demo-garden`, `demo-harbour`, `demo-willow`); remove or reload it.

## Setting it up in Anvil (once)

1. In the Anvil editor: **Create app → Clone from GitHub**, and paste `https://github.com/arkulinskis/good-landlord`.
2. **Users** service: email + password and "Continue with Google", sign-up allowed (already set in `anvil.yaml`; check it).
3. Open the app in the editor. If it shows a **Schema Mismatch** alert, choose **"The schema of the source code is correct"** so Anvil creates the tables.
4. **Run** it and sign up with **your admin email** (App Secret `admin_emails`) straight away (that account becomes the admin).
5. **Publish** (Publish → public URL, or your own domain).

<!-- libraries:start -->
## Libraries and outside services

What this project uses besides its own code. Generated by `APP_MAKER/tools/libraries.py`; to change it, edit `APP_MAKER/libraries/catalog.py` and re-run the script.

| Name | How it gets in | Used here for |
|---|---|---|
| [YouTube embeds](https://developers.google.com/youtube/player_parameters) | Outside web service | Plays a YouTube video inside the page (the privacy-friendlier youtube-nocookie address). |
| [Cloudflare R2](https://developers.cloudflare.com/r2/) | Outside web service | repair-request photos in the private bucket goodlandlord-photos, behind our own Worker (HMAC-signed uploads and views, SHA-256 sealed into the record) |
| [Google Fonts](https://fonts.google.com) | Loaded from a CDN | Fraunces, Nunito Sans |

**Built into the browser:** Canvas 2D, localStorage, Clipboard, File downloads (Blob).

**Anvil platform:** Anvil, Anvil Data Tables, Anvil Email, Anvil JS bridge (anvil.js), Anvil Secrets, Anvil Users, Anvil Google service, Anvil HTTP, Anvil timezones (anvil.tz).

**Build and test tools (not shipped):** axe-core, Node.js, Headless Chrome (DevTools Protocol), PyYAML.

<!-- libraries:end -->

## Working on it

Native Anvil Forms (since Nov 2026, branch `forms`): this folder *is* the Anvil app. Code map: `APP_MAP.md`.

```
python tools/check.py                            # Anvil's validator, JS syntax, asset hashes, server tests -> ALL CHECKS PASSED
python -I tools/ui_test.py                       # smoke test in the Anvil App Server (Docker): every page, desktop + phone
git push origin forms                            # Anvil pulls the branch you publish
```

## Project layout

```
client_code/    startup.py, router.py (addresses), state.py, auth.py, gl.py (bridge to the engine + portfolio cache), legal.py
                Layouts/Shell, Pages/ (Landing, Auth, Home, Property, Money, Deal, Tenants, Tenancy, TenantPage, Profile, Admin),
                Items/ (RepeatingPanel rows), Dialogs/ (property, mortgage, tenancy, ledger entry, task, new request, share link),
                Components/ (House, Chart, Slider)
server_code/    common.py, Accounts.py, Feedback.py, Admin.py, DemoData.py, legal_server.py, seo_routes.py, SchemaCheck.py,
                Portfolio.py, Ledger.py, Tenancy.py, TenantPortal.py, Record.py (the append-only hash-chained record)
theme/assets/   gl.js (the engine: finance maths, SVG houses, charts, record download), app.css, icons.css, app-kit.js,
                legal-kit.js, theme.css (loading spinner), icons and pictures (served at _/theme/<name>)
tools/          check.py, assets.py, build_icons.py, make_icons.py, ui_test.py + ui/smoke.js, live/drive.mjs, testing/
```
