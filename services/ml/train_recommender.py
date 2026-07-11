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
VERSIONS_DIR = os.path.join(ARTIFACT_DIR, "versions")
KEEP_VERSIONS = 5       # rollback depth

NEGATIVE_RATIO = 3      # sampled negatives per positive
RANDOM_SEED = 42


def _save_version(stamp):
    """Archive the just-trained artifacts under versions/<stamp>/ and prune
    to the newest KEEP_VERSIONS — this is what `flask rollback-recommender`
    restores from."""
    import shutil
    vdir = os.path.join(VERSIONS_DIR, stamp)
    os.makedirs(vdir, exist_ok=True)
    shutil.copy2(MODEL_PATH, os.path.join(vdir, "recommender.joblib"))
    shutil.copy2(METRICS_PATH, os.path.join(vdir, "recommender_metrics.json"))
    versions = sorted(os.listdir(VERSIONS_DIR), reverse=True)
    for old in versions[KEEP_VERSIONS:]:
        shutil.rmtree(os.path.join(VERSIONS_DIR, old), ignore_errors=True)


def list_versions():
    """Archived model versions, newest first."""
    if not os.path.isdir(VERSIONS_DIR):
        return []
    return sorted(os.listdir(VERSIONS_DIR), reverse=True)


def rollback(version):
    """Restore an archived version as the serving model. Returns the version."""
    import shutil
    vdir = os.path.join(VERSIONS_DIR, version)
    src_model = os.path.join(vdir, "recommender.joblib")
    if not os.path.exists(src_model):
        raise FileNotFoundError(
            f"version {version!r} not found — available: {list_versions()}"
        )
    shutil.copy2(src_model, MODEL_PATH)
    shutil.copy2(os.path.join(vdir, "recommender_metrics.json"), METRICS_PATH)
    return version


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
    X, y, pair_uids = [], [], []
    for (uid, pid) in positives:
        X.append(pair_features(users[uid], projects[pid]))
        y.append(1)
        pair_uids.append(uid)
    for (uid, pid) in negatives:
        X.append(pair_features(users[uid], projects[pid]))
        y.append(0)
        pair_uids.append(uid)

    meta = {
        "n_users": len(users), "n_projects": len(projects),
        "n_positive": len(positives), "n_negative": len(negatives),
        "positive_source": src,
    }
    return (np.array(X, dtype=float), np.array(y, dtype=int),
            np.array(pair_uids, dtype=int), meta)


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
    """Out-of-fold CV: returns (roc_auc, pr_auc, oof_scores)."""
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_SEED)
    oof = cross_val_predict(_make_pipe(), X, y, cv=cv, method="predict_proba")[:, 1]
    return float(roc_auc_score(y, oof)), float(average_precision_score(y, oof)), oof


def _ranking_metrics(scores, y, uids, k_recall=5, k_ndcg=10):
    """Per-user ranking quality from out-of-fold scores.

    ROC-AUC treats every pair independently, but a recommender is judged on
    the ORDER it shows each user — so we also report ranking metrics:
      recall@5 — of a user's true matches, what share lands in their top 5
      NDCG@10  — rank-weighted relevance of the top 10 (1.0 = perfect order)
    Averaged over users that have at least one positive and one negative.
    """
    import math
    from collections import defaultdict

    by_user = defaultdict(list)
    for s, label, uid in zip(scores, y, uids):
        by_user[int(uid)].append((float(s), int(label)))

    recalls, ndcgs = [], []
    for rows in by_user.values():
        n_pos = sum(label for _, label in rows)
        if n_pos == 0 or n_pos == len(rows):
            continue  # ranking is undefined without both classes
        ranked = [label for _, label in sorted(rows, key=lambda t: t[0], reverse=True)]
        recalls.append(sum(ranked[:k_recall]) / n_pos)
        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ranked[:k_ndcg]))
        ideal = sorted(ranked, reverse=True)
        idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal[:k_ndcg]))
        ndcgs.append(dcg / idcg if idcg > 0 else 0.0)

    if not recalls:
        return None
    return {
        "recall_at_5": round(float(np.mean(recalls)), 4),
        "ndcg_at_10": round(float(np.mean(ndcgs)), 4),
        "n_users_evaluated": len(recalls),
    }


def _log_mlflow(metrics):
    """Log the run to MLflow when the package is installed (dev-only,
    see requirements-dev.txt). Silently skipped otherwise."""
    try:
        import mlflow
    except ImportError:
        return
    try:
        mlflow.set_experiment("projectbuddy-recommender")
        with mlflow.start_run():
            mlflow.log_params({
                "model": metrics["model"],
                "n_samples": metrics["n_samples"],
                "n_features": metrics["n_features"],
                "cv_folds": metrics["cv_folds"],
                "negative_ratio": NEGATIVE_RATIO,
            })
            numeric = {"roc_auc": metrics["roc_auc"], "pr_auc": metrics["pr_auc"]}
            if metrics.get("ranking"):
                numeric.update({
                    "recall_at_5": metrics["ranking"]["recall_at_5"],
                    "ndcg_at_10": metrics["ranking"]["ndcg_at_10"],
                })
            mlflow.log_metrics(numeric)
            mlflow.log_artifact(MODEL_PATH)
            mlflow.log_artifact(METRICS_PATH)
        print("[recommender] run logged to MLflow")
    except Exception as e:  # tracking must never fail the training itself
        print(f"[recommender] MLflow logging skipped: {e}")


def train(verbose=True):
    # 1) Build the shared LSA embedding space (the two towers live here).
    emb_docs, emb_dims = embeddings.build_embedding_model()

    # 2) Assemble the labeled (user, project) dataset with all features.
    X, y, pair_uids, meta = _build_dataset()
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
    base_roc, base_pr, _ = _cv_auc(X_base, y, n_splits)
    # semantic-only — rank purely by embedding cosine similarity (the retriever)
    sem_scores = X[:, sem_idx]
    sem_roc = float(roc_auc_score(y, sem_scores))
    sem_pr = float(average_precision_score(y, sem_scores))
    # full — overlap features + the semantic embedding similarity
    roc_auc, pr_auc, oof_full = _cv_auc(X, y, n_splits)

    # Per-user ranking quality on the same out-of-fold scores.
    ranking = _ranking_metrics(oof_full, y, pair_uids)

    pipe = _make_pipe()

    # Fit the final (full) model on all data for serving.
    pipe.fit(X, y)
    kept = [f for f, keep in zip(FEATURE_NAMES, pipe.named_steps["var"].get_support()) if keep]
    coefs = pipe.named_steps["clf"].coef_[0]
    weights = sorted(
        ({"feature": f, "weight": round(float(w), 4)} for f, w in zip(kept, coefs)),
        key=lambda d: abs(d["weight"]), reverse=True,
    )

    # Per-feature training distribution — the drift check (services/ml/drift.py)
    # compares the current serving population against these.
    feature_stats = {
        name: {"mean": round(float(X[:, i].mean()), 6),
               "std": round(float(X[:, i].std()), 6)}
        for i, name in enumerate(FEATURE_NAMES)
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    metrics = {
        "version": stamp,
        "feature_stats": feature_stats,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": "LogisticRegression (balanced) + StandardScaler",
        "n_samples": int(len(y)),
        "n_features": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
        "cv_folds": n_splits,
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "random_pr_auc": round(float(y.sum()) / len(y), 4),  # random baseline = positive rate
        "ranking": ranking,  # recall@5 / NDCG@10 per user, or None if not computable
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
    _save_version(stamp)

    _log_mlflow(metrics)

    if verbose:
        print(f"[recommender] trained on {metrics['n_samples']} pairs "
              f"({metrics['n_positive']} pos / {metrics['n_negative']} neg)")
        print(f"[recommender] LSA embeddings: {emb_docs} docs → {emb_dims} dims")
        print(f"[recommender] baseline ROC-AUC   = {round(base_roc,4)}")
        print(f"[recommender] semantic-only AUC  = {round(sem_roc,4)}")
        print(f"[recommender] FULL ROC-AUC       = {round(roc_auc,4)}  PR-AUC={round(pr_auc,4)}  ({n_splits}-fold CV)")
        if ranking:
            print(f"[recommender] recall@5={ranking['recall_at_5']}  NDCG@10={ranking['ndcg_at_10']}  "
                  f"({ranking['n_users_evaluated']} users)")
        print(f"[recommender] saved → {MODEL_PATH}")
    return metrics


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        train()
