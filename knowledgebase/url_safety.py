import ipaddress
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from django.conf import settings

from .errors import ValidationFailed


class FetchFailed(Exception):
    pass


def _resolve(host):
    """Return every IP the host resolves to. Tests replace this function."""
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    except socket.gaierror:
        raise ValidationFailed("The host could not be resolved.") from None


def _is_public(ip_text):
    ip = ipaddress.ip_address(ip_text)
    if getattr(ip, "ipv4_mapped", None):
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast       # blocks private, loopback, link-local (169.254.x.x), reserved


def normalize_url(url):
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    netloc = host if parts.port in (None, 443) else f"{host}:{parts.port}"
    return urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))      # fragment dropped


def strip_query(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))


def validate_submission(url):
    """Validate BEFORE any fetch. Returns the normalized URL or raises ValidationFailed (400)."""
    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        raise ValidationFailed("A valid URL is required.")
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "https":
        raise ValidationFailed("Only HTTPS links are accepted.")
    if parts.username or parts.password:
        raise ValidationFailed("Links with credentials are not accepted.")
    try:
        port = parts.port
    except ValueError:
        raise ValidationFailed("Invalid port in URL.") from None
    if port not in (None, 443):
        raise ValidationFailed("Only the default HTTPS port is accepted.")
    host = (parts.hostname or "").lower()
    if not host:
        raise ValidationFailed("The URL has no host.")
    try:
        ipaddress.ip_address(host)
        raise ValidationFailed("IP addresses are not accepted; use an approved hostname.")
    except ValueError:
        pass
    if not any(host == d or host.endswith("." + d) for d in settings.KB_URL_ALLOWLIST):
        raise ValidationFailed("This website is not on the approved list.")
    for ip in _resolve(host):                          # DNS-based SSRF: every resolved IP must be public
        if not _is_public(ip):
            raise ValidationFailed("The host resolves to a non-public address.")
    return normalize_url(url)


def safe_fetch(url, *, max_redirects=5, timeout=10):
    """Fetch an HTML page. Every hop (the first URL and each redirect target) is fully re-validated."""
    current = url
    for _ in range(max_redirects + 1):
        try:
            current = validate_submission(current)
        except ValidationFailed as exc:
            raise FetchFailed(exc.message) from exc
        try:
            response = requests.get(current, allow_redirects=False, timeout=timeout, stream=True,
                                    headers={"User-Agent": "OneCareKnowledgeBase/1.0"})
        except requests.RequestException as exc:
            raise FetchFailed(f"Request failed: {exc.__class__.__name__}") from exc
        try:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise FetchFailed("Redirect without a Location header.")
                current = urljoin(current, location)
                continue
            if response.status_code >= 400:
                raise FetchFailed(f"The page returned HTTP {response.status_code}.")
            if "html" not in response.headers.get("Content-Type", "").lower():
                raise FetchFailed("The page is not HTML.")
            body, size = [], 0
            for chunk in response.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > settings.KB_FETCH_MAX_BYTES:
                    raise FetchFailed("The page is too large.")
                body.append(chunk)
            return b"".join(body).decode(response.encoding or "utf-8", errors="replace")
        finally:
            response.close()
    raise FetchFailed("Too many redirects.")