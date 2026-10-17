from django.conf import settings
from django.utils.module_loading import import_string

_cache = {}


class SentenceTransformerEmbedder:
    """The shared EN/TA model. The chat service (CHAT-04) must use the same class and model name at query time."""

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)

    def count_tokens(self, text):
        return len(self.model.tokenizer.encode(text, add_special_tokens=False))

    def embed_passages(self, texts):
        vectors = self.model.encode([f"passage: {t}" for t in texts], batch_size=settings.KB_EMBED_BATCH,
                                    normalize_embeddings=True, convert_to_numpy=True)
        return vectors.astype("float32")

    def embed_query(self, text):
        return self.model.encode([f"query: {text}"], normalize_embeddings=True, convert_to_numpy=True)[0].astype("float32")


def get_embedder():
    path = settings.KB_EMBEDDER_CLASS
    if path not in _cache:
        _cache[path] = import_string(path)()
    return _cache[path]


def reset_embedder():
    _cache.clear()