import hashlib
import math


class FakeEmbedder:
    """Deterministic bag-of-words embedder: similar text gives similar vectors. No model download."""
    dim = 64

    def count_tokens(self, text):
        return len(text.split())

    def _vec(self, text):
        v = [0.0] * self.dim
        for word in text.lower().split():
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim] += 1.0
        norm = math.sqrt(sum(value * value for value in v))
        return [value / norm for value in v] if norm else v

    def embed_passages(self, texts):
        return [self._vec(text) for text in texts]

    def embed_query(self, text):
        return self._vec(text)