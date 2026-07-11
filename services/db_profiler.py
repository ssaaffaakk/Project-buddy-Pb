"""
Slow-query logging (DBA observability).

Registers SQLAlchemy engine hooks that time every statement and log the ones
slower than SLOW_QUERY_MS (default 300 ms). Deliberately logs the statement
WITHOUT bound parameters — parameters can contain emails, message bodies, and
password hashes, which must never land in log files.

Enabled by init_db_profiler(app) in create_app(); overhead is one
perf_counter() call per query.
"""

import logging
import time

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("slow_query")

_registered = False


def init_db_profiler(app):
    global _registered
    if _registered:          # create_app can run more than once (tests, CLI)
        return
    _registered = True

    threshold_ms = float(app.config.get("SLOW_QUERY_MS", 300))

    @event.listens_for(Engine, "before_cursor_execute")
    def _start_timer(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start", []).append(time.perf_counter())

    @event.listens_for(Engine, "after_cursor_execute")
    def _log_slow(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get("query_start")
        if not starts:
            return
        elapsed_ms = (time.perf_counter() - starts.pop()) * 1000
        if elapsed_ms >= threshold_ms:
            # statement only — never the parameters (PII)
            logger.warning("slow query %.0fms: %s",
                           elapsed_ms, " ".join(statement.split())[:500])
