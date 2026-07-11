"""Tests for the Prometheus /metrics endpoint (services/metrics.py)."""
import os


def test_metrics_endpoint_exposes_request_metrics(client):
    client.get("/health")  # generate at least one observed request
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "pb_http_requests_total" in body
    assert "pb_http_request_duration_seconds" in body
    assert "pb_users_total" in body


def test_metrics_endpoint_labels_by_route_pattern(client, make_user, make_project, login):
    """Paths with IDs must collapse to the route pattern (bounded cardinality)."""
    owner = make_user("m-owner@example.com")
    pid = make_project(owner)
    login("m-owner@example.com")
    client.get(f"/project/{pid}")

    body = client.get("/metrics").get_data(as_text=True)
    assert "/project/<int:project_id>" in body
    assert f'endpoint="/project/{pid}"' not in body


def test_metrics_token_guard(client, monkeypatch):
    monkeypatch.setitem(os.environ, "METRICS_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 403
    assert client.get("/metrics?token=wrong").status_code == 403
    assert client.get("/metrics?token=s3cret").status_code == 200
    assert client.get("/metrics", headers={"X-Metrics-Token": "s3cret"}).status_code == 200
