"""Page routes. Three of them, and none renders data server-side.

``dashboard.html`` contains no Jinja expression other than ``url_for`` — the
dashboard is a client-rendered SPA and the server's only job here is to hand over
a shell with a nonce and an asset version. Keeping it that way is deliberate: it
is why the whole visual redesign needed no change to a Python template.

The Mini App gets its own route with its own stylesheet scope, so its ``:root``
block and its ``pulse`` keyframe can no longer leak into the operational document.
"""

from __future__ import annotations

import logging
import secrets

from flask import Blueprint, Flask, g, redirect, render_template, send_from_directory, url_for

logger = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)

_engine = None
_asset_version = "0"


def register_views(app: Flask, *, engine, asset_version: str) -> None:
    global _engine, _asset_version
    _engine = engine
    _asset_version = asset_version
    app.register_blueprint(views_bp)


def _shell_context() -> dict:
    """Everything the shell needs, and nothing that is data.

    The CSP nonce is minted per response so the one inline bootstrap script can be
    allowed without ``'unsafe-inline'`` — which the previous policy granted to
    every script on the page, materially weakening it against the 31 unescaped
    ``innerHTML`` sinks that existed alongside it.
    """
    nonce = getattr(g, "qf_csp_nonce", None)
    if nonce is None:
        nonce = secrets.token_urlsafe(16)
        g.qf_csp_nonce = nonce
    return {"asset_version": _asset_version, "csp_nonce": nonce}


@views_bp.get("/")
def index():
    from security.session_auth import current_principal

    if current_principal() is None:
        return redirect(url_for("views.login"))
    return render_template("dashboard.html", **_shell_context())


@views_bp.get("/login")
def login():
    from security.session_auth import current_principal, session_service

    if current_principal() is not None:
        return redirect(url_for("views.index"))

    svc = session_service()
    # A deployment with no operator yet must say so. A login form that cannot
    # possibly succeed, with a generic "wrong password", is a support call.
    has_users = svc.has_any_user() if svc is not None else False
    return render_template(
        "login.html",
        has_users=has_users,
        db_available=_engine is not None,
        **_shell_context(),
    )


@views_bp.get("/miniapp")
@views_bp.get("/miniapp/")
def miniapp_index():
    """Quant Hunter, on its own route.

    It was a nav item in the operational rail, one keystroke from Learning, and
    its 67 KB of assets loaded eagerly on every dashboard page load — 21 % of the
    local payload for a hidden view. Here it is a separate document, so the
    operational shell no longer loads it at all.
    """
    from pathlib import Path

    return send_from_directory(
        str(Path(__file__).resolve().parent / "static" / "miniapp"), "index.html"
    )


@views_bp.get("/miniapp/<path:filename>")
def miniapp_static(filename: str):
    from pathlib import Path

    return send_from_directory(
        str(Path(__file__).resolve().parent / "static" / "miniapp"), filename
    )
