import pytest

from knowledgebase import url_safety
from knowledgebase.errors import ValidationFailed
from knowledgebase.models import KnowledgeDocument as Doc

from .helpers import auth

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]
URL = "/internal/knowledge-base/links"
REAL_SAFE_FETCH = url_safety.safe_fetch
PUBLIC = ["93.184.216.34"]


@pytest.fixture(autouse=True)
def _allowlist(settings, monkeypatch):
    settings.KB_URL_ALLOWLIST = ["who.int"]
    monkeypatch.setattr(url_safety, "_resolve", lambda host: PUBLIC)
    monkeypatch.setattr(url_safety, "safe_fetch", lambda *a, **k: pytest.fail("nothing may be fetched on submission"))


def submit(client, url, user="42"):
    return client.post(URL, {"url": url}, content_type="application/json", **auth(user))


def test_allowlisted_https_url_is_accepted_and_row_is_pending(client):
    r = submit(client, "https://www.who.int/news-room/fact-sheets/detail/malaria")
    assert r.status_code == 202
    doc = Doc.objects.get(pk=r.json()["id"])
    assert doc.status == "PENDING" and doc.source_type == "WEB" and doc.created_by_external_id == "42"


def test_url_outside_allowlist_is_400(client):
    r = submit(client, "https://example.com/page")
    assert r.status_code == 400 and Doc.objects.count() == 0


@pytest.mark.parametrize("bad", [
    "http://localhost/admin", "http://who.int/page", "https://127.0.0.1/", "https://169.254.169.254/latest/meta-data",
    "https://user:pw@who.int/page", "https://who.int:8443/page", "ftp://who.int/file",
])
def test_unsafe_urls_are_400(client, bad):
    assert submit(client, bad).status_code == 400


@pytest.mark.parametrize("ip", ["10.0.0.5", "192.168.1.10", "127.0.0.1", "169.254.169.254", "::1", "fd00::1"])
def test_allowlisted_host_resolving_to_private_ip_is_400(client, monkeypatch, ip):
    monkeypatch.setattr(url_safety, "_resolve", lambda host: [ip])
    assert submit(client, "https://who.int/page").status_code == 400


def test_duplicate_url_is_409_even_with_fragment_or_case_differences(client):
    assert submit(client, "https://who.int/page").status_code == 202
    assert submit(client, "https://WHO.int/page#section").status_code == 409
    assert Doc.objects.count() == 1


class FakeResp:
    def __init__(self, status=200, headers=None, body=b"<html>ok</html>"):
        self.status_code, self.headers, self._body, self.encoding = status, headers or {"Content-Type": "text/html"}, body, "utf-8"

    def iter_content(self, chunk_size=8192):
        yield self._body

    def close(self):
        pass


def test_redirect_to_private_address_is_blocked_at_fetch_time(monkeypatch):
    responses = iter([FakeResp(302, {"Location": "https://169.254.169.254/latest"}), FakeResp()])
    monkeypatch.setattr(url_safety.requests, "get", lambda *a, **k: next(responses))
    monkeypatch.setattr(url_safety, "_resolve", lambda host: ["169.254.169.254"] if host.startswith("169") else PUBLIC)
    with pytest.raises(url_safety.FetchFailed):
        REAL_SAFE_FETCH("https://who.int/start")


def test_redirect_to_non_allowlisted_host_is_blocked(monkeypatch):
    responses = iter([FakeResp(301, {"Location": "https://evil.example/x"}), FakeResp()])
    monkeypatch.setattr(url_safety.requests, "get", lambda *a, **k: next(responses))
    with pytest.raises(url_safety.FetchFailed):
        REAL_SAFE_FETCH("https://who.int/start")


def test_safe_fetch_returns_html_for_a_clean_page(monkeypatch):
    monkeypatch.setattr(url_safety.requests, "get", lambda *a, **k: FakeResp())
    assert "ok" in REAL_SAFE_FETCH("https://who.int/start")