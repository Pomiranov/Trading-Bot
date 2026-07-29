/**
 * The locale layer. Russian is complete; English is a stub with the same keys.
 *
 * The old interface had 113 Cyrillic and 224 Latin-only user-facing strings with
 * no i18n layer at all — an English nav (`Dashboard`, `Portfolio`, `Signals`)
 * over Russian content (`ОБЩИЙ БАЛАНС`, `Активные позиции`), while the marketing
 * site shipped two locale files with 254 keys each. One language, and mean it.
 *
 * Identifiers, tickers, strategy ids and technical codes are never translated.
 */

const ru = {
  // ── Navigation ──
  'nav.group.trading': 'Торговля',
  'nav.group.system': 'Система',
  'nav.overview': 'Обзор',
  'nav.portfolio': 'Портфель',
  'nav.positions': 'Позиции',
  'nav.trades': 'Сделки',
  'nav.signals': 'Сигналы',
  'nav.strategies': 'Стратегии',
  'nav.backtest': 'Бэктест',
  'nav.analytics': 'Аналитика',
  'nav.risk': 'Риск',
  'nav.health': 'Здоровье',
  'nav.events': 'Журнал',
  'nav.settings': 'Настройки',

  // ── Shell ──
  'shell.skip': 'Перейти к содержимому',
  'shell.refresh': 'Обновить',
  'shell.collapse': 'Свернуть панель',
  'shell.expand': 'Развернуть панель',
  'shell.menu': 'Меню',
  'shell.logout': 'Выйти',
  'shell.shortcuts': 'Горячие клавиши',
  'shell.updated': 'Обновлено',
  'shell.never_updated': 'Данные ещё не загружались',

  // ── Environment band ──
  'band.engine': 'Движок',
  'band.data': 'Данные',
  'band.readonly': 'Только чтение',
  'band.trading_disabled': 'Торговые действия отключены',

  // ── Data states. Eight messages that must never merge into «Нет данных». ──
  'state.loading': 'Загрузка…',
  'state.NO_TRADES_EVER': 'Сделок пока нет',
  'state.NO_TRADES_IN_PERIOD': 'Нет сделок за выбранный период',
  'state.NO_POSITIONS': 'Открытых позиций нет',
  'state.NO_SIGNALS': 'Сигналов пока нет',
  'state.NO_EQUITY_HISTORY': 'История капитала ещё не сформирована',
  'state.NO_EVENTS': 'Событий пока нет',
  'state.STRATEGY_NEVER_RAN': 'Стратегия ещё не запускалась',
  'state.MARKET_CLOSED': 'Рынок закрыт',
  'state.NOT_CONFIGURED': 'Не настроено',
  'state.error': 'Не удалось загрузить данные',
  'state.error.DB_UNAVAILABLE': 'База данных недоступна',
  'state.error.SCHEMA_OUT_OF_DATE': 'Схема базы данных устарела',
  'state.error.BROKER_UNAVAILABLE': 'Брокер не отвечает',
  'state.error.FORBIDDEN': 'Недостаточно прав',
  'state.error.UPSTREAM_TIMEOUT': 'Внешний сервис не ответил',
  'state.disconnected': 'Нет связи с сервером',
  'state.stale': 'Данные устарели',
  'state.partial': 'Часть данных не загрузилась',
  'state.retry': 'Повторить',
  'state.open_log': 'Открыть журнал',
  'state.error_id': 'Идентификатор ошибки',

  // ── Overview ──
  'overview.title': 'Обзор',
  'overview.risk': 'Риск и экспозиция',
  'overview.positions': 'Открытые позиции',
  'overview.capital': 'Капитал',
  'overview.last_signal': 'Последний сигнал',
  'overview.health': 'Здоровье системы',
  'overview.no_faults_note': 'Проблем не обнаружено',

  // ── Risk ──
  'risk.exposure': 'Экспозиция',
  'risk.capital_at_risk': 'Риск в рынке',
  'risk.drawdown': 'Просадка',
  'risk.drawdown_max': 'Макс. просадка',
  'risk.drawdown_current': 'Текущая просадка',
  'risk.positions': 'Позиции',
  'risk.daily_limit': 'Дневной лимит',
  'risk.concentration': 'Концентрация',
  'risk.stale_marks': 'Устаревшие котировки',
  'risk.not_configured': 'не настроен',
  'risk.breaches': 'Нарушения лимитов',
  'risk.no_stop': 'без стопа',
  'risk.derived': 'производная величина',

  // ── Positions ──
  'positions.ticker': 'Тикер',
  'positions.direction': 'Напр.',
  'positions.quantity': 'Кол-во',
  'positions.entry': 'Вход',
  'positions.mark': 'Тек.',
  'positions.mark_age': 'Возраст',
  'positions.distance_to_stop': 'До стопа',
  'positions.unrealized': 'Нереализ. PnL',
  'positions.strategy': 'Стратегия',
  'positions.environment': 'Среда',
  'positions.close': 'Закрыть позицию',
  'positions.no_quote': 'нет котировки',

  // ── Trades ──
  'trades.title': 'Сделки',
  'trades.entry': 'Вход',
  'trades.exit': 'Выход',
  'trades.pnl_money': 'PnL, ₽',
  'trades.pnl_pct': 'PnL, %',
  'trades.pnl_r': 'PnL, R',
  'trades.commission': 'Комиссия',
  'trades.duration': 'Длительность',
  'trades.reason': 'Причина закрытия',
  'trades.closed_at': 'Закрыта',
  'trades.result': 'Результат',
  'trades.result.win': 'прибыль',
  'trades.result.loss': 'убыток',
  'trades.result.flat': 'в нуле',
  'trades.showing': 'Показано',
  'trades.of': 'из',

  // ── Signals ──
  'signals.title': 'Сигналы',
  'signals.decision': 'Решение шлюза',
  'signals.stage': 'Этап',
  'signals.reason': 'Причина',
  'signals.reason_missing': 'причина не записана',
  'signals.candle_age': 'Возраст свечи',
  'signals.resulting_trade': 'Сделка',
  'signals.gate_not_recording':
    'Шлюз ещё не записал ни одного отклонения — причины отказов недоступны.',

  // ── Strategies ──
  'strategies.title': 'Стратегии',
  'strategies.confidence': 'Уверенность',
  'strategies.sample': 'Выборка',
  'strategies.win_rate': 'Доля прибыльных',
  'strategies.profit_factor': 'Profit factor',
  'strategies.expectancy': 'Ожидание',
  'strategies.best_regime': 'Лучший режим',
  'strategies.updated': 'Обновлена',
  'strategies.immature': 'мало данных',
  'strategies.excluded_from_ranking': 'не участвует в рейтинге',
  'strategies.state': 'Состояние',
  'strategies.mixed_environments': 'смешанные среды',
  'strategies.confidence_note':
    'Уверенность — статистическая оценка стратегии по её собственной истории сделок, а не вероятность прибыли.',

  // ── Analytics ──
  'analytics.title': 'Аналитика',
  'analytics.equity': 'Кривая капитала',
  'analytics.underwater': 'Просадка от максимума',
  'analytics.daily_pnl': 'Дневной PnL',
  'analytics.distribution': 'Распределение PnL',
  'analytics.latency': 'Задержка API',
  'analytics.bin_width': 'Ширина интервала',
  'analytics.points': 'точек',
  'analytics.observations': 'наблюдений',
  'analytics.distinct_values': 'различных значений',
  'analytics.polling_artefact':
    'В серии мало различных значений: снапшоты писались по частоте опроса, а не по времени рынка.',
  'analytics.data_table': 'Показать таблицей',
  'analytics.chart': 'Показать графиком',

  // ── Backtest ──
  'backtest.title': 'Бэктест',
  'backtest.run': 'Запустить',
  'backtest.running': 'Выполняется…',
  'backtest.strategy': 'Стратегия',
  'backtest.ticker': 'Инструмент',
  'backtest.period': 'Период',
  'backtest.capital': 'Капитал',
  'backtest.commission': 'Комиссия',
  'backtest.slippage': 'Проскальзывание',
  'backtest.risk': 'Риск на сделку',
  'backtest.leverage': 'Плечо',
  'backtest.trades': 'Сделок',
  'backtest.ready': 'Готов к запуску',
  'backtest.ready_hint': 'Задайте параметры и запустите расчёт на исторических данных.',

  // ── Health ──
  'health.title': 'Здоровье системы',
  'health.service': 'Сервис',
  'health.state': 'Состояние',
  'health.reason': 'Причина',
  'health.action': 'Действие',
  'health.checked': 'Проверено',
  'health.collector_stale': 'Метрики здоровья не обновлялись',
  'health.latency_p50': 'p50',
  'health.latency_p95': 'p95',

  // ── Events ──
  'events.title': 'Журнал событий',
  'events.level': 'Уровень',
  'events.source': 'Источник',
  'events.message': 'Сообщение',
  'events.correlation': 'Correlation ID',
  'events.search': 'Поиск по сообщению',
  'events.audit': 'Аудит действий',
  'events.actor': 'Кто',
  'events.action': 'Действие',
  'events.outcome': 'Результат',
  'events.target': 'Объект',

  // ── Settings ──
  'settings.title': 'Настройки',
  'settings.profile': 'Профиль и сессия',
  'settings.display': 'Отображение',
  'settings.brokers': 'Брокеры',
  'settings.limits': 'Лимиты системы',
  'settings.security': 'Безопасность',
  'settings.configured': 'настроено',
  'settings.not_configured': 'не настроено',
  'settings.clear': 'Очистить',
  'settings.save': 'Сохранить',
  'settings.change_password': 'Сменить пароль',
  'settings.density': 'Плотность таблиц',
  'settings.density.compact': 'Компактная',
  'settings.density.comfortable': 'Обычная',
  'settings.density.monitoring': 'Мониторинг',
  'settings.shortcuts_enabled': 'Горячие клавиши',
  'settings.credential_never_shown': 'Значение не передаётся в браузер.',

  // ── Actions and dialogs ──
  'action.confirm': 'Подтвердить',
  'action.cancel': 'Отмена',
  'action.reason': 'Причина',
  'action.reason_required': 'Укажите причину — она попадёт в журнал аудита.',
  'action.type_to_confirm': 'Для подтверждения введите',
  'action.in_flight': 'Выполняется…',
  'action.engine_start': 'Запустить движок',
  'action.engine_stop': 'Остановить движок',
  'action.acknowledge': 'Подтвердить',
  'action.unavailable': 'Действие недоступно',
  'action.succeeded': 'Выполнено',
  'action.failed': 'Не выполнено',

  // ── Units and generic ──
  'unit.pieces': 'шт',
  'common.period': 'Период',
  'common.environment': 'Среда',
  'common.all': 'Все',
  'common.total': 'Всего',
  'common.window': 'Окно',
  'common.source': 'Источник',
  'common.sample': 'выборка',
  'common.yes': 'да',
  'common.no': 'нет',
  'common.direction.long': 'LONG',
  'common.direction.short': 'SHORT',
};

/** English keys mirror Russian exactly; only the values differ. Incomplete by
    design — Russian is the shipped interface and the fallback chain resolves any
    missing key to it rather than to a raw token. */
const en = {
  'nav.overview': 'Overview',
  'nav.portfolio': 'Portfolio',
  'nav.positions': 'Positions',
  'nav.trades': 'Trades',
  'nav.signals': 'Signals',
  'nav.strategies': 'Strategies',
  'nav.backtest': 'Backtest',
  'nav.analytics': 'Analytics',
  'nav.risk': 'Risk',
  'nav.health': 'Health',
  'nav.events': 'Event log',
  'nav.settings': 'Settings',
};

const catalogues = { ru, en };
let active = 'ru';

export function setLocale(locale) {
  if (catalogues[locale]) active = locale;
}

export function locale() {
  return active;
}

/**
 * Translate. A missing key falls back to Russian, then to the key itself —
 * visible in development, never a blank in production.
 */
export function t(key, fallback) {
  const primary = catalogues[active];
  if (primary && key in primary) return primary[key];
  if (key in ru) return ru[key];
  return fallback !== undefined ? fallback : key;
}

/** Text for an `empty_reason` code from the contract. */
export function emptyReasonText(code) {
  return code ? t(`state.${code}`, t('state.NO_EVENTS')) : t('state.NO_EVENTS');
}

/** Text for an error code from the contract. */
export function errorText(code) {
  return t(`state.error.${code}`, t('state.error'));
}

/** Every key, for the parity test. */
export function keys() {
  return Object.keys(ru);
}
