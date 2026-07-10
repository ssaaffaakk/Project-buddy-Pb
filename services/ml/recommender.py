"""
Serve the trained recommender: rank open projects for a user by predicted fit.

Loads the fitted pipeline once (cached). If no model artifact exists yet, the
public functions return None so callers can fall back to the rule-based scorer.
"""

import os
import json
import logging
from datetime import datetime, timezone

import numpy as np

from models import User, Project, ProjectMember, Application, UserInterest, UserSkill, UserCourse
from services.ml.features import pair_features, build_user_profile, build_project_profile
from services.ml import embeddings

logger = logging.getLogger(__name__)

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "recommender.joblib")
METRICS_PATH = os.path.join(ARTIFACT_DIR, "recommender_metrics.json")

_model = None
_model_mtime = None


def _load_model():
    """Return the pipeline, reloading if the artifact changed on disk."""
    global _model, _model_mtime
    if not os.path.exists(MODEL_PATH):
        return None
    mtime = os.path.getmtime(MODEL_PATH)
    if _model is None or mtime != _model_mtime:
        try:
            import joblib
            _model = joblib.load(MODEL_PATH)
            _model_mtime = mtime
            logger.info("Recommender model loaded (%s)", MODEL_PATH)
        except Exception as e:  # pragma: no cover
            logger.warning("Could not load recommender model: %s", e)
            return None
    return _model


def model_available():
    return _load_model() is not None


def load_metrics():
    """Return the training metrics 'model card', or None."""
    if not os.path.exists(METRICS_PATH):
        return None
    try:
        with open(METRICS_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def rank_open_projects(user_id, limit=None):
    """Return [(project, score_0_100), ...] for open projects the user could
    join, ranked by the model's predicted fit. Returns None if no model."""
    model = _load_model()
    if model is None:
        return None

    now = datetime.now(timezone.utc)
    user = User.query.get(user_id)
    interests = UserInterest.query.filter_by(user_id=user_id).all()
    skills = UserSkill.query.filter_by(user_id=user_id).all()
    courses = UserCourse.query.filter_by(user_id=user_id).all()
    u_vec = embeddings.embed(embeddings.user_text(user, interests, skills, courses))
    u = build_user_profile(user, interests, skills, courses, vec=u_vec)

    joined = {m.project_id for m in ProjectMember.query.filter_by(user_id=user_id, removed=False).all()}
    applied = {a.project_id for a in Application.query.filter_by(applicant_id=user_id).all()}

    candidates, feats = [], []
    for p in Project.query.filter_by(status="open").all():
        if p.owner_id == user_id or p.id in joined or p.id in applied or p.is_full():
            continue
        candidates.append(p)
        p_vec = embeddings.embed(embeddings.project_text(p))
        feats.append(pair_features(u, build_project_profile(p, now, vec=p_vec)))

    if not candidates:
        return []

    probs = model.predict_proba(np.array(feats, dtype=float))[:, 1]
    ranked = sorted(zip(candidates, probs), key=lambda t: t[1], reverse=True)
    ranked = [(p, round(float(score) * 100, 1)) for p, score in ranked]
    return ranked[:limit] if limit else ranked
