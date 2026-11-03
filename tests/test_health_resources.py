from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import pytest
from django.core.management import call_command

from chat_pipeline import service
from knowledgebase import url_safety
from knowledgebase.extraction import extract_pdf_text, validate_text
from knowledgebase.health_resources import PDFS, WEBSITES


@pytest.mark.parametrize('url', WEBSITES)
def test_project_websites_use_existing_validation(url, settings, monkeypatch):
    settings.KB_URL_ALLOWLIST = [urlsplit(url).hostname]
    monkeypatch.setattr(url_safety, '_resolve', lambda host: ['8.8.8.8'])
    assert url_safety.validate_submission(url) == url
    settings.KB_URL_ALLOWLIST = []
    with pytest.raises(Exception, match='approved list'):
        url_safety.validate_submission(url)


@pytest.mark.parametrize('filename', PDFS)
def test_local_pdfs_have_extractable_text(filename, settings):
    path = Path(settings.BASE_DIR) / filename
    if not path.exists():
        pytest.skip(f'Project PDF is not present: {filename}')
    assert len(validate_text(extract_pdf_text(path))) > 50


def test_english_sources_reach_tamil_generation_without_language_filter():
    query = 'நீரிழிவு நோயாளிகள் என்ன உணவுகளைச் சாப்பிடலாம்?'
    text = 'Non-starchy vegetables are a foundation for healthy eating.'
    hit = {'chunk_id': 1, 'document_id': 2, 'text': text, 'language': 'EN',
           'score': .95, 'source': WEBSITES[0]}
    generator = mock.Mock(info={}, system_prompt=None)
    generator.generate.return_value = 'மாவுச்சத்து குறைந்த காய்கறிகள் ஆரோக்கியமான உணவின் அடிப்படையாகும்.'
    with mock.patch('chat_pipeline.service.search.similarity_search', return_value=[hit]), \
            mock.patch('chat_pipeline.service.get_generator', return_value=generator):
        response = service.process_query(query)
    generator.generate.assert_called_once_with(query, [hit], 'TA')
    assert response['type'] == 'ANSWER' and response['language'] == 'TA'
    assert response['sources'][0]['url'] == WEBSITES[0]


def test_foreign_clinic_does_not_use_onecare_live_information():
    with mock.patch('chat_pipeline.service.clinic.answer_clinic_fact') as live, \
            mock.patch('chat_pipeline.service.search.similarity_search', return_value=[]):
        assert service.process_query('What are City Hospital clinic hours?')['type'] == 'FALLBACK'
    live.assert_not_called()


def test_citations_only_include_chunks_supplied_to_generation(settings):
    settings.CHAT_CONTEXT_CHUNKS = 1
    hits = [
        {'chunk_id': 1, 'document_id': 3, 'text': 'Healthy eating includes vegetables.',
         'language': 'EN', 'score': .95, 'source': WEBSITES[0]},
        {'chunk_id': 2, 'document_id': 10, 'text': 'Other lifestyle information.',
         'language': 'EN', 'score': .90, 'source': PDFS[1]},
    ]
    with mock.patch('chat_pipeline.service.search.similarity_search', return_value=hits):
        response = service.process_query('Healthy eating tips for diabetes?')
    assert response['type'] == 'ANSWER'
    assert [source['documentId'] for source in response['sources']] == [3]


def test_resource_setup_reuses_existing_documents(settings, tmp_path, monkeypatch):
    from contextlib import nullcontext

    from knowledgebase import services, vector_index
    from knowledgebase.models import KnowledgeDocument

    settings.KB_URL_ALLOWLIST = [urlsplit(url).hostname for url in WEBSITES]
    monkeypatch.setattr(url_safety, '_resolve', lambda host: ['8.8.8.8'])
    for filename in PDFS:
        (tmp_path / filename).write_bytes(b'%PDF-1.4\nplaceholder')
    doc = mock.Mock(pk=42, status='INDEXED', failure_reason='')
    monkeypatch.setattr(vector_index, 'index_lock', nullcontext)
    with mock.patch.object(KnowledgeDocument.objects, 'filter') as query, \
            mock.patch.object(services, 'submit_link') as submit, \
            mock.patch.object(services, 'upload_pdf') as upload:
        query.return_value.first.return_value = doc
        query.return_value.exclude.return_value.first.return_value = doc
        for _ in range(2):
            call_command('setup_health_resources', actor='admin-test', pdf_dir=str(tmp_path))
    submit.assert_not_called()
    upload.assert_not_called()
