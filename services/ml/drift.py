"""
Feature-drift monitoring for the recommender.

The model was trained on one snapshot of (user, project) pairs; as the
platform grows, the live population's feature distribution moves. This module
rebuilds the current pair-feature population, compares each feature's mean
against the training distribution (standardized shift, |Δmean| / train_std),
and writes artifacts/drift.json. The Prometheus gauge pb_model_drift_score
and the model card read that file.

Thresholds: max-z < 2 → ok · < 3 → warn · ≥ 3 → drift (retrain or roll back).
"""

import json
import logging
import os
from datetime import datetime, timezone
from itertools import islice

import numpy as np

logger = logging.getLogger(__name__)

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
DRIFT_PATH = os.path.join(ARTIFACT_DIR, "drift.json")

MAX_PAIRS = 2000
WARN_Z, DRIFT_Z = 2.0, 3.0


def _current_pairs():
    """Yield feature vectors for the live serving population
    (every user × every open project, capped at MAX_PAIRS)."""
    from models import Project, User, UserCourse, UserInterest, UserSkill
    from services.ml import embeddings
    from services.ml.features import build_project_profile, build_user_profile, pair_features

    now = datetime.now(timezone.utc)
    projects = Project.query.filter_by(status="open").all()
    if not projects:
        return
    project_profiles = [
        build_project_profile(p, now, vec=embeddings.embed(embeddings.project_text(p)))
        for p in projects
    ]

    def gen():
        for user in User.query.all():
            interests = UserInterest.query.filter_by(user_id=user.id).all()
            skills = UserSkill.query.filter_by(user_id=user.id).all()
            courses = UserCourse.query.filter_by(user_id=user.id).all()
            u_vec = embeddings.embed(embeddings.user_text(user, interests, skills, courses))
            u = build_user_profile(user, interests, skills, courses, vec=u_vec)
            for pp in project_profiles:
                yield pair_features(u, pp)

    yield from islice(gen(), MAX_PAIRS)


def compute_drift():
    """Compare live feature means against the training snapshot; persist and
    return the report, or None when there is no baseline/population."""
    from services.ml.features import FEATURE_NAMES
    from services.ml.recommender import load_metrics

    metrics = load_metrics()
    baseline = (metrics or {}).get("feature_stats")
    if not baseline:
        logger.info("drift check skipped: no training feature_stats baseline")
        return None

    X = np.array(list(_current_pairs()), dtype=float)
    if X.size == 0:
        logger.info("drift check skipped: no serving population")
        return None

    per_feature = {}
    for i, name in enumerate(FEATURE_NAMES):
        train = baseline.get(name)
        if not train:
            continue
        cur_mean = float(X[:, i].mean())
        std = train["std"] or 1e-9
        z = abs(cur_mean - train["mean"]) / std
        per_feature[name] = {
            "train_mean": train["mean"],
            "current_mean": round(cur_mean, 6),
            "z": round(float(z), 3),
        }

    score = max((f["z"] for f in per_feature.values()), default=0.0)
    status = "ok" if score < WARN_Z else ("warn" if score < DRIFT_Z else "drift")
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_pairs": int(X.shape[0]),
        "score": round(score, 3),
        "status": status,
        "model_version": (metrics or {}).get("version"),
        "features": per_feature,
    }

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    with open(DRIFT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    log = logger.warning if status != "ok" else logger.info
    log("model drift %s: score=%.2f over %d pairs", status, score, X.shape[0])
    return report


def load_drift():
    """Last drift report, or None. Never raises."""
    try:
        with open(DRIFT_PATH) as f:
            return json.load(f)
    except Exception:
        return None
