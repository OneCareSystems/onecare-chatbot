# views.py
from django.http import JsonResponse

from .service_auth import require_service_token


@require_service_token
def health(request):
    return JsonResponse({"status": "ok"})


def public_health(request):
    return JsonResponse({"status": "ok"})