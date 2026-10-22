from unittest import mock

from knowledgebase.embedding import preload_embedder


def test_preload_warms_existing_embedder_before_requests(settings):
    settings.KB_PRELOAD_EMBEDDER = True
    with mock.patch('knowledgebase.embedding.get_embedder') as get:
        preload_embedder()
    get.return_value.embed_query.assert_called_once_with('clinic information')


def test_preload_is_optional(settings):
    settings.KB_PRELOAD_EMBEDDER = False
    with mock.patch('knowledgebase.embedding.get_embedder') as get:
        preload_embedder()
    get.assert_not_called()
