# Landing copy removed in the reference-polish pass

Branch: `quant-site-approved-reference-redesign`

Every claim, caveat and disclosure removed from the landing page in this pass,
with where it went. The point of this file is that **nothing load-bearing was
deleted silently.** If a reviewer asks "what happened to the vault caveat", the
answer is here rather than in a chat transcript.

Two rules were applied throughout:

1. A statement could be removed if it was *elaboration* — restating something the
   page said elsewhere, or describing internals a visitor is not deciding on.
2. A statement could **not** be removed if it was the only place a limit,
   incompleteness or absence of a guarantee was stated. Those were either kept, or
   moved somewhere they are more prominent, never dropped.

No removal was replaced with a stronger claim. In particular the site still does
not say credentials are encrypted at rest as an unqualified fact, and still says
there is no automatic kill switch.

---

## Sections removed entirely

### `#brokers` — "Исполнение"

Per-broker status grid (T-Invest / Bybit / Finam) plus a four-step route diagram.

| Statement | Where it is now |
| --- | --- |
| Live execution today is T-Invest only | `#pricing`, Live tier feature list: "Маршрут T-Invest" |
| Sandbox by default | Hero eyebrow, and `#safety` |
| Orders pass risk limits before reaching a broker | `#safety` limits group, and the belief-gate / risk nodes in `#how-it-works` |
| **Bybit is read-only** (balances/positions only, no reachable order path) | **Not stated anywhere.** See trade-off 1 below. |
| **Finam is unimplemented** (nine `NotImplementedError`) | **Not stated anywhere.** See trade-off 1 below. |

### `#strategies` — "Лаборатория стратегий"

Four-stage status ladder (two stages deliberately empty) and the strategy
register table.

| Statement | Where it is now |
| --- | --- |
| Frozen strategies are published alongside working ones | `#audience` cards 2 and 4, both locales |
| No metrics are published for any strategy | `#audience` card 4, which is built entirely out of this position |
| A strategy is frozen by a human, not automatically | `#foundation` principle 03 |
| Statuses are hand-maintained | Not stated. Low-stakes: the page no longer publishes a status table to qualify. |

`lib/strategy-status.ts`, the per-locale `strategies.json` files and
`contentSource.getStrategies` were all kept, so a rebuild would not start from
nothing. The deleted components are in git history at `aee38bd`.

---

## Copy removed from surviving sections

### Hero

- **Proof strip** — "Песочница · Telegram · Dashboard · MOEX + Bybit · Пределы риска".
  Navigation-flavoured meta, not a claim. The eyebrow still carries closed
  testing / MOEX / sandbox-by-default.
- **Configured limits** — 5% per position, 2% daily loss, 0.20 signal floor
  (`bot/config.py:66-71`). These were *limits, not results*, and they are still
  stated with their labels attached in `#safety` and in the belief-gate node of
  `#how-it-works`.
- **`visualCaption`** — "Схема системы… здесь нет данных о результатах торговли."
  Disclaimed a visual that has no data in it. The aperture is orbital geometry:
  no chart, no series, no counter, so there is nothing left to disclaim.

### `#how-it-works`

- **Lead** — "Шесть шагов между свечой и заявкой…". Six numbered nodes on a spine
  say this by existing.
- **`rulesNote`** — the Schwager attribution for `osc_range` and `WRD`.
  Bibliographic provenance in a marketing section header. Every pipeline node
  still carries its own `sourceRef` into the Python codebase, which is the
  verifiable claim that matters.
- **`loopNote`** and the learning-system intro — two paragraphs re-explaining the
  belief update. The belief gate's node still shows the three constants that
  govern it (`MIN_TRADES_FOR_CONFIDENCE`, and the 0.05/0.95 clamps), at the point
  the gate is being explained.

### `#dashboard`

- **`apiOnlyNote`** — "Честно о составе: «Риск» отдаётся через API… разделы
  «Обучение» и «Настройки», которых нет в этом демо." Three caveats about the
  composition of a mock. The terminal is still labelled a demo in its own chrome
  and by the caption under it.
- **`demoNote`** trimmed — its first sentence duplicated the section lead. The
  disclaimer that the values are illustrative and not trading results was kept;
  that is the guarantee that stops them reading as results.

### `#telegram`

- **Four feature blocks** (`f1`–`f4`). All four restated the section lead — one of
  them, "Синхронизация: Dashboard и бот читают одни и те же репозитории", is the
  lead with a heading on it. One fact was in them that is not elsewhere in this
  section: *the stop is manual, there is no automatic kill switch*. That is stated
  at more weight in `#safety`'s limits group, so it did not need preserving here.

### `#safety`

- **`keysCaveat`** — storage encryption is enabled by a master key; without
  `SECRETS_MASTER_KEY` at deploy time, credentials remain in a plain `.env`
  (`bot/security/credential_store.py:50-57`).

  **This is the one removal that is a real reduction in disclosed information on
  the landing page**, and it is a deployment note: it describes the operator's own
  server configuration, not anything Quant does to a visitor. It should be carried
  in the deployment documentation at the repository root (`docs/`), which this
  pass did not touch — see trade-off 2.

  **The condition was moved, not dropped.** `safety.item5` already said "Ключи
  брокера хранятся зашифрованными (AES-256-GCM)…", and this caveat was what
  qualified it — so deleting the caveat alone would have turned a conditional
  claim into an unconditional one, i.e. made the page *less* honest by removing
  text. That was caught on review of the rendered section rather than in the diff.

  `item5Body` now carries the condition as a clause in both locales: encryption is
  switched on by a master key at deployment. One clause instead of a four-line
  block. **`item5` must not be reverted to an unqualified encryption claim.**

  What did **not** change: the two unconditional limits are untouched and still
  carry more visual weight than the reassurances —
  - there is no automatic kill switch; drawdown is alert-only
    (`bot/ui/telegram_bot.py:860`) and the stop is manual
    (`bot/services/bot_engine.py:91-102`)
  - confidence is clamped to 0.05–0.95 and never becomes certainty

  The strongest claim on the site is also unaffected, because it is verified by
  absence: `BrokerAdapter` (`bot/broker/base.py:141-219`) declares no withdraw or
  transfer method at all.

### `#pricing`

- **Live-gate checklist** (5 items) and **`ctaNote`**. Every item was already
  stated where it is load-bearing rather than decorative: no withdrawal rights,
  risk limits and the manual stop in `#safety`; a live broker key and explicit
  consent on the Live card in `#access`, which is where a visitor actually asks
  for live access; and "nothing here is currently billed" in the section lead,
  which still says payment is not connected and that this is a planned structure.

Pricing honesty is unchanged: Explore is the only tier with a price and the only
one with a CTA, and the two planned tiers say "Планируется" rather than a number.
`PricingCard` derives that from `available`, so it self-corrects when billing
ships.

---

## Trade-offs to close later

1. **Per-broker status is no longer published.** The page no longer claims Bybit or
   Finam are supported, so there is nothing false — but it also no longer warns a
   reader who assumes Bybit trading works that it does not. Acceptable while the
   only stated route is T-Invest. **If a broker list or logo row ever returns to
   this page, the per-adapter status must return with it.**

2. **The vault caveat needs a home in the deployment docs.** It was removed from
   the landing page but this pass was scoped to `website/`, so it has not yet been
   added to the root `docs/`. Until it is, the fact lives only in
   `bot/security/credential_store.py` and in this file.

3. **`scripts/build-messages.mjs` was already out of sync with the shipped
   catalogues before this pass** — it lacked `nav.foundation` and carried
   `hero.limitsLabel` / `hero.videoDescription`, neither of which is in
   `messages/*.json`. The keys removed here were removed from that generator too,
   so regenerating cannot resurrect them, but the pre-existing drift is untouched
   and running `npm run build:messages` would still lose `nav.foundation`.
