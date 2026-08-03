\pset pager off
\echo '======================================================================'
\echo 'Z1. forward_state'
\echo '======================================================================'
\echo ''
\echo '-- Z1.1 число строк ВСЕЙ таблицы (без фильтра по strategy_id)'
\echo '-- SQL: SELECT count(*) AS rows_total, count(DISTINCT ticker) AS tickers, count(DISTINCT strategy_id) AS strategies FROM forward_state;'
SELECT count(*) AS rows_total, count(DISTINCT ticker) AS tickers, count(DISTINCT strategy_id) AS strategies FROM forward_state;

\echo '-- Z1.2 разбивка по стратегиям'
\echo '-- SQL: SELECT strategy_id, count(*) AS rows FROM forward_state GROUP BY 1 ORDER BY 1;'
SELECT strategy_id, count(*) AS rows FROM forward_state GROUP BY 1 ORDER BY 1;

\echo '-- Z1.3 построчно: метка последней обработанной сессии у каждого тикера'
\echo '-- last_candle_time = ВНУТРЕННЯЯ МЕТКА БАРА (UTC); msk_session = МОСКОВСКАЯ ТОРГОВАЯ СЕССИЯ этого бара'
\echo '-- updated_at = момент записи строки прогоном'
\echo '-- SQL: SELECT strategy_id, ticker, last_candle_time, (last_candle_time AT TIME ZONE ''Europe/Moscow'')::date AS msk_session, updated_at FROM forward_state ORDER BY strategy_id, ticker;'
SELECT strategy_id, ticker, last_candle_time,
       (last_candle_time AT TIME ZONE 'Europe/Moscow')::date AS msk_session,
       updated_at
FROM forward_state ORDER BY strategy_id, ticker;

\echo '-- Z1.4 сводка: сколько тикеров на каждой метке'
\echo '-- SQL: SELECT last_candle_time, (last_candle_time AT TIME ZONE ''Europe/Moscow'')::date AS msk_session, count(*) AS tickers FROM forward_state GROUP BY 1,2 ORDER BY 1;'
SELECT last_candle_time, (last_candle_time AT TIME ZONE 'Europe/Moscow')::date AS msk_session,
       count(*) AS tickers
FROM forward_state GROUP BY 1,2 ORDER BY 1;

\echo ''
\echo '======================================================================'
\echo 'Z2. candles, timeframe=1d, ПРЕДИКАТ ПО ВСЕЙ ТАБЛИЦЕ (без списка тикеров)'
\echo 'Область: WHERE timeframe = ''1d''  — и ничего больше.'
\echo '======================================================================'
\echo ''
\echo '-- Z2.0 объём области предиката'
\echo '-- SQL: SELECT count(*) AS rows_1d, count(DISTINCT ticker) AS tickers_1d, min(time) AS min_time, max(time) AS max_time FROM candles WHERE timeframe = ''1d'';'
SELECT count(*) AS rows_1d, count(DISTINCT ticker) AS tickers_1d,
       min(time) AS min_time, max(time) AS max_time
FROM candles WHERE timeframe = '1d';

\echo '-- Z2a МАКСИМАЛЬНАЯ МЕТКА БАРА по всей области'
\echo '-- SQL: SELECT max(time) AS max_bar_label_utc, (max(time) AT TIME ZONE ''Europe/Moscow'')::date AS max_msk_session FROM candles WHERE timeframe = ''1d'';'
SELECT max(time) AS max_bar_label_utc,
       (max(time) AT TIME ZONE 'Europe/Moscow')::date AS max_msk_session
FROM candles WHERE timeframe = '1d';

\echo '-- Z2a(доп) распределение per-ticker максимумов: сколько тикеров стоит на какой метке'
\echo '-- SQL: SELECT mt AS max_bar_label_utc, (mt AT TIME ZONE ''Europe/Moscow'')::date AS max_msk_session, count(*) AS tickers FROM (SELECT ticker, max(time) AS mt FROM candles WHERE timeframe = ''1d'' GROUP BY ticker) x GROUP BY 1,2 ORDER BY 1;'
SELECT mt AS max_bar_label_utc, (mt AT TIME ZONE 'Europe/Moscow')::date AS max_msk_session,
       count(*) AS tickers
FROM (SELECT ticker, max(time) AS mt FROM candles WHERE timeframe = '1d' GROUP BY ticker) x
GROUP BY 1,2 ORDER BY 1;

\echo '-- Z2b число строк с UTC-часом <> 21 (канон метки D1: 21:00 UTC = московская полночь сессии)'
\echo '-- SQL: SELECT count(*) AS rows_hour_ne_21 FROM candles WHERE timeframe = ''1d'' AND EXTRACT(hour FROM time AT TIME ZONE ''UTC'') <> 21;'
SELECT count(*) AS rows_hour_ne_21
FROM candles WHERE timeframe = '1d' AND EXTRACT(hour FROM time AT TIME ZONE 'UTC') <> 21;

\echo '-- Z2b(доп) полное распределение UTC-часа по области'
\echo '-- SQL: SELECT EXTRACT(hour FROM time AT TIME ZONE ''UTC'') AS utc_hour, count(*) AS rows FROM candles WHERE timeframe = ''1d'' GROUP BY 1 ORDER BY 1;'
SELECT EXTRACT(hour FROM time AT TIME ZONE 'UTC') AS utc_hour, count(*) AS rows
FROM candles WHERE timeframe = '1d' GROUP BY 1 ORDER BY 1;

\echo '-- Z2c дубли по паре (тикер, московская сессия)'
\echo '-- SQL: SELECT count(*) AS dup_groups, COALESCE(sum(n-1),0) AS extra_rows FROM (SELECT ticker,(time AT TIME ZONE ''Europe/Moscow'')::date d, count(*) n FROM candles WHERE timeframe = ''1d'' GROUP BY 1,2 HAVING count(*) > 1) x;'
SELECT count(*) AS dup_groups, COALESCE(sum(n-1),0) AS extra_rows
FROM (SELECT ticker,(time AT TIME ZONE 'Europe/Moscow')::date d, count(*) n
      FROM candles WHERE timeframe = '1d' GROUP BY 1,2 HAVING count(*) > 1) x;

\echo '-- Z2c(доп) перечень дублей (пусто = дублей нет)'
\echo '-- SQL: SELECT ticker,(time AT TIME ZONE ''Europe/Moscow'')::date AS msk_session, count(*) AS n FROM candles WHERE timeframe = ''1d'' GROUP BY 1,2 HAVING count(*) > 1 ORDER BY 1,2;'
SELECT ticker,(time AT TIME ZONE 'Europe/Moscow')::date AS msk_session, count(*) AS n
FROM candles WHERE timeframe = '1d' GROUP BY 1,2 HAVING count(*) > 1 ORDER BY 1,2;

\echo '-- Z2d колонки candles: ЕСТЬ ЛИ отметка времени вставки строки'
\echo '-- SQL: SELECT column_name, data_type FROM information_schema.columns WHERE table_name = ''candles'' ORDER BY ordinal_position;'
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'candles' ORDER BY ordinal_position;

\echo '-- Z2(доп) хвост московских сессий области: что есть за последние дни'
\echo '-- SQL: SELECT (time AT TIME ZONE ''Europe/Moscow'')::date AS msk_session, min(time) AS bar_label_utc, count(*) AS rows, count(DISTINCT ticker) AS tickers FROM candles WHERE timeframe = ''1d'' AND time >= ''2026-07-23 00:00:00+00'' GROUP BY 1 ORDER BY 1;'
SELECT (time AT TIME ZONE 'Europe/Moscow')::date AS msk_session,
       min(time) AS bar_label_utc, count(*) AS rows, count(DISTINCT ticker) AS tickers
FROM candles WHERE timeframe = '1d' AND time >= '2026-07-23 00:00:00+00'
GROUP BY 1 ORDER BY 1;

\echo ''
\echo '======================================================================'
\echo 'Z3. forward_catchup_log'
\echo '======================================================================'
\echo ''
\echo '-- Z3.1 число строк'
\echo '-- SQL: SELECT count(*) AS rows FROM forward_catchup_log;'
SELECT count(*) AS rows FROM forward_catchup_log;

\echo '-- Z3.2 все строки целиком (пусто = строк нет)'
\echo '-- SQL: SELECT * FROM forward_catchup_log ORDER BY log_id;'
\x on
SELECT * FROM forward_catchup_log ORDER BY log_id;
\x off
