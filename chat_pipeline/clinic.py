"""CHAT-07: clinic-fact router. Clinic hours and doctor availability are LIVE data, so they come from the Spring Boot
API (never from the knowledge base). Credential: ONLY the service-to-service token (INT-01). A user or staff JWT is
never accepted by, stored in or forwarded by this module. Hours and availability only: no patient data is read."""
import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .errors import ClinicUnavailable
from .messages import day_name, get_message
from .patterns import first_match, load_patterns, normalize

logger = logging.getLogger(__name__)
HOURS, AVAILABILITY = "HOURS", "AVAILABILITY"


def detect_clinic_intent(query):
    """HOURS, AVAILABILITY or None. Runs all pattern sets (EN, TA, romanised)."""
    facts, text = load_patterns()["clinic_facts"], normalize(query)
    if first_match({AVAILABILITY: facts["availability"]}, text):
        return AVAILABILITY
    if first_match({HOURS: facts["hours"]}, text):
        return HOURS
    return None


def _requested_date(query):
    facts, text = load_patterns()["clinic_facts"], normalize(query)
    today = timezone.localdate()
    if any(p.search(text) for p in facts["tomorrow"]):
        return today + timedelta(days=1)
    return today


class SpringClinicClient:
    """One attempt per call, short timeouts, no retries: a slow Spring cannot cause a retry storm."""

    def __init__(self):
        self.base_url = (getattr(settings, "SPRING_BASE_URL", "") or "").rstrip("/")
        self.token = getattr(settings, "SPRING_SERVICE_TOKEN", "") or ""
        self.timeout = (getattr(settings, "SPRING_CONNECT_TIMEOUT", 2), getattr(settings, "SPRING_READ_TIMEOUT", 3))

    def _get(self, path, params=None):
        if not self.base_url:
            raise ClinicUnavailable("SPRING_BASE_URL is not configured.")
        headers = {"Accept": "application/json"}          # built from scratch: nothing from the incoming request
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = requests.get(self.base_url + path, headers=headers, params=params,
                                    timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as exc:
            logger.error("Spring clinic API unreachable (%s)", exc.__class__.__name__)
            raise ClinicUnavailable("Spring is unreachable or timed out.") from exc
        if response.status_code == 401:
            logger.error("Spring rejected the service credential (HTTP 401). Check SPRING_SERVICE_TOKEN.")
            raise ClinicUnavailable("Spring rejected the service credential.")
        if response.status_code != 200:
            logger.error("Spring clinic API returned HTTP %s", response.status_code)
            raise ClinicUnavailable(f"Spring returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ClinicUnavailable("Spring returned invalid JSON.") from exc
        data = payload.get("data", payload) if isinstance(payload, dict) else None   # accepts ApiResponse or a bare object
        if not isinstance(data, dict):
            raise ClinicUnavailable("Spring returned an unexpected shape.")
        return data

    def get_hours(self):
        path = getattr(settings, "SPRING_CLINIC_HOURS_PATH", "/api/internal/clinic/hours")
        days = self._get(path).get("days")
        if not isinstance(days, list):
            raise ClinicUnavailable("Spring hours response has no 'days'.")
        return [{"day": str(d.get("day", "")), "open": d.get("open"), "close": d.get("close"),
                 "closed": bool(d.get("closed"))} for d in days if isinstance(d, dict) and d.get("day")]

    def get_availability(self, date):
        path = getattr(settings, "SPRING_CLINIC_AVAILABILITY_PATH", "/api/internal/clinic/availability")
        doctors = self._get(path, params={"date": date.isoformat()}).get("doctors")
        if not isinstance(doctors, list):
            raise ClinicUnavailable("Spring availability response has no 'doctors'.")
        result = []
        for d in doctors:                                  # whitelist: name and free-slot count only
            if not isinstance(d, dict) or not d.get("name"):
                continue
            slots = d.get("availableSlots")
            if slots is None and isinstance(d.get("slots"), list):
                slots = len(d["slots"])
            result.append({"name": str(d["name"]), "slots": int(slots or 0)})
        return result


def _format_hours(days, language):
    parts = []
    for d in days:
        name = day_name(d["day"], language)
        if d["closed"] or not d["open"] or not d["close"]:
            parts.append(f"{name}: {get_message('closed', language)}")
        else:
            parts.append(f"{name} {d['open']}-{d['close']}")
    return "; ".join(parts)


def _named_doctors(query, doctors):
    text = normalize(query)
    named = []
    for d in doctors:
        short = normalize(d["name"]).replace("dr.", "").replace("dr ", "").strip()
        if len(short) >= 3 and short in text:
            named.append(d)
    return named


def answer_clinic_fact(query, intent, language, client=None):
    """Returns the localised answer text. Raises ClinicUnavailable on ANY problem: the caller then returns the
    localised fallback, never a knowledge-base answer."""
    client = client or SpringClinicClient()
    if intent == HOURS:
        days = client.get_hours()
        if not days:
            raise ClinicUnavailable("Spring returned no opening hours.")
        return get_message("clinic_hours", language, hours=_format_hours(days, language))
    date = _requested_date(query)
    doctors = client.get_availability(date)
    doctors = _named_doctors(query, doctors) or doctors
    doctors = [d for d in doctors if d["slots"] > 0]
    if not doctors:
        return get_message("availability_none", language, date=date.isoformat())
    listing = ", ".join(f"{d['name']} ({get_message('slots', language, count=d['slots'])})" for d in doctors)
    return get_message("availability", language, date=date.isoformat(), doctors=listing)