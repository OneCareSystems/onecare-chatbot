import pytest

from .helpers import auth


@pytest.mark.parametrize("url", ["/internal/health", "/internal/health/"])
def test_health_endpoint_returns_ok_with_or_without_trailing_slash(client, url):
    response = client.get(url, **auth())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_requires_the_service_token(client):
    assert client.get("/internal/health/").status_code == 401
