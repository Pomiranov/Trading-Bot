#!/usr/bin/env node
/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  STALE — DO NOT RUN. This is NOT the source of truth any more.           ║
 * ║  Running it DELETES 56 keys that the site is using and breaks the page.  ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 *
 * `messages/{ru,en}.json` have been hand-edited since this generator was last
 * used, and they are what ships. This file has drifted behind them.
 *
 * Measured, by generating into a scratch copy and diffing the key sets:
 *
 *   • 56 keys exist in the shipped catalogues and NOT here — the entire
 *     `foundation` namespace, `nav.foundation`, `faq.eyebrow`,
 *     `safety.{guaranteesHeading,limitsHeading}`, the whole dashboard tab/column
 *     set (`tab1Label`…`rkApiNote`, 39 keys), `telegram.card{Accepted,Skipped,
 *     Reset,DemoHint}` and the four `footer.col*`/`linkFoundation` entries.
 *   • 1 key exists here and not there: `hero.videoDescription`.
 *   • `dashboard.lead` differs in wording.
 *
 * Running `npm run build:messages` therefore removes 56 live keys, and every one
 * of them throws `MISSING_MESSAGE` in the browser at render time — next-intl does
 * not fail the build for a missing key. This was verified the hard way: the
 * command was run during the reference-polish pass, wrote 193 keys over the
 * shipped 248, and had to be restored from a backup.
 *
 * ── Why it is kept ──
 *
 * The bilingual-pair structure is genuinely the right design: it makes RU/EN
 * parity impossible to break by construction, which a post-hoc check cannot do.
 * It is worth reviving. Reviving it means reconciling the 57 differences above
 * *first*, in this file, and only then running it — at which point delete this
 * banner.
 *
 * Until then it is maintained as documentation: keys removed from the shipped
 * catalogues are removed here too, with the reason, so that a future
 * reconciliation cannot silently resurrect copy that was deliberately cut. See
 * docs/LANDING_COPY_REMOVALS.md.
 *
 * ── Original intent, still accurate ──
 *
 * Single bilingual source for messages/{ru,en}.json.
 *
 * Every leaf is a [ru, en] pair, so the two files cannot drift structurally —
 * parity is guaranteed by construction rather than checked after the fact.
 * `check:i18n` still runs, because it also catches ICU placeholder mismatches
 * and untranslated copies, which this cannot.
 *
 * Russian is authored first and is the primary language. English is a
 * translation of it, not the other way round.
 *
 * CLAIMS DISCIPLINE — every line here was written against verified code:
 *   - no result figures anywhere (win rate, profit factor, sample size,
 *     Sharpe, P&L, drawdown). Only configured limits and system constants.
 *   - confidence bounds are 0.05–0.95, signal floor 0.20
 *     (bot/learning/belief_updater.py:37,46-47; trading_orchestrator.py:63)
 *   - risk limits 5% / 2% / 5 positions / 2xATR (bot/config.py:66-71)
 *   - T-Invest active (sandbox default), Bybit read-only, Finam not implemented
 *     (bot/broker/registry.py:46-52; providers/finam.py:63-118)
 *   - no ML anywhere; confidence is an EMA over an equal-weighted mean
 *   - no automatic kill switch; the stop is manual (bot/services/bot_engine.py:91)
 *   - Quant has no withdraw/transfer code path at all (bot/broker/base.py:141-219)
 *
 * Run: npm run build:messages
 */
import { writeFile } from "node:fs/promises";

const t = (ru, en) => ({ __ru: ru, __en: en });

const M = {
  seo: {
    title: t(
      "Quant — автоматический торговый оператор для MOEX и Bybit",
      "Quant — automated trading operator for MOEX and Bybit",
    ),
    description: t(
      "Quant анализирует рынок, проверяет стратегию по записанным правилам, измеряет уверенность, ограничивает риск и исполняет сделку через ваш брокерский аккаунт. Начинается с песочницы.",
      "Quant analyses the market, checks the strategy against written rules, measures confidence, limits risk and executes through your broker account. It starts in the sandbox.",
    ),
    ogTitle: t(
      "Рынок создаёт шум. Quant превращает его в решение.",
      "The market makes noise. Quant turns it into a decision.",
    ),
    ogDescription: t(
      "Автоматический торговый оператор для MOEX и Bybit. Закрытое тестирование.",
      "Automated trading operator for MOEX and Bybit. Closed testing.",
    ),
  },

  nav: {
    brand: t("Quant", "Quant"),
    how: t("Как работает", "How it works"),
    dashboard: t("Продукт", "Product"),
    safety: t("Безопасность", "Safety"),
    pricing: t("Тарифы", "Pricing"),
    faq: t("FAQ", "FAQ"),
    ctaPrimary: t("Получить доступ к песочнице", "Get sandbox access"),
    ctaShort: t("Доступ к песочнице", "Sandbox access"),
    menuOpen: t("Открыть меню", "Open menu"),
    menuClose: t("Закрыть меню", "Close menu"),
  },

  common: {
    brokerStatus: {
      active: t("Активен", "Active"),
      sandbox: t("Песочница", "Sandbox"),
      beta: t("Бета", "Beta"),
      validation: t("Проверка", "Validation"),
      planned: t("Планируется", "Planned"),
    },
    strategyStatus: {
      active: t("Активная", "Active"),
      forward: t("Форвард", "Forward"),
      candidate: t("Кандидат", "Candidate"),
      frozen: t("Заморожена", "Frozen"),
    },
    plain: t("Простыми словами", "In plain terms"),
    technical: t("Технически", "Technically"),
    closedTesting: t("Закрытое тестирование", "Closed testing"),
  },

  hero: {
    eyebrow: t(
      "Закрытое тестирование · MOEX · песочница по умолчанию",
      "Closed testing · MOEX · sandbox by default",
    ),
    headline1: t("Рынок создаёт шум.", "The market makes noise."),
    headline2: t("Quant превращает его в решение.", "Quant turns it into a decision."),
    subline: t(
      "Автоматический торговый оператор для MOEX и Bybit: анализирует рынок, проверяет стратегию, ограничивает риск и исполняет сделку через ваш брокерский аккаунт.",
      "An automated trading operator for MOEX and Bybit: it analyses the market, checks the strategy, limits risk and executes through your broker account.",
    ),
    ctaPrimary: t("Получить доступ к песочнице", "Get sandbox access"),
    ctaSecondary: t("Посмотреть как работает", "See how it works"),
    // The proof strip (proof1-5), the three configured limits and
    // `visualCaption` were removed from the hero — see
    // docs/LANDING_COPY_REMOVALS.md. The limits themselves are still published
    // in `#safety` and in the belief-gate node of `#how-it-works`, with their
    // labels attached; nothing removed here was a result.
    videoDescription: t(
      "Абстрактная анимация: частицы собираются в кольцевую диафрагму Quant с одной оранжевой сигнальной точкой.",
      "Abstract animation: particles forming the Quant ring aperture with a single orange signal point.",
    ),
  },

  audience: {
    eyebrow: t("Аудитории", "Audiences"),
    heading: t("Один Quant. Разный уровень контроля.", "One Quant. Different levels of control."),
    lead: t(
      "Продукт один и тот же. Отличается только то, сколько вы хотите видеть и сколько решать сами.",
      "It is the same product throughout. What changes is how much you want to see, and how much you want to decide yourself.",
    ),
    card1Title: t("Новичку", "If you are starting out"),
    card1Body: t(
      "Начните с песочницы: те же сигналы и тот же путь решения, но без реальных денег. Каждую сделку можно подтверждать вручную, пока не появится доверие к системе.",
      "Start in the sandbox: the same signals and the same decision path, without real money. You can confirm every trade by hand until you trust the system.",
    ),
    // card1 routes to #dashboard and card3 to #safety — #brokers is gone, so the
    // link labels had to describe where they actually go.
    card1Link: t("Терминал оператора", "The operator terminal"),
    card2Title: t("Трейдеру", "If you already trade"),
    card2Body: t(
      "Правила записаны и читаемы, режим рынка классифицируется, уверенность измеряется по закрытым сделкам, а риск проверяется до входа. Замороженные стратегии мы публикуем вместе с работающими.",
      "The rules are written down and readable, the market regime is classified, confidence is measured from closed trades, and risk is checked before entry. We publish frozen strategies alongside the working ones.",
    ),
    card2Link: t("Путь решения", "The decision path"),
    card3Title: t("Партнёру и разработчику", "If you are a partner or developer"),
    card3Body: t(
      "Telegram и Dashboard читают одно и то же состояние из общего слоя данных. Ключи шифруются, действия пишутся в журнал, а права на вывод средств не запрашиваются — их просто нет в интерфейсе брокера.",
      "Telegram and the dashboard read the same state from one shared data layer. Keys are encrypted, actions are logged, and withdrawal permissions are never requested — there is no such method in the broker interface at all.",
    ),
    card3Link: t("Ключи и доступы", "Keys and access"),

    /**
     * The fourth audience is the sceptic, and it is the only one of the obvious
     * candidates this product can address without inventing something.
     *
     * "Инвестору" / "Владельцу капитала" both imply a return, and there is no
     * return figure anywhere in this repository to support one. "Команде" implies
     * multi-user access, and there is no team or role model in the product. The
     * sceptic is addressable entirely out of things that are already true, and it
     * is the strongest remaining conversion angle for a product whose whole
     * positioning is what it refuses to claim.
     *
     * Naming win rate / profit factor without a figure is deliberate and is
     * already precedent on this site — see the adjacency-window note beside
     * FORBIDDEN_CLAIMS in scripts/visual-qa.mjs. The gate requires a digit
     * immediately after the term; there is none here and there never will be.
     */
    card4Title: t("Скептику", "If you are sceptical"),
    card4Body: t(
      "Ни win rate, ни profit factor, ни доходности — на этом сайте нет ни одной цифры результата. Замороженные стратегии стоят рядом с работающими, а автоматической остановки в системе нет, и об этом сказано прямо.",
      "No win rate, no profit factor, no return — there is not a single result figure on this site. Frozen strategies sit alongside the working ones, and there is no automatic kill switch, which we say plainly.",
    ),
    card4Link: t("Чего мы не заявляем", "What we do not claim"),
  },

  how: {
    eyebrow: t("Как работает", "How it works"),
    heading: t("Путь от свечи до заявки.", "From candle to order."),
    // `lead`, `rulesNote`, `loopNote` and `principlesHeading` were removed: the
    // section now carries its argument through the six numbered spine nodes
    // rather than three blocks of prose. Every node still carries its own
    // `sourceRef` into the Python codebase, and the belief gate still publishes
    // the three constants below. See docs/LANDING_COPY_REMOVALS.md.
    constantsHeading: t("Границы уверенности", "Confidence bounds"),
    minTradesLabel: t("сделок до движения", "trades before it moves"),
    minConfidenceLabel: t("нижняя граница", "lower bound"),
    maxConfidenceLabel: t("верхняя граница", "upper bound"),
  },

  dashboard: {
    eyebrow: t("Продукт", "Product"),
    heading: t("Терминал оператора, а не витрина.", "An operator terminal, not a showcase."),
    lead: t(
      "Dashboard и Telegram читают одно состояние. Ниже — разделы, которые действительно существуют в продукте.",
      "The dashboard and Telegram read one state. Below are the sections that actually exist in the product.",
    ),
    disclaimer: t(
      "Схема интерфейса. Значения — демонстрационные и не являются результатами торговли.",
      "Interface schematic. Values are illustrative and are not trading results.",
    ),
    // `apiOnlyNote` removed: three caveats about the composition of a mock, in
    // the header of the section whose job is to make the product feel real. The
    // terminal is still labelled a demo in its own chrome and by `demoNote`.
    view1Label: t("Обзор", "Dashboard"),
    view1Desc: t("Состояние движка и последние события", "Engine state and recent events"),
    view2Label: t("Портфель", "Portfolio"),
    view2Desc: t("Позиции и баланс у брокера", "Positions and broker balance"),
    view3Label: t("Сигналы", "Signals"),
    view3Desc: t("Что сработало и что было заблокировано", "What fired and what was blocked"),
    view4Label: t("Бэктест", "Backtest"),
    view4Desc: t("Прогоны на истории и их выгрузка", "Historical runs and their exports"),
    view5Label: t("Аналитика", "Analytics"),
    view5Desc: t("Разрезы по стратегиям и режимам", "Breakdowns by strategy and regime"),
    view6Label: t("Обучение", "Learning"),
    view6Desc: t("Уверенность стратегий и гипотезы", "Strategy confidence and hypotheses"),
    view7Label: t("Настройки", "Settings"),
    view7Desc: t("Ключи брокера и пределы риска", "Broker keys and risk limits"),
    mockChrome: t("Quant · Dashboard", "Quant · Dashboard"),
    mockDemo: t("Демо-данные", "Sample data"),
    mockTabOverview: t("Обзор", "Overview"),
    mockTabPositions: t("Позиции", "Positions"),
    mockTabStrategies: t("Стратегии", "Strategies"),
    mockTabSignals: t("Сигналы", "Signals"),
    mockModeLabel: t("Режим", "Mode"),
    mockModeValue: t("Песочница", "Sandbox"),
    mockColTicker: t("Тикер", "Ticker"),
    mockColSide: t("Сторона", "Side"),
    mockColStrategy: t("Стратегия", "Strategy"),
    mockColGate: t("Шлюз", "Gate"),
    mockColState: t("Состояние", "State"),
    mockStateExecuted: t("Исполнено", "Executed"),
    mockStateBlocked: t("Заблокировано", "Blocked"),
    mockStatePaper: t("Песочница", "Paper"),
    mockGatePassed: t("пройден", "passed"),
    mockGateBelowFloor: t("ниже порога 0.20", "below 0.20 floor"),
    mockGateRiskLimit: t("дневной лимит", "daily limit"),
  },

  telegram: {
    eyebrow: t("Telegram", "Telegram"),
    heading: t("Тот же оператор — в Telegram.", "The same operator, in Telegram."),
    lead: t(
      "Не витрина уведомлений и не упрощённая копия: второй интерфейс к тому же состоянию, тому же движку и той же базе.",
      "Not a notification feed and not a simplified copy: a second interface onto the same state, the same engine and the same database.",
    ),
    /**
     * The four feature blocks (f1–f4) were removed when this became a compact
     * touchpoint rather than a full section. All four restated the lead — f3,
     * "Dashboard и бот читают одни и те же репозитории", is the lead with a
     * heading on it.
     *
     * One fact in them was not elsewhere in this section: f4's "остановка —
     * ручная: автоматического kill switch в системе нет". It is stated at more
     * weight in `#safety`'s limits group (item4), so it did not need preserving
     * here. See docs/LANDING_COPY_REMOVALS.md.
     */
    cardTitle: t("Quant нашёл возможную сделку", "Quant found a possible trade"),
    cardConfidence: t("Уверенность", "Confidence"),
    cardRisk: t("Риск", "Risk"),
    cardRiskValue: t("в пределах лимитов", "within limits"),
    cardStrategy: t("Стратегия", "Strategy"),
    cardExecute: t("Исполнить в песочнице", "Execute in sandbox"),
    cardDismiss: t("Пропустить", "Skip"),
    cardNote: t(
      "Пример карточки. Кнопка исполнения работает в песочнице; вывод в Live — отдельный, ручной шаг.",
      "Example card. The execute button runs in the sandbox; going live is a separate, manual step.",
    ),
  },

  /**
   * ── Removed namespaces: `brokers` and `strategyLab` ──
   *
   * Their sections ("Исполнение" and "Лаборатория стратегий") were removed from
   * the landing page. Every disclosure they carried is accounted for in
   * docs/LANDING_COPY_REMOVALS.md — including the two that are now stated
   * nowhere (Bybit being read-only, Finam being unimplemented), which is a
   * deliberate narrowing rather than a claim: the page no longer says either
   * broker is supported.
   *
   * If a broker list ever returns to this page, the per-adapter status must
   * return with it.
   */


  safety: {
    eyebrow: t("Безопасность", "Safety"),
    heading: t("Quant работает с вашим счётом. Вот границы.", "Quant works with your account. Here are the boundaries."),
    lead: t(
      "Ограничения ниже — не обещания, а свойства кода. Там, где ограничение неполное, мы говорим об этом прямо.",
      "The constraints below are properties of the code, not promises. Where a constraint is incomplete, we say so directly.",
    ),
    item1Title: t("Quant не выводит средства", "Quant cannot withdraw funds"),
    item1Body: t(
      "В интерфейсе брокера, который использует Quant, нет метода вывода или перевода. Не «запрещено настройкой» — такого кода просто не существует. Права на вывод при подключении не нужны.",
      "The broker interface Quant uses has no withdraw or transfer method. Not “disabled by configuration” — the code does not exist. Withdrawal permissions are not needed to connect.",
    ),
    item2Title: t("Пределы риска — до входа", "Risk limits, before entry"),
    item2Body: t(
      "Доля на позицию, дневной убыток, число открытых позиций и стоп по ATR проверяются до обращения к брокеру. Не прошло — заявки не будет.",
      "Share per position, daily loss, number of open positions and the ATR stop are all checked before the broker is called. Fail one and the order is never sent.",
    ),
    item3Title: t("Песочница по умолчанию", "Sandbox by default"),
    item3Body: t(
      "Клиент брокера стартует в режиме песочницы. Переход к реальным деньгам — отдельный осознанный шаг, а не настройка по умолчанию.",
      "The broker client starts in sandbox mode. Moving to real money is a separate, deliberate step, not a default.",
    ),
    item4Title: t("Остановка выполняется человеком", "A person performs the stop"),
    item4Body: t(
      "Движок можно поставить на паузу и остановить из Telegram и из Dashboard. Просадка отслеживается и присылает уведомление, но торговлю сама не останавливает: автоматического kill switch нет.",
      "The engine can be paused and stopped from Telegram and from the dashboard. Drawdown is monitored and sends an alert, but does not halt trading by itself: there is no automatic kill switch.",
    ),
    item5Title: t("Ключи шифруются, действия пишутся", "Keys encrypted, actions logged"),
    item5Body: t(
      "Ключи брокера хранятся зашифрованными (AES-256-GCM) в файле с правами только для владельца, а изменения учётных данных попадают в журнал аудита. Ключи можно отозвать на стороне брокера в любой момент.",
      "Broker keys are stored encrypted (AES-256-GCM) in an owner-only file, and credential changes are written to an audit log. You can revoke the keys on the broker's side at any time.",
    ),
    item6Title: t("Уверенность ограничена", "Confidence is bounded"),
    item6Body: t(
      "Уверенность в стратегии держится в диапазоне 0.05–0.95 и никогда не становится определённостью. Сигнал ниже 0.20 фиксируется, но не исполняется.",
      "Confidence in a strategy stays within 0.05–0.95 and never becomes certainty. A signal below 0.20 is recorded but not executed.",
    ),
    /**
     * `keysCaveat` was removed from the landing page — the vault is opt-in via
     * SECRETS_MASTER_KEY and credentials otherwise stay in a plain `.env`
     * (bot/security/credential_store.py:50-57).
     *
     * It is a *deployment* note: it describes the operator's own server
     * configuration, not anything Quant does to a visitor, and it was the longest
     * piece of small print on the page. It belongs in the deployment docs at the
     * repository root; until it is added there, the fact lives in that Python
     * module and in docs/LANDING_COPY_REMOVALS.md.
     *
     * What must NOT happen: this section may not gain an unqualified "keys are
     * encrypted" claim to replace it. That is the one rewrite here that would be
     * false. The two unconditional limits (item4, item6) are untouched.
     */
  },

  pricing: {
    eyebrow: t("Тарифы", "Pricing"),
    heading: t("Три уровня доступа.", "Three levels of access."),
    lead: t(
      "Оплата пока не подключена. Ниже — планируемая структура, а не действующее предложение.",
      "Billing is not connected yet. Below is the planned structure, not a live offer.",
    ),
    plan1Title: t("Explore", "Explore"),
    plan1Price: t("Бесплатно", "Free"),
    plan1Body: t("Чтобы разобраться, как принимается решение.", "To understand how a decision gets made."),
    plan1Feat1: t("Путь решения целиком", "The full decision path"),
    // Was "Лаборатория стратегий и статусы" — reworded when that section was
    // removed, so the tier no longer promises a page that does not exist.
    plan1Feat2: t("Статусы стратегий", "Strategy statuses"),
    plan1Feat3: t("Документация движка", "Engine documentation"),
    plan1Feat4: t("Без торговли", "No trading"),
    plan2Title: t("Sandbox", "Sandbox"),
    plan2Price: t("Планируется", "Planned"),
    plan2Body: t("Бумажная торговля с полным набором интерфейсов.", "Paper trading with the full set of interfaces."),
    plan2Feat1: t("Песочница с симуляцией исполнения", "Sandbox with simulated fills"),
    plan2Feat2: t("Telegram-бот и карточки сигналов", "Telegram bot and signal cards"),
    plan2Feat3: t("Dashboard и история сигналов", "Dashboard and signal history"),
    plan2Feat4: t("Ручное подтверждение сделок", "Manual trade confirmation"),
    plan3Title: t("Live", "Live"),
    plan3Price: t("Планируется", "Planned"),
    plan3Body: t("Исполнение через ваш брокерский аккаунт.", "Execution through your broker account."),
    plan3Feat1: t("Маршрут T-Invest", "T-Invest route"),
    plan3Feat2: t("Обязательные пределы риска", "Mandatory risk limits"),
    plan3Feat3: t("Журнал аудита", "Audit log"),
    plan3Feat4: t("Ручная остановка движка", "Manual engine stop"),
    // The five Live gates and `ctaNote` were removed: a form-shaped block of empty
    // checkboxes directly under the commercial ask, every item of which is stated
    // where it is load-bearing instead — #safety for the withdrawal/risk/stop
    // guarantees, the Live card in #access for the key and consent, and this
    // section's own lead for "payment is not connected".
    cta: t("Запросить доступ", "Request access"),
  },

  faq: {
    heading: t("Вопросы", "Questions"),
    q1: t("Это AI?", "Is this AI?"),
    a1: t(
      "Нет — ни в смысле нейросетей, ни в смысле языковых моделей. В проекте нет ни одной ML-библиотеки. Правила записаны заранее и читаемы, а «уверенность» — это сглаженное среднее из win rate, profit factor и expectancy, которое обновляется после каждой закрытой сделки.",
      "No — not neural networks, and not language models. There is not a single ML library in the project. The rules are written in advance and readable, and “confidence” is a smoothed mean of win rate, profit factor and expectancy, updated after each closed trade.",
    ),
    q2: t("Можно ли начать без риска для капитала?", "Can I start without risking capital?"),
    a2: t(
      "Да. Песочница проходит тот же путь решения, что и Live, но исполняет сделки против симулированных цен. Реальные деньги не участвуют, пока вы сами не переключите режим.",
      "Yes. The sandbox runs the same decision path as live, but fills against simulated prices. No real money is involved until you switch the mode yourself.",
    ),
    q3: t("Что такое песочница?", "What is the sandbox?"),
    a3: t(
      "Режим, в котором сигналы, правила и проверки риска работают полностью, а исполнение имитируется: сделка закрывается по наблюдаемой цене с учётом комиссии и проскальзывания. Это способ увидеть поведение системы до того, как доверить ей счёт.",
      "A mode where signals, rules and risk checks all run for real, but execution is simulated: a trade fills at the observed price with commission and slippage applied. It is a way to see how the system behaves before trusting it with an account.",
    ),
    q4: t("Кто принимает решение?", "Who makes the decision?"),
    a4: t(
      "Решение собирается из проверок: правила дают скор, шлюз уверенности сравнивает его с порогом, риск-менеджер считает размер и проверяет лимиты. Любая из проверок может остановить сделку. Вы задаёте пределы и в любой момент можете остановить движок.",
      "The decision is assembled from checks: the rules produce a score, the confidence gate compares it against a floor, the risk manager sizes the position and checks the limits. Any one of them can stop the trade. You set the limits, and you can stop the engine at any point.",
    ),
    q5: t("Можно ли подтверждать сделки вручную?", "Can I confirm trades manually?"),
    a5: t(
      "Да. Ручная заявка проходит через два шага с показом всех параметров перед отправкой. Карточка сигнала в Telegram исполняется в песочнице одной кнопкой.",
      "Yes. A manual order goes through two steps, showing every parameter before it is sent. A signal card in Telegram executes in the sandbox with one button.",
    ),
    q6: t("Где хранятся API-ключи?", "Where are API keys stored?"),
    a6: t(
      "В зашифрованном хранилище (AES-256-GCM) с доступом только у владельца файла; изменения пишутся в журнал аудита. Шифрование включается мастер-ключом — если он не задан при развёртывании, ключи останутся в обычном .env, и это нужно исправить до боевого запуска.",
      "In an encrypted vault (AES-256-GCM) readable only by the file's owner; changes are written to an audit log. Encryption is switched on by a master key — if it is not set at deployment, keys stay in a plain .env, and that must be fixed before any live run.",
    ),
    q7: t("Может ли Quant выводить деньги?", "Can Quant withdraw money?"),
    a7: t(
      "Нет. В брокерском интерфейсе, которым пользуется Quant, вообще нет метода вывода или перевода средств — только заявки, отмена и чтение состояния счёта. Права на вывод при подключении ключей не требуются.",
      "No. The broker interface Quant uses has no withdraw or transfer method at all — only orders, cancellation and reading account state. Withdrawal permissions are not required when connecting keys.",
    ),
    q8: t("Есть ли гарантированная доходность?", "Is there a guaranteed return?"),
    a8: t(
      "Нет. Гарантированной доходности не существует, и мы её не обещаем. Поэтому на сайте нет ни одной цифры результата: торговля сопряжена с риском потери капитала.",
      "No. Guaranteed returns do not exist and we do not promise them. That is why there is not a single performance figure on this site: trading carries the risk of losing capital.",
    ),
    q9: t("Какие рынки поддерживаются?", "Which markets are supported?"),
    a9: t(
      "Сегодня — MOEX через Т-Инвестиции. Bybit подключён только для чтения балансов и позиций; крипто-стратегий в системе пока нет. Финам запланирован, но не реализован.",
      "Today, MOEX through T-Invest. Bybit is connected for reading balances and positions only; there are no crypto strategies in the system yet. Finam is planned but not implemented.",
    ),
    q10: t("Когда доступен Live?", "When is live available?"),
    a10: t(
      "Live открывается вручную и только после песочницы, заданных пределов риска и подтверждённого согласия. Мы не переводим в Live по факту оплаты — сейчас оплата вообще не подключена.",
      "Live is opened by hand, and only after the sandbox, configured risk limits and confirmed consent. We do not move anyone to live on payment — and payment is not connected at all right now.",
    ),
  },

  finalCta: {
    eyebrow: t("Доступ", "Access"),
    heading: t(
      "Начните с песочницы. Перейдите к Live, когда будете готовы.",
      "Start in the sandbox. Move to live when you are ready.",
    ),
    lead: t(
      "Проект в закрытом тестировании: доступ выдаётся вручную, небольшими группами.",
      "The project is in closed testing: access is granted by hand, in small groups.",
    ),
    trust1: t("Без реальных денег на старте", "No real money to begin with"),
    trust2: t("Права на вывод не нужны", "No withdrawal permissions needed"),
    trust3: t("Пределы риска обязательны", "Risk limits are mandatory"),
    liveHeading: t("Уже торгуете и хотите Live?", "Already trading and want live?"),
    liveBody: t(
      "Live-доступ обсуждается отдельно: нужен действующий ключ брокера без прав на вывод и заданные пределы риска.",
      "Live access is discussed separately: it needs a working broker key without withdrawal permissions, and configured risk limits.",
    ),
    liveCta: t("Запросить Live-доступ", "Request live access"),
  },

  accessForm: {
    emailLabel: t("Рабочая почта", "Work email"),
    emailPlaceholder: t("you@example.com", "you@example.com"),
    submit: t("Получить доступ к песочнице", "Get sandbox access"),
    submitting: t("Отправляем…", "Sending…"),
    success: t("Заявка отправлена.", "Request sent."),
    successDetail: t(
      "Доступ выдаётся вручную. Мы напишем, когда откроем следующую группу.",
      "Access is granted by hand. We will write when we open the next group.",
    ),
    successUndelivered: t(
      "Приём заявок ещё не подключён на этом стенде, поэтому адрес нигде не сохранён. Напишите нам напрямую, чтобы попасть в список.",
      "Request intake is not connected on this deployment, so the address has not been stored anywhere. Contact us directly to get on the list.",
    ),
    error: t("Проверьте адрес и попробуйте ещё раз.", "Check the address and try again."),
    networkError: t("Не удалось отправить. Попробуйте позже.", "Could not send. Please try again later."),
    consentNote: t(
      "Отправляя форму, вы соглашаетесь на переписку об этом продукте. Ничего кроме адреса мы не собираем.",
      "By submitting you agree to correspondence about this product. We collect nothing beyond the address.",
    ),
  },

  footer: {
    brand: t("Quant", "Quant"),
    tagline1: t("Автоматический торговый оператор", "Automated trading operator"),
    tagline2: t("с проверяемым путём решения.", "with a decision path you can audit."),
    linkHow: t("Как работает", "How it works"),
    linkSafety: t("Безопасность", "Safety"),
    // `linkStrategies` removed with the strategy-lab section; the product column
    // links to #telegram in its place. Every footer href must resolve to a live
    // section id in app/[locale]/page.tsx — a stale anchor fails silently.
    linkTelegram: t("Telegram", "Telegram"),
    linkContact: t("Связаться", "Contact"),
    buildLabel: t("Сборка", "Build"),
    status: t("Закрытое тестирование", "Closed testing"),
    copyright: t("© 2026 Quant. Закрытое тестирование.", "© 2026 Quant. Closed testing."),
    legal: t(
      "Торговля сопряжена с риском потери капитала. Материалы на сайте не являются индивидуальной инвестиционной рекомендацией.",
      "Trading carries the risk of losing capital. Nothing on this site is individual investment advice.",
    ),
  },
};

function pick(node, locale) {
  if (node && typeof node === "object" && "__ru" in node) return node[`__${locale}`];
  return Object.fromEntries(Object.entries(node).map(([k, v]) => [k, pick(v, locale)]));
}

for (const locale of ["ru", "en"]) {
  await writeFile(`messages/${locale}.json`, JSON.stringify(pick(M, locale), null, 2) + "\n");
}

const count = (n) =>
  "__ru" in n ? 1 : Object.values(n).reduce((a, v) => a + count(v), 0);
console.log(`✓ wrote messages/ru.json and messages/en.json — ${count(M)} keys each`);
