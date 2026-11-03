import json

import numpy as np
import pytest
from sentence_transformers import SentenceTransformer

from vectorstore.model_config import MODEL_NAME, MODEL_REVISION

pytestmark = pytest.mark.embedding          # run as its own CI job


@pytest.fixture(scope="module")
def data():
    with open("tests/fixtures/embedding_pairs.json", encoding="utf-8") as f:
        cfg = json.load(f)
    model = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION)
    en = model.encode([p["en"] for p in cfg["pairs"]], normalize_embeddings=True)
    ta = model.encode([p["ta"] for p in cfg["pairs"]], normalize_embeddings=True)
    return cfg, en, ta


def test_both_languages_embed_in_one_space(data):
    _, en, ta = data
    assert en.shape == ta.shape and en.shape[1] == 768 and np.isfinite(en).all() and np.isfinite(ta).all()


def test_each_tamil_sentence_closest_to_its_english_pair(data):
    _, en, ta = data
    sims = ta @ en.T                                  # rows: Tamil, columns: English
    assert list(sims.argmax(axis=1)) == list(range(len(en)))


def test_pair_similarity_meets_recorded_minimum(data):
    cfg, en, ta = data
    pair_sims = (en * ta).sum(axis=1)
    assert pair_sims.min() >= cfg["min_cosine"], f"lowest pair={pair_sims.min():.3f}"