import hashlib

import numpy as np


class FakeEmbedder:
    """Deterministic bag-of-words embedder: similar text gives similar vectors. No model download."""
    dim = 64

    def count_tokens(self, text):
        return len(text.split())

    def _vec(self, text):
        v = np.zeros(self.dim, dtype="float32")
        for word in text.lower().split():
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = np.linalg.norm(v)
        return v / norm if norm else v

    def embed_passages(self, texts):
        return np.stack([self._vec(t) for t in texts]).astype("float32")

    def embed_query(self, text):
        return self._vec(text)