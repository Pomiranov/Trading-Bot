#!/usr/bin/env node
/**
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
    proof1: t("Песочница", "Sandbox"),
    proof2: t("Telegram", "Telegram"),
    proof3: t("Dashboard", "Dashboard"),
    proof4: t("MOEX + Bybit", "MOEX + Bybit"),
    proof5: t("Пределы риска", "Risk limits"),
    limitsLabel: t("Пределы, заданные до входа", "Limits set before entry"),
    limit1Value: t("5%", "5%"),
    limit1Label: t("на позицию", "per position"),
    limit2Value: t("2%", "2%"),
    limit2Label: t("дневной убыток", "daily loss"),
    limit3Value: t("0.20", "0.20"),
    limit3Label: t("порог сигнала", "signal floor"),
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
    card1Link: t("Что такое песочница", "What the sandbox is"),
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
    card3Link: t("Исполнение и брокеры", "Execution and brokers"),
  },

  how: {
    eyebrow: t("Как работает", "How it works"),
    heading: t("Quant не угадывает. Он проверяет.", "Quant does not guess. It checks."),
    lead: t(
      "Шесть шагов между свечой и заявкой. Каждый можно назвать по имени модуля, который его выполняет.",
      "Six steps between a candle and an order. Each one can be named after the module that performs it.",
    ),
    principlesHeading: t("На чём это стоит", "What this rests on"),
    loopNote: t(
      "После исполнения круг замыкается: решение записывается отдельно от результата и становится входом для следующего обновления уверенности.",
      "After execution the loop closes: the decision is recorded separately from the outcome and becomes the input for the next confidence update.",
    ),
    rulesNote: t(
      "Стратегии osc_range и WRD построчно восходят к книгам Швагера. Базовый набор индикаторных правил — стандартный технический анализ без книжной атрибуции.",
      "The osc_range and WRD strategies trace rule by rule to Schwager. The baseline indicator rule set is standard technical analysis, without book attribution.",
    ),
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
    apiOnlyNote: t(
      "Состояние риска и история сделок доступны через API; отдельными страницами они пока не сделаны.",
      "Risk state and trade history are available over the API; they are not separate pages yet.",
    ),
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
    heading: t("Оператор в кармане.", "The operator in your pocket."),
    lead: t(
      "Тот же движок, та же база. Telegram — не витрина уведомлений, а второй интерфейс к тому же состоянию.",
      "The same engine, the same database. Telegram is not a notification feed — it is a second interface onto the same state.",
    ),
    f1Title: t("Карточка сигнала", "Signal card"),
    f1Body: t(
      "Тикер, сторона, стратегия, режим рынка, уровни и шкала уверенности. Кнопка одна — исполнить в песочнице.",
      "Ticker, side, strategy, market regime, levels and a confidence bar. One button — execute in the sandbox.",
    ),
    f2Title: t("Подтверждение сделки", "Trade confirmation"),
    f2Body: t(
      "Ручная заявка проходит через два шага: параметры показываются целиком, и только после подтверждения уходят брокеру.",
      "A manual order goes through two steps: the parameters are shown in full, and only after confirmation do they reach the broker.",
    ),
    f3Title: t("Синхронизация", "Synchronised state"),
    f3Body: t(
      "Dashboard и бот читают одни и те же репозитории. В боте нет упрощённой или отложенной копии данных.",
      "The dashboard and the bot read the same repositories. There is no simplified or delayed copy in the bot.",
    ),
    f4Title: t("Автоматический режим", "Automatic mode"),
    f4Body: t(
      "Движок можно запустить, поставить на паузу и остановить из чата. Остановка — ручная: автоматического kill switch в системе нет.",
      "The engine can be started, paused and stopped from the chat. The stop is manual: there is no automatic kill switch in the system.",
    ),
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

  brokers: {
    eyebrow: t("Исполнение", "Execution"),
    heading: t("Честный статус каждого маршрута.", "An honest status for every route."),
    lead: t(
      "Мы не отмечаем интеграцию готовой, пока через неё нельзя отправить заявку. Ниже — фактическое состояние адаптеров.",
      "We do not mark an integration as ready until an order can actually go through it. Below is the factual state of each adapter.",
    ),
    tinvestName: t("Т-Инвестиции", "T-Invest"),
    tinvestDetail: t("песочница по умолчанию", "sandbox by default"),
    tinvestBody: t(
      "Рабочий маршрут для MOEX: акции и деривативы. Один клиент обслуживает и песочницу, и Live — по умолчанию включена песочница, переключение делается вручную.",
      "The working MOEX route: equities and derivatives. One client serves both sandbox and live — sandbox is on by default and switching is a manual step.",
    ),
    bybitName: t("Bybit", "Bybit"),
    bybitDetail: t("только чтение", "read-only"),
    bybitBody: t(
      "Подключён для чтения балансов и позиций. Отправка заявок через Bybit не включена, крипто-стратегий в системе пока нет.",
      "Connected for reading balances and positions. Order placement through Bybit is not enabled, and there are no crypto strategies in the system yet.",
    ),
    finamName: t("Финам", "Finam"),
    finamBody: t(
      "Адаптер заведён, методы ещё не реализованы. Второй независимый маршрут для MOEX — после T-Invest.",
      "The adapter exists, the methods are not implemented. A second, independent MOEX route — after T-Invest.",
    ),
    disclosure: t(
      "«Активен» означает, что маршрут проверен от сигнала до заявки. Всё остальное названо своим состоянием.",
      "“Active” means the route has been verified from signal to order. Everything else is named for the state it is actually in.",
    ),
  },

  strategyLab: {
    eyebrow: t("Лаборатория стратегий", "Strategy lab"),
    heading: t(
      "Стратегии продвигаются доказательствами, а не обещаниями.",
      "Strategies advance on evidence, not promises.",
    ),
    lead: t(
      "Стратегия проходит стадии в одну сторону и может остановиться на любой. Замороженные мы не прячем.",
      "A strategy moves through the stages in one direction and can stop at any of them. We do not hide the frozen ones.",
    ),
    ladderHeading: t("Стадии", "Stages"),
    activeDesc: t(
      "Появляется только после форварда и допуска к Live. Выдаётся вручную.",
      "Granted only after a forward run and admission to live. Assigned by hand.",
    ),
    forwardDesc: t(
      "Работает на живых данных, исполнение остаётся в песочнице.",
      "Runs on live data, with execution kept in the sandbox.",
    ),
    candidateDesc: t(
      "Прошла бэктест, ожидает форварда.",
      "Passed backtest, waiting for a forward run.",
    ),
    frozenDesc: t(
      "Развитие остановлено. История остаётся опубликованной.",
      "Development stopped. The history stays published.",
    ),
    currentStateNote: t(
      "Active-стратегии появляются только после форварда и допуска к Live. Сейчас публично показаны реальные состояния: Forward и Frozen.",
      "Active strategies appear only after a forward run and admission to live. What is shown publicly right now are the real states: Forward and Frozen.",
    ),
    disclosure: t(
      "Статусы ведутся вручную в исследовательском журнале — это не поле в базе, и автоматической заморозки в системе нет.",
      "Statuses are maintained by hand in the research journal — this is not a database field, and there is no automatic freeze in the system.",
    ),
    noMetricsNote: t(
      "Мы не публикуем цифры доходности. Статус — и есть информация.",
      "We do not publish performance figures. The status is the information.",
    ),
    tableStrategy: t("Стратегия", "Strategy"),
    tableMarket: t("Рынок", "Market"),
    tableTimeframe: t("Таймфрейм", "Timeframe"),
    tableStatus: t("Статус", "Status"),
    tableUpdated: t("Обновлено", "Updated"),
  },

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
    keysCaveat: t(
      "Честная оговорка: шифрование хранилища включается мастер-ключом. Если он не задан при развёртывании, учётные данные останутся в обычном .env — это состояние по умолчанию для локальной установки, и его нужно менять перед боевым запуском.",
      "An honest caveat: vault encryption is switched on by a master key. If it is not set at deployment, credentials stay in a plain .env — that is the default for a local install, and it must be changed before any live run.",
    ),
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
    plan1Feat2: t("Лаборатория стратегий и статусы", "Strategy lab and statuses"),
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
    liveGatesHeading: t("Live открывается только при этих условиях", "Live opens only under these conditions"),
    liveGate1: t("Действующий ключ брокера", "A working broker key"),
    liveGate2: t("Без прав на вывод средств", "No withdrawal permissions"),
    liveGate3: t("Заданные пределы риска", "Risk limits configured"),
    liveGate4: t("Подтверждённое согласие", "Confirmed consent"),
    liveGate5: t("Доступная остановка", "A reachable stop"),
    cta: t("Запросить доступ", "Request access"),
    ctaNote: t("Ничего из перечисленного сейчас не тарифицируется.", "Nothing listed here is billable today."),
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
    linkStrategies: t("Стратегии", "Strategies"),
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
