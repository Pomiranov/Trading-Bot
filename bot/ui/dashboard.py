"""Dashboard entry point.

This module used to be 751 lines: a Flask app built at module scope, 23 routes,
Sharpe and drawdown arithmetic, DDL execution, hypothesis seeding and
``paper_engine.start()`` — all triggered by importing it.

It is now a launcher. ``app`` is still exported at module level because
``python3 bot/ui/dashboard.py`` and any WSGI server pointed at
``ui.dashboard:app`` expect it, but everything it does is inside
``create_app()``, which performs no DDL and starts no trading thread unless
explicitly told to.

Run:

    python3 bot/ui/dashboard.py                  # normal
    QF_DASHBOARD_READ_ONLY=1 python3 bot/ui/dashboard.py   # safe QA against real data
    python -m qf_platform.migrate                # migrations, separately
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui.app_factory import create_app  # noqa: E402

logger = logging.getLogger(__name__)

app = create_app()


if __name__ == "__main__":
    from config import config

    logging.basicConfig(level=logging.INFO)
    host = config.dashboard.host
    port = config.dashboard.port

    # `debug=True` turns the Werkzeug console into remote code execution. It stays
    # env-gated, and it is refused outright when the app is bound to anything
    # other than loopback — a debug console on 0.0.0.0 is not a debugging aid.
    use_debug = os.getenv("QF_DASHBOARD_DEBUG", "0") == "1"
    if use_debug and host not in {"127.0.0.1", "localhost", "::1"}:
        logger.error(
            "QF_DASHBOARD_DEBUG=1 запрещён при host=%s — консоль Werkzeug "
            "это удалённое выполнение кода. Отладка выключена.", host,
        )
        use_debug = False

    logger.info("Dashboard listening on %s:%s", host, port)
    app.run(host=host, port=port, debug=use_debug, use_reloader=use_debug)
