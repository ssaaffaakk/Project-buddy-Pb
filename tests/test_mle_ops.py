"""Tests for MLE ops: model versioning/rollback and drift detection."""
import json
import os

import numpy as np
import pytest

from services.ml import drift as drift_mod
from services.ml import train_recommender as tr


@pytest.fixture
def artifact_sandbox(tmp_path, monkeypatch):
    """Point every artifact path at a temp dir so tests never touch the real
    serving model."""
    art = tmp_path / "artifacts"
    art.mkdir()
    monkeypatch.setattr(tr, "ARTIFACT_DIR", str(art))
    monkeypatch.setattr(tr, "MODEL_PATH", str(art / "recommender.joblib"))
    monkeypatch.setattr(tr, "METRICS_PATH", str(art / "recommender_metrics.json"))
    monkeypatch.setattr(tr, "VERSIONS_DIR", str(art / "versions"))
    monkeypatch.setattr(drift_mod, "ARTIFACT_DIR", str(art))
    monkeypatch.setattr(drift_mod, "DRIFT_PATH", str(art / "drift.json"))
    return art


def _fake_artifacts(art, content=b"model-bytes"):
    (art / "recommender.joblib").write_bytes(content)
    (art / "recommender_metrics.json").write_text(json.dumps({"roc_auc": 0.9}))


# ── Versioning / rollback ───────────────────────────────────────────────────────

def test_save_version_archives_and_prunes(artifact_sandbox):
    _fake_artifacts(artifact_sandbox)
    for i in range(7):
        tr._save_version(f"2026010{i}T000000Z")
    versions = tr.list_versions()
    assert len(versions) == tr.KEEP_VERSIONS          # pruned to the cap
    assert versions[0] == "20260106T000000Z"          # newest first


def test_rollback_restores_archived_model(artifact_sandbox):
    _fake_artifacts(artifact_sandbox, b"v1-bytes")
    tr._save_version("v1")
    _fake_artifacts(artifact_sandbox, b"v2-bytes")
    tr._save_version("v2")

    assert (artifact_sandbox / "recommender.joblib").read_bytes() == b"v2-bytes"
    tr.rollback("v1")
    assert (artifact_sandbox / "recommender.joblib").read_bytes() == b"v1-bytes"


def test_rollback_unknown_version_raises(artifact_sandbox):
    with pytest.raises(FileNotFoundError):
        tr.rollback("nope")


# ── Drift detection ─────────────────────────────────────────────────────────────

def _drift_with(monkeypatch, artifact_sandbox, baseline_mean, current_value):
    from services.ml.features import FEATURE_NAMES
    baseline = {name: {"mean": baseline_mean, "std": 1.0} for name in FEATURE_NAMES}
    monkeypatch.setattr("services.ml.recommender.load_metrics",
                        lambda: {"feature_stats": baseline, "version": "test"})
    rows = [[current_value] * len(FEATURE_NAMES)] * 10
    monkeypatch.setattr(drift_mod, "_current_pairs", lambda: iter(np.array(rows)))
    return drift_mod.compute_drift()


def test_drift_ok_when_distribution_stable(artifact_sandbox, monkeypatch):
    report = _drift_with(monkeypatch, artifact_sandbox,
                         baseline_mean=1.0, current_value=1.1)
    assert report["status"] == "ok"
    assert report["score"] < 2.0
    assert os.path.exists(drift_mod.DRIFT_PATH)


def test_drift_flagged_when_distribution_shifts(artifact_sandbox, monkeypatch):
    report = _drift_with(monkeypatch, artifact_sandbox,
                         baseline_mean=1.0, current_value=9.0)
    assert report["status"] == "drift"
    assert report["score"] >= 3.0
    # the persisted report is what /metrics and the model card read
    assert drift_mod.load_drift()["status"] == "drift"


def test_drift_skips_without_baseline(artifact_sandbox, monkeypatch):
    monkeypatch.setattr("services.ml.recommender.load_metrics", lambda: {})
    assert drift_mod.compute_drift() is None


def test_load_drift_never_raises(artifact_sandbox):
    assert drift_mod.load_drift() is None  # file absent → None, no exception
