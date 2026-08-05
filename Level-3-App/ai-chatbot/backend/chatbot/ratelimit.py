"""slowapi rate-limit setup (M8) — technical abuse prevention.

One shared Limiter keyed on the client IP. Endpoints opt in with
`@limiter.limit(...)` decorators; the limit strings are read from settings so
they can be tuned via .env without code changes.

This guards against *technical* abuse (brute-force logins, signup spam, chat
cost-bombing). It is deliberately NOT plan-based quota (free/paid monthly
message limits) — that is a future billing-phase feature keyed on
`Tenant.plan` + `UsageEvent`.

Storage is in-memory: correct for a single process. When the backend runs
more than one instance each keeps its own counters, so the effective limit
becomes (limit x instances). Switch to shared counters by passing
`storage_uri="redis://..."` to Limiter — the decorators stay unchanged.
"""

from __future__ import annotations

from chatbot.config import get_settings
from slowapi import Limiter
from slowapi.util import get_remote_address

_settings = get_settings()

# key_func = client IP. `enabled` lets tests (and dev) switch throttling off.
limiter = Limiter(key_func=get_remote_address, enabled=_settings.rate_limit_enabled)


# Dynamic limit providers: slowapi accepts a callable returning the limit
# string, evaluated per request, so tuning a value in .env takes effect
# without re-decorating. `*_args` tolerates slowapi calling them with or
# without the request argument across versions.
def login_limit(*_args: object) -> str:
    return get_settings().rate_limit_login


def register_limit(*_args: object) -> str:
    return get_settings().rate_limit_register


def widget_session_limit(*_args: object) -> str:
    return get_settings().rate_limit_widget_session


def widget_chat_limit(*_args: object) -> str:
    return get_settings().rate_limit_widget_chat
