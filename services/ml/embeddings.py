"""
Semantic embeddings for profiles and projects (a two-tower / dual-encoder
retriever built with LSA — Latent Semantic Analysis).

Why LSA and not a big transformer: for a corpus this small (tens of short
documents) and a Flask/Render deploy, TF-IDF + Truncated SVD is the right,
honest tool — it learns a dense latent space where semantically related terms
sit close ("machine learning" ≈ "neural networks") without a 400M-param model
or a torch dependency. The exact same code embeds a user tower and a project
tower into one shared space; matching is cosine similarity.

Artifact: services/ml/artifacts/embeddings.joblib
"""

import os
import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import Normalizer
from sklearn.pipeline import make_pipeline
import joblib

from models import User, Project, UserInterest, UserSkill, UserCourse

logger = logging.getLogger(__name__)

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
EMB_PATH = os.path.join(ARTIFACT_DIR, "embeddings.joblib")

_pipe = None
_pipe_mtime = None


# ── text assembly (one blob per tower) ────────────────────────────────────────

def user_text(user, interests, skills, courses):
    parts = []
    if user is not None:
        if user.bio:
            parts.append(user.bio)
        if user.department:
            parts.append(user.department)
    parts += [i.tag for i in interests]
    parts += [s.skill for s in skills]
    parts += [c.course for c in courses]
    return " . ".join(p for p in parts if p) or "student"


def project_text(project):
    parts = [project.title or "", project.description or ""]
    if project.course:
        parts.append(project.course)
    parts += [t.tag for t in project.topic_tags]
    parts += [s.skill for s in project.required_skills]
    return " . ".join(p for p in parts if p) or "project"


# ── build / load ──────────────────────────────────────────────────────────────

def build_embedding_model():
    """Fit the LSA pipeline on the whole corpus (users + projects) and save it.

    Returns the number of documents and the latent dimensionality."""
    interests, skills, courses = {}, {}, {}
    for i in UserInterest.query.all():
        interests.setdefault(i.user_id, []).append(i)
    for s in UserSkill.query.all():
        skills.setdefault(s.user_id, []).append(s)
    for c in UserCourse.query.all():
        courses.setdefault(c.user_id, []).append(c)

    corpus = [
        user_text(u, interests.get(u.id, []), skills.get(u.id, []), courses.get(u.id, []))
        for u in User.query.all()
    ]
    corpus += [project_text(p) for p in Project.query.all()]

    n_docs = len(corpus)
    if n_docs < 4:
        raise RuntimeError("Not enough text to build embeddings yet.")

    # Latent dimensionality: bounded by corpus size and vocabulary.
    tfidf = TfidfVectorizer(min_df=1, ngram_range=(1, 2), sublinear_tf=True)
    tfidf_matrix = tfidf.fit_transform(corpus)
    n_features = tfidf_matrix.shape[1]
    # Keep the latent rank comfortably below the corpus rank so SVD stays
    # numerically stable (arpack is exact for a matrix this small).
    n_components = int(max(2, min(32, n_docs - 2, n_features - 1)))

    pipe = make_pipeline(
        TfidfVectorizer(min_df=1, ngram_range=(1, 2), sublinear_tf=True),
        TruncatedSVD(n_components=n_components, algorithm="arpack", random_state=42),
        Normalizer(copy=False),  # unit vectors → cosine == dot product
    )
    pipe.fit(corpus)

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(pipe, EMB_PATH)
    logger.info("Embedding model built: %d docs → %d dims", n_docs, n_components)
    return n_docs, n_components


def _load():
    global _pipe, _pipe_mtime
    if not os.path.exists(EMB_PATH):
        return None
    mtime = os.path.getmtime(EMB_PATH)
    if _pipe is None or mtime != _pipe_mtime:
        try:
            _pipe = joblib.load(EMB_PATH)
            _pipe_mtime = mtime
        except Exception as e:  # pragma: no cover
            logger.warning("Could not load embedding model: %s", e)
            return None
    return _pipe


def available():
    return _load() is not None


def embed(text):
    """Return a unit-length embedding vector for a text blob, or None."""
    pipe = _load()
    if pipe is None:
        return None
    return pipe.transform([text])[0]


def embed_many(texts):
    """Embed a list of texts in ONE vectorized transform → list of vectors
    (or None). Callers that embed N documents per request must use this instead
    of N embed() calls — a single transform is dramatically cheaper than N."""
    pipe = _load()
    if pipe is None:
        return None
    if not texts:
        return []
    return list(pipe.transform(texts))


def cosine(a, b):
    """Cosine similarity of two (already unit-normalized) vectors → [-1, 1]."""
    if a is None or b is None:
        return 0.0
    return float(np.dot(a, b))
