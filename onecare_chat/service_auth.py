import hmac
from functools import wraps

from django.conf import settings
from django.http import JsonResponse

from knowledgebase.validators import clean_external_user_id


def require_service_token(view):
    """Only Spring Boot (holding the shared token) may call the chatbot APIs."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        header = request.headers.get("Authorization", "")
        supplied = header[7:] if header.startswith("Bearer ") else ""
        if not supplied or not hmac.compare_digest(supplied, settings.CHATBOT_SERVICE_TOKEN):
            return JsonResponse({"detail": "Unauthorized"}, status=401)
        try:
            request.onecare_user_id = clean_external_user_id(request.headers.get("X-OneCare-User-Id"))
        except ValueError:
            return JsonResponse({"detail": "Invalid X-OneCare-User-Id"}, status=400)
        return view(request, *args, **kwargs)
    return wrapper