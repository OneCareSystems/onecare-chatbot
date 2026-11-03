import json

from django.conf import settings  # type: ignore[reportMissingModuleSource]
from django.http import JsonResponse  # type: ignore[reportMissingModuleSource]
from django.views.decorators.csrf import csrf_exempt  # type: ignore[reportMissingModuleSource]
from django.views.decorators.http import require_http_methods  # type: ignore[reportMissingModuleSource]

from knowledgebase.errors import ValidationFailed
from knowledgebase.views import json_errors
from onecare_chat.service_auth import require_service_token

from . import service


@csrf_exempt
@require_service_token
@require_http_methods(["POST"])
@json_errors
def chat_query(request):
    """Spring Boot -> Django. Body: {"query": "..."}. Patients are anonymous: no user id is needed or used.
    The public rate limit (20 req/min/IP) and the first input validation belong to the Spring endpoint
    POST /api/chatbot/query; this is a defensive second check."""
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        raise ValidationFailed("The request body must be JSON.") from None
    query = payload.get("query") if isinstance(payload, dict) else None
    if not isinstance(query, str):
        raise ValidationFailed("'query' is required.")
    query = query.strip()
    if not query:
        raise ValidationFailed("'query' is required.")
    limit = getattr(settings, "CHAT_MAX_QUERY_CHARS", 500)
    if len(query) > limit:
        raise ValidationFailed(f"'query' must be at most {limit} characters.")
    return JsonResponse(service.process_query(query), json_dumps_params={"ensure_ascii": False})