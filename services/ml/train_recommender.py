"""
Train the teammate/project recommender.

Dataset construction (from real signals in the DB):
  positive (label 1) — the user is an active member of, or has applied to, the
      project. These are genuine "this user fit this project" observations.
  negative (label 0) — a sampled (user, project) pair with no such interaction.

We engineer features per pair (services/ml/features.py), train a logistic
regression, and evaluate leakage-free with out-of-fold cross-validation
(ROC-AUC + PR-AUC). The fitted pipeline and a metrics "model card" are saved
to services/ml/artifacts/ for serving.

Run standalone:      python -m services.ml.train_recommender
Or via Flask CLI:    flask train-recommender
"""

import os
import json
import random
from datetime import datetime, timezone

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, average_precision_score
import joblib

from models import User, Project, ProjectMember, Application, UserInterest, UserSkill, UserCourse
from services.ml.features import (
    FEATURE_NAMES, pair_features, build_user_profile, build_project_profile,
)
from services.ml import embeddings

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "recommender.joblib")
METRICS_PATH = os.path.join(ARTIFACT_DIR, "recommender_metrics.json")

NEGATIVE_RATIO = 3      # sampled negatives per positive
RANDOM_SEED = 42


def _load_profiles():
    """Build user- and project-side feature caches keyed by id."""
    now = datetime.now(timezone.utc)

    interests, skills, courses = {}, {}, {}
    for i in UserInterest.query.all():
        interests.setdefault(i.user_id, []).append(i)
    for s in UserSkill.query.all():
        skills.setdefault(s.user_id, []).append(s)
    for c in UserCourse.query.all():
        courses.setdefault(c.user_id, []).append(c)

    users = {}
    for u in User.query.all():
        ui, us, uc = interests.get(u.id, []), skills.get(u.id, []), courses.get(u.id, [])
        vec = embeddings.embed(embeddings.user_text(u, ui, us, uc))
        users[u.id] = build_user_profile(u, ui, us, uc, vec=vec)

    projects, owners = {}, {}
    for p in Project.query.all():
        vec = embeddings.embed(embeddings.project_text(p))
        projects[p.id] = build_project_profile(p, now, vec=vec)
        owners[p.id] = p.owner_id
    return users, projects, owners


def _build_dataset():
    users, projects, owners = _load_profiles()
    rng = random.Random(RANDOM_SEED)

    # ── positives ────────────────────────────────────────────────────────────
    positives = set()
    src = {"members": 0, "applications": 0}
    for m in ProjectMember.query.filter_by(removed=False).all():
        if m.project_id in projects and owners.get(m.project_id) != m.user_id:
            if (m.user_id, m.project_id) not in positives:
                positives.add((m.user_id, m.project_id))
                src["members"] += 1
    for a in Application.query.all():
        if a.project_id in projects and owners.get(a.project_id) != a.applicant_id:
            if (a.applicant_id, a.project_id) not in positives:
                positives.add((a.applicant_id, a.project_id))
                src["applications"] += 1

    # ── negatives (sampled non-interactions) ─────────────────────────────────
    user_ids = list(users.keys())
    project_ids = list(projects.keys())
    n_neg_target = len(positives) * NEGATIVE_RATIO
    negatives = set()
    attempts = 0
    while len(negatives) < n_neg_target and attempts < n_neg_target * 50:
        attempts += 1
        uid = rng.choice(user_ids)
        pid = rng.choice(project_ids)
        if owners.get(pid) == uid:
            continue
        if (uid, pid) in positives or (uid, pid) in negatives:
            continue
        negatives.add((uid, pid))

    # ── vectorize ────────────────────────────────────────────────────────────
    X, y = [], []
    for (uid, pid) in positives:
        X.append(pair_features(users[uid], projects[pid])); y.append(1)
    for (uid, pid) in negatives:
        X.append(pair_features(users[uid], projects[pid])); y.append(0)

    return np.array(X, dtype=float), np.array(y, dtype=int), {
        "n_users": len(users), "n_projects": len(projects),
        "n_positive": len(positives), "n_negative": len(negatives),
        "positive_source": src,
    }


def _make_pipe():
    return Pipeline([
        # Drop features with no variance in the data (e.g. every project has 5
        # tags) so the scaler/solver stay well-conditioned. Saved in the
        # pipeline, so serving applies the exact same column mask.
        ("var", VarianceThreshold(threshold=0.0)),
        ("scale", StandardScaler()),
        # liblinear is well-suited to this small, dense binary problem and
        # avoids the lbfgs numerical noise on a matrix this size.
        ("clf", LogisticRegression(class_weight="balanced", solver="liblinear",
                                   max_iter=1000, C=1.0)),
    ])


def _cv_auc(X, y, n_splits):
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_SEED)
    oof = cross_val_predict(_make_pipe(), X, y, cv=cv, method="predict_proba")[:, 1]
    return float(roc_auc_score(y, oof)), float(average_precision_score(y, oof))


def train(verbose=True):
    # 1) Build the shared LSA embedding space (the two towers live here).
    emb_docs, emb_dims = embeddings.build_embedding_model()

    # 2) Assemble the labeled (user, project) dataset with all features.
    X, y, meta = _build_dataset()
    if len(y) < 12 or y.sum() < 4 or (len(y) - y.sum()) < 4:
        raise RuntimeError(
            f"Not enough signal to train (samples={len(y)}, positives={int(y.sum())}). "
            "Need more members/applications first."
        )

    n_splits = max(2, min(5, int(y.sum()), int(len(y) - y.sum())))
    sem_idx = FEATURE_NAMES.index("semantic_sim")

    # ── The experiment: baseline vs semantic-only vs full ────────────────────
    # baseline  — hand-engineered overlap features, no embeddings
    X_base = np.delete(X, sem_idx, axis=1)
    base_roc, base_pr = _cv_auc(X_base, y, n_splits)
    # semantic-only — rank purely by embedding cosine similarity (the retriever)
    sem_scores = X[:, sem_idx]
    sem_roc = float(roc_auc_score(y, sem_scores))
    sem_pr = float(average_precision_score(y, sem_scores))
    # full — overlap features + the semantic embedding similarity
    roc_auc, pr_auc = _cv_auc(X, y, n_splits)

    pipe = _make_pipe()

    # Fit the final (full) model on all data for serving.
    pipe.fit(X, y)
    kept = [f for f, keep in zip(FEATURE_NAMES, pipe.named_steps["var"].get_support()) if keep]
    coefs = pipe.named_steps["clf"].coef_[0]
    weights = sorted(
        ({"feature": f, "weight": round(float(w), 4)} for f, w in zip(kept, coefs)),
        key=lambda d: abs(d["weight"]), reverse=True,
    )

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": "LogisticRegression (balanced) + StandardScaler",
        "n_samples": int(len(y)),
        "n_features": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
        "cv_folds": n_splits,
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "random_pr_auc": round(float(y.sum()) / len(y), 4),  # random baseline = positive rate
        # ── the experiment: three approaches, same eval ──────────────────────
        "comparison": [
            {"name": "Rule-based overlap (baseline)", "roc_auc": round(base_roc, 4), "pr_auc": round(base_pr, 4)},
            {"name": "Semantic embeddings only (retriever)", "roc_auc": round(sem_roc, 4), "pr_auc": round(sem_pr, 4)},
            {"name": "Full model (overlap + embeddings)", "roc_auc": round(roc_auc, 4), "pr_auc": round(pr_auc, 4)},
        ],
        "embedding": {"docs": emb_docs, "dims": emb_dims, "method": "TF-IDF + Truncated SVD (LSA)"},
        "feature_weights": weights,
        **meta,
    }

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(pipe, MODEL_PATH)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    if verbose:
        print(f"[recommender] trained on {metrics['n_samples']} pairs "
              f"({metrics['n_positive']} pos / {metrics['n_negative']} neg)")
        print(f"[recommender] LSA embeddings: {emb_docs} docs → {emb_dims} dims")
        print(f"[recommender] baseline ROC-AUC   = {round(base_roc,4)}")
        print(f"[recommender] semantic-only AUC  = {round(sem_roc,4)}")
        print(f"[recommender] FULL ROC-AUC       = {round(roc_auc,4)}  PR-AUC={round(pr_auc,4)}  ({n_splits}-fold CV)")
        print(f"[recommender] saved → {MODEL_PATH}")
    return metrics


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        train()
