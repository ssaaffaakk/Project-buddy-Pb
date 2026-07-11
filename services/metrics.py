"""
Prometheus metrics — request-level RED metrics plus domain gauges.

Exposed at GET /metrics in the standard text exposition format, ready for a
Prometheus scrape + Grafana dashboard. When METRICS_TOKEN is set in the
environment, the endpoint requires it (?token=... or X-Metrics-Token header);
leave it unset in development for open access.

Collectors live at module level so repeated create_app() calls (tests, the
Flask reloader) never double-register on the default registry.
"""

import hmac
import os
import time
import logging

from flask import Response, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest,
)

logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter(
    "pb_http_requests_total",
    "HTTP requests processed",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "pb_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)
USERS_TOTAL = Gauge("pb_users_total", "Registered users")
PROJECTS_OPEN = Gauge("pb_projects_open", "Projects currently open")
ACTIVITY_EVENTS_TOTAL = Gauge("pb_activity_events_total", "Analytics events recorded")


def _endpoint_label():
    """Route pattern (e.g. '/project/<int:project_id>'), never the raw path —
    raw paths would explode label cardinality."""
    if request.url_rule is not None:
        return request.url_rule.rule
    return "unmatched"


def _refresh_domain_gauges():
    from models import ActivityEvent, Project, User
    USERS_TOTAL.set(User.query.count())
    PROJECTS_OPEN.set(Project.query.filter_by(status="open").count())
    ACTIVITY_EVENTS_TOTAL.set(ActivityEvent.query.count())


def init_metrics(app):
    @app.before_request
    def _start_timer():
        g._metrics_start = time.perf_counter()

    @app.after_request
    def _record_request(response):
        # Static files and the scrape itself would drown the useful signal.
        if request.path == "/metrics" or request.path.startswith("/static/"):
            return response
        try:
            endpoint = _endpoint_label()
            REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
            start = getattr(g, "_metrics_start", None)
            if start is not None:
                REQUEST_LATENCY.labels(request.method, endpoint).observe(
                    time.perf_counter() - start
                )
        except Exception:
            logger.exception("metrics recording failed")
        return response

    @app.route("/metrics")
    def metrics():
        token = os.environ.get("METRICS_TOKEN", "")
        if token:
            supplied = (request.args.get("token")
                        or request.headers.get("X-Metrics-Token", ""))
            if not hmac.compare_digest(supplied, token):
                return Response("forbidden", status=403, mimetype="text/plain")
        try:
            _refresh_domain_gauges()
        except Exception:
            logger.exception("domain gauge refresh failed")
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
