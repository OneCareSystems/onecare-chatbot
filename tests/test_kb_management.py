import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from knowledgebase.models import KnowledgeDocument as Doc

from .helpers import auth, new_pdf_doc, pdf_file

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]
BASE = '/internal/knowledge-base'


def test_pdf_upload_is_queued_using_the_existing_storage(client):
    response = client.post(BASE, {'file': pdf_file(), 'title': 'Clinic guide'}, **auth())
    assert response.status_code == 201
    doc = Doc.objects.get(pk=response.json()['id'])
    assert (doc.status, doc.source_type, doc.created_by_external_id) == ('PENDING', 'PDF', '42')
    assert doc.storage_path and response.json()['title'] == 'Clinic guide'


def test_invalid_and_oversized_pdf_uploads_are_rejected(client, settings):
    bad = SimpleUploadedFile('fake.pdf', b'not a pdf', content_type='application/pdf')
    assert client.post(BASE, {'file': bad}, **auth()).status_code == 400
    settings.KB_MAX_UPLOAD_BYTES = 10
    assert client.post(BASE, {'file': pdf_file()}, **auth()).status_code == 400
    assert Doc.objects.count() == 0


def web_document():
    return Doc.objects.create(title='Health education', source_type='WEB', status='INDEXED', language='EN',
                              source_url='https://who.int/article?tracking=secret', created_by_external_id='42')


def test_list_pdf_and_web_metadata_with_pagination(client):
    pdf = new_pdf_doc()
    web = web_document()
    response = client.get(BASE, {'pageSize': 1}, **auth())
    assert response.status_code == 200
    page = response.json()
    assert (page['count'], page['page'], page['pageSize'], page['totalPages']) == (2, 1, 1, 2)
    assert page['items'][0]['id'] == web.id
    assert page['items'][0]['sourceUrl'] == 'https://who.int/article'
    assert page['items'][0]['uploadedBy'] == '42'
    assert page['items'][0]['createdAt']
    second = client.get(BASE, {'page': 2, 'pageSize': 1}, **auth()).json()
    assert second['items'][0]['id'] == pdf.id
    assert client.get(BASE, {'page': 3, 'pageSize': 1}, **auth()).json()['items'] == []
    for item in [*page['items'], *second['items']]:
        assert not {'storage_path', 'storagePath', 'content_sha256', 'chunks', 'embeddings'} & item.keys()


def test_type_and_status_filters(client):
    pdf = new_pdf_doc()
    web_document()
    page = client.get(BASE, {'sourceType': 'PDF', 'status': 'PENDING'}, **auth()).json()
    assert page['count'] == 1 and page['items'][0]['id'] == pdf.id
    assert client.get(BASE, {'sourceType': 'WEB', 'status': 'PENDING'}, **auth()).json()['count'] == 0


@pytest.mark.parametrize('params', [
    {'page': 'abc'}, {'page': 0}, {'page': -1}, {'pageSize': 0}, {'pageSize': 101},
    {'pageSize': 'NaN'}, {'sourceType': 'OTHER'}, {'status': 'SECRET'},
])
def test_invalid_filters_and_pagination_are_400(client, params):
    assert client.get(BASE, params, **auth()).status_code == 400


def test_list_requires_service_authentication_and_user_identity(client):
    assert client.get(BASE).status_code == 401
    assert client.get(BASE, **auth(None)).status_code == 400
    assert client.get(BASE, HTTP_AUTHORIZATION='Bearer wrong').status_code == 401


def test_detail_returns_safe_metadata_and_missing_ids_are_404(client):
    doc = new_pdf_doc()
    response = client.get(f'{BASE}/{doc.id}', **auth())
    assert response.status_code == 200
    assert response.json()['id'] == doc.id
    assert response.json()['originalFilename'] == 'doc.pdf'
    assert 'storagePath' not in response.json()
    assert client.get(f'{BASE}/999999', **auth()).status_code == 404
    assert client.get(f'{BASE}/-1', **auth()).status_code == 404
    assert client.delete(f'{BASE}/999999', **auth()).status_code == 404


@pytest.mark.parametrize('kind', ['PDF', 'WEB'])
def test_removed_resources_leave_active_listing_but_remain_auditable(client, kind):
    doc = new_pdf_doc() if kind == 'PDF' else web_document()
    assert client.delete(f'{BASE}/{doc.id}', **auth()).status_code == 204
    assert client.get(BASE, **auth()).json()['count'] == 0
    removed = client.get(BASE, {'status': 'REMOVED'}, **auth()).json()
    assert removed['items'][0]['id'] == doc.id
    assert client.get(f'{BASE}/{doc.id}', **auth()).json()['status'] == 'REMOVED'
    assert client.delete(f'{BASE}/{doc.id}', **auth()).status_code == 204
