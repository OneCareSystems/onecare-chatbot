"""Optional real-model check: never downloads a model while running the unit suite."""
import numpy as np
import pytest


@pytest.mark.embedding
def test_configured_model_retrieves_english_passages_for_tamil_questions(settings):
    from sentence_transformers import SentenceTransformer

    try:
        model = SentenceTransformer(settings.EMBEDDING_MODEL, local_files_only=True)
    except OSError:
        pytest.skip('Configured multilingual embedding model is not cached; semantic retrieval not verified.')
    passages = [
        'passage: Healthy eating for diabetes includes non-starchy vegetables and balanced meals.',
        'passage: Exercise and physical activity support an active lifestyle at the gym.',
        'passage: General information about pregnancy and maternal healthcare.',
    ]
    queries = [
        'query: நீரிழிவு நோயாளிகள் என்ன உணவுகளைச் சாப்பிடலாம்?',
        'query: உடற்பயிற்சி மூலம் ஆரோக்கியமாக வாழ்வது எப்படி?',
        'query: கர்ப்ப காலத்தில் ஆரோக்கியமாக இருக்க என்ன செய்ய வேண்டும்?',
    ]
    docs = model.encode(passages, normalize_embeddings=True)
    vectors = model.encode(queries, normalize_embeddings=True)
    assert list(np.argmax(vectors @ docs.T, axis=1)) == [0, 1, 2]
