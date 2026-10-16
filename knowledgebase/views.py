import json
import logging
from functools import wraps

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from onecare_chat.service_auth import require_service_token

from . import services
from .errors import NotFound, ServiceError, ValidationFailed
from .models import KnowledgeDocument
from .serializers import document_to_dict

logger = logging.getLogger(__name__)


def json_errors(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except ServiceError as exc:
            if exc.status >= 500:
                logger.error("Request failed: %s (%s)", exc.message, exc.code)
            return JsonResponse({"error": {"code": exc.code, "message": exc.message}}, status=exc.status)
        except Exception:
            logger.exception("Unhandled error")
            return JsonResponse({"error": {"code": "INTERNAL_ERROR", "message": "Unexpected error"}}, status=500)
    return wrapper


def _actor(request):
    if not request.onecare_user_id:
        raise ValidationFailed("The X-OneCare-User-Id header is required.")
    return request.onecare_user_id


@csrf_exempt
@require_service_token
@require_http_methods(["POST"])
@json_errors
def upload(request):
    doc = services.upload_pdf(uploaded_file=request.FILES.get("file"),
                              title=request.POST.get("title", ""), actor=_actor(request))
    return JsonResponse(document_to_dict(doc), status=201)


@csrf_exempt
@require_service_token
@require_http_methods(["POST"])
@json_errors
def submit_link(request):
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        raise ValidationFailed("The request body must be JSON.") from None
    url = payload.get("url") if isinstance(payload, dict) else None
    if not isinstance(url, str) or not url.strip():
        raise ValidationFailed("'url' is required.")
    doc = services.submit_link(url=url, actor=_actor(request))
    return JsonResponse(document_to_dict(doc), status=202)


@csrf_exempt
@require_service_token
@require_http_methods(["GET", "DELETE"])
@json_errors
def document_detail(request, doc_id):
    if request.method == "DELETE":
        services.remove_document(doc_id, actor=_actor(request))
        return HttpResponse(status=204)
    try:
        return JsonResponse(document_to_dict(KnowledgeDocument.objects.get(pk=doc_id)))
    except KnowledgeDocument.DoesNotExist:
        raise NotFound("Knowledge document not found.") from None