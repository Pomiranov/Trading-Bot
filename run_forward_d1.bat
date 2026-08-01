@echo off
rem QuantFlow: daily forward run osc_range D1 (Task Scheduler, 00:15)
rem
rem ASCII only, on purpose: cmd reads .bat in the OEM codepage (cp866 here), so
rem Cyrillic here would reach the log and Telegram as garbage. Russian wording
rem lives in bot\forward_start_alert.py, which controls its own encoding.
cd /d D:\Trading-Bot-Nik
if not exist logs mkdir logs
set PYTHONIOENCODING=utf-8

rem venv interpreter, not C:\Python314: dependencies live in one place.
set PY=D:\Trading-Bot-Nik\.venv\Scripts\python.exe
set LOG=logs\forward_d1.log

rem --- 0. Run journal: "start", FIRST, before anything that can fail --------
rem Positive evidence that this run existed at all. Until 01.08 the watchdog
rem could only INFER "the run did not happen" from the absence of a fresh bar,
rem and inference from emptiness stayed silent exactly when it mattered: on
rem 01.08 the run slid from slot 00:15 to 11:38 (the machine slept), the bar was
rem in place by check time, and the watchdog said "forward alive". Debt 46.
rem
rem Deliberately BEFORE the docker wait, the DB wait and any config read: this
rem line must be written earlier than everything that can break. Import budget
rem of run_journal.py is stdlib only, for the same reason.
rem
rem A crude ASCII marker goes to the log too. It is for a HUMAN reading the log
rem during diagnosis, NOT for the watchdog predicate: %DATE%/%TIME% are locale
rem dependent, and a predicate must not stand on that. If python itself is
rem missing, the marker is present while the journal line is not - and that
rem difference is what tells "interpreter dead" from "machine slept".
echo [%DATE% %TIME%] run_forward_d1.bat started>> %LOG%
"%PY%" bot\run_journal.py start >> %LOG% 2>&1

rem This marker says "the process below IS the scheduled run", and ONLY this
rem file sets it. bot\run_forward_d1.py writes its "session" journal record only
rem when it is present. Found by the live probe on 01.08: without the marker the
rem replay tests, which build a ForwardRunner in-process, poured 97 "session"
rem lines into the PRODUCTION journal - and the watchdog attaches "session" to
rem the last preceding "start", so a test line could have latched onto a real
rem run and claimed a session the run never saw.
set FWD_IN_SLOT_RUN=1

rem Wait budgets, each defined ONCE. Both are used twice - by the gate and by the
rem text of the Telegram alert - and a number living in two places is the defect
rem class that put the commission rate in eight (PROJECT_STATE section 2a).
rem DAEMON_TRIES x ~6s is DAEMON_WAIT_S; keep them consistent by hand, cmd has no
rem arithmetic worth trusting here.
set DAEMON_TRIES=30
set DAEMON_WAIT_S=180
set DBWAIT_TIMEOUT=450
set DBWAIT_INTERVAL=5

rem Every abort below is LOUD: forward_start_alert.py sends Telegram before we
rem quit. Until 30.07 the abort was silent - a line in the log and exit 1 - so a
rem missed run surfaced only in the 09:00 watchdog message, nine hours later and
rem as a consequence rather than a cause. Principle: the system flags, the human
rem decides (PROJECT_STATE section 9). Exit code stays 1: the RUN did not happen,
rem and LastTaskResult must show it.

rem --- 1. Docker daemon ------------------------------------------------------
rem Docker Desktop starts at user logon, which can be seconds before this task
rem fires - and after hibernation it needs minutes, measured 30.07. "compose" is
rem useless while the daemon itself is down, so wait for it first.
rem 30 x ~6s = ~3 min. CHOSEN, not measured: a daemon that has not come up in
rem three minutes is not coming up slowly, it is not coming up.
set /a TRIES=0
:waitdaemon
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 goto daemonup
set /a TRIES+=1
if %TRIES% GEQ %DAEMON_TRIES% (
    echo [%DATE% %TIME%] docker daemon not up after ~%DAEMON_WAIT_S%s - run aborted>> %LOG%
    rem Space before >> when the last argument is a number. MEASURED 30.07, three
    rem cases: "x 450>>" passes 450 (multi-digit is not a handle), "x 1>>" LOSES
    rem the argument (a standalone single digit IS a file handle), "x 1 >>" passes
    rem it. So 180 and 450 happen to be safe today, and the habit is what keeps a
    rem future one-digit limit from silently arriving as no argument at all.
    "%PY%" bot\forward_start_alert.py docker-daemon %DAEMON_WAIT_S% >> %LOG% 2>&1
    rem Space before >> is MANDATORY here: a standalone single digit IS a file
    rem handle, so "finish 1>>" would pass NO argument and the journal would
    rem record a run that never reported its code. Same lesson as above.
    "%PY%" bot\run_journal.py finish 1 >> %LOG% 2>&1
    exit /b 1
)
rem ping instead of timeout: timeout fails when stdin is redirected, which is how
rem Task Scheduler runs this.
ping -n 7 127.0.0.1 >nul
goto waitdaemon
:daemonup

rem --- 2. Bring the stack up -------------------------------------------------
rem "restart: always" in docker-compose only applies once the daemon is running.
docker compose up -d >> %LOG% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [%DATE% %TIME%] docker compose up -d failed - run aborted>> %LOG%
    "%PY%" bot\forward_start_alert.py docker-compose >> %LOG% 2>&1
    "%PY%" bot\run_journal.py finish 1 >> %LOG% 2>&1
    exit /b 1
)

rem --- 3. Wait for the DB on the HOST side -----------------------------------
rem Was: docker exec trading_db pg_isready. That checks the DB INSIDE the
rem container, bypassing the Docker host port proxy - while the run connects from
rem the host. The gate could therefore pass and the run still fail on the same
rem port. Measured 30.07 11:04: three watchdog attempts got Permission denied
rem (0x0000271D/10013) on localhost (::1) port 5432, i.e. the host-side port was
rem not published yet - a failure class the old gate could not see by
rem construction. db_wait.py connects the way the run does, and logs which
rem address answered, after how many seconds, and the error text of the one that
rem did not.
"%PY%" bot\db_wait.py --timeout %DBWAIT_TIMEOUT% --interval %DBWAIT_INTERVAL% >> %LOG% 2>&1
if %ERRORLEVEL% NEQ 0 (
    rem Space before >> after a numeric argument - see the docker-daemon branch.
    "%PY%" bot\forward_start_alert.py db-timeout %DBWAIT_TIMEOUT% >> %LOG% 2>&1
    "%PY%" bot\run_journal.py finish 1 >> %LOG% 2>&1
    exit /b 1
)

rem --- 4. The run ------------------------------------------------------------
rem Script lives in bot\, not the repo root. Python puts the SCRIPT's directory
rem on sys.path[0], so "from config import ..." resolves while cwd stays at the
rem repo root and the log keeps its existing location.
"%PY%" bot\run_forward_d1.py >> %LOG% 2>&1

rem --- 5. Run journal: "finish" with the run's OWN exit code ----------------
rem RC is captured BEFORE calling python: the journal call overwrites
rem %ERRORLEVEL%, and without this line the run's code would be replaced by the
rem journal's own. The exit code still belongs to the run - LastTaskResult must
rem show what the RUN did, not what the bookkeeping did.
rem
rem The processed Moscow session is NOT written here: this file does not know it.
rem The session convention lives in bot\market_time.py and is available only to
rem the Python run, which writes its own "session" record. Passing it through
rem the .bat would mean either a second copy of the convention or parsing the
rem log. Each writer writes what it knows.
set RC=%ERRORLEVEL%
"%PY%" bot\run_journal.py finish %RC% >> %LOG% 2>&1
exit /b %RC%
