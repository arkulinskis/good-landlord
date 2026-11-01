# Good Landlord

For small landlords who want to know their numbers and treat tenants fairly. Track rent and every claimable expense,
see cash flow, mortgage, equity and the profit a property would make if sold today or in 20 years, and give each tenant a
private link to a permanent, tamper-evident record of messages and repair requests (with the date each was asked and
done). Warm-home look: linen, terracotta and honey, Fraunces + Nunito Sans. Built on [Anvil](https://anvil.works).

- **App repo:** github.com/arkulinskis/good-landlord (branch `master`). Anvil pulls `master`.
- **Live:** not published yet (the user publishes in Anvil, then the URL goes in apps.json and here).

## What it does

**For everyone:** a landing page written for landlords and tenants (hero house at dusk, "good for both sides of the door",
how it works, features, FAQ), a **public tenant demo** at `#t/demo-upstairs`, sign-up with email and password, a feedback
form, and the Privacy & Terms page.

**For landlords (signed in):**
- **Home** (`#home`): a street of their houses (windows glow brighter with cash flow, chimney smoke when positive), rent
  this month (collected vs expected), monthly cash flow, equity, profit if sold today; "Needs your attention" (new
  requests, unread messages, rent not recorded after the due day, mortgage renewals within 150 days, work scheduled this
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

**The record rules:** no server function edits or deletes a message; each entry stores SHA-256(prev hash | seq | time |
author kind | author name | body | event | task number); `Record.verify` recomputes the chain. Only Admin -> Demo data
removes demo rows, and an unused tenancy (opening entry only, never visited) can be deleted.

**For admins** (`#admin`; arkulinskis@gmail.com becomes an admin on first sign-in):
- **Feedback inbox:** New / Read / Done, private notes.
- **Users:** search, make admin, disable an account.
- **Overview:** landlords, properties, tenancy records and entries (counts only; admins don't read records).
- **Demo data:** the public demo landlord Maya Chen and her tenancies (fixed links `#t/demo-upstairs`, `demo-garden`, `demo-harbour`, `demo-willow`); remove or reload it.

## Setting it up in Anvil (once)

1. In the Anvil editor: **Create app → Clone from GitHub**, and paste `https://github.com/arkulinskis/good-landlord`.
2. **Users** service: email + password, sign-up allowed (already set in `anvil.yaml`; check it).
3. Open the app in the editor. If it shows a **Schema Mismatch** alert, choose **"The schema of the source code is correct"** so Anvil creates the tables.
4. **Run** it and sign up with **arkulinskis@gmail.com** straight away (that account becomes the admin).
5. **Publish** (Publish → public URL, or your own domain).

<!-- libraries:start -->
## Libraries and outside services

What this project uses besides its own code. Generated by `APP_MAKER/tools/libraries.py`; to change it, edit `APP_MAKER/libraries/catalog.py` and re-run the script.

| Name | How it gets in | Used here for |
|---|---|---|
| [Google Fonts](https://fonts.google.com) | Loaded from a CDN | Fraunces, Nunito Sans |

**Built into the browser:** localStorage, Clipboard, File downloads (Blob).

**Anvil platform:** Anvil, Anvil Data Tables, Anvil JS bridge (anvil.js), Anvil Users.

**Build and test tools (not shipped):** Node.js, PyYAML, Headless Chrome (DevTools Protocol).

<!-- libraries:end -->

## Working on it

See `.claude/skills/goodlandlord/SKILL.md`. In short:

```
python -I tools/check.py --ui                    # syntax, server tests, headless UI tests → ALL CHECKS PASSED
python -I tools/preview/devserver.py 8765        # the app on in-memory data: http://localhost:8765/  (?as=ana#home, ?as=admin#admin)
python tools/deploy.py                           # dry run (needs PyYAML, so no -I)
python tools/deploy.py --push "Message"          # deploy: commit + push to GitHub, Anvil pulls it
```

## Project layout

```
web/            the interface: core.js/core.css (shared engine + design tokens), app.js (header, footer), pages/*.html
                (pages/_gl.html = shared finance maths, houses, charts, forms, the record thread)
client_code/    Main.py (the only Anvil form: bridge to the server, sign-in), legal.py
server_code/    common.py, Accounts.py, Feedback.py, Admin.py, DemoData.py, legal_server.py,
                Portfolio.py, Ledger.py, Tenancy.py, TenantPortal.py, Record.py
assets/         icon.svg + generated PNG icons, pictures (served at _/theme/<name>)
tools/          sync_to_anvil.py (settings + table schema), deploy.py, check.py, preview/ (dev server, UI tests, screenshots), testing/
```
