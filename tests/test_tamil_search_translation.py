from unittest import mock

from chat_pipeline import search

QUERY = '\u0ba8\u0bc0\u0bb0\u0bbf\u0bb4\u0bbf\u0bb5\u0bc1 \u0b89\u0ba3\u0bb5\u0bc1'


def test_tamil_search_merges_translated_hits_and_keeps_best_score(settings):
    settings.CHAT_TRANSLATE_TAMIL_SEARCH = True
    original = {'chunk_id': 1, 'score': .8}
    improved = {'chunk_id': 1, 'score': .9}
    diabetes = {'chunk_id': 2, 'score': .95}
    client = mock.Mock()
    client.complete.return_value = 'diabetes food'
    with mock.patch('chat_pipeline.search.retrieval.search', side_effect=[[original], [improved, diabetes]]) as retrieve, \
            mock.patch('chat_pipeline.llm.get_llm_client', return_value=client):
        assert search._worker(QUERY, 5) == [diabetes, improved]
    assert retrieve.call_args_list == [mock.call(QUERY, k=5), mock.call('diabetes food', k=5)]


def test_tamil_translation_failure_preserves_original_hits(settings):
    settings.CHAT_TRANSLATE_TAMIL_SEARCH = True
    hits = [{'chunk_id': 1, 'score': .9}]
    with mock.patch('chat_pipeline.search.retrieval.search', return_value=hits), \
            mock.patch('chat_pipeline.llm.get_llm_client', side_effect=RuntimeError):
        assert search._worker(QUERY, 5) == hits


def test_english_search_does_not_call_translation(settings):
    settings.CHAT_TRANSLATE_TAMIL_SEARCH = True
    with mock.patch('chat_pipeline.search.retrieval.search', return_value=[]), \
            mock.patch('chat_pipeline.llm.get_llm_client') as client:
        assert search._worker('diabetes food', 5) == []
    client.assert_not_called()
