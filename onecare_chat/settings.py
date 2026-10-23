import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from db_config import build_database_config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-o)t5@48u&$f1v^9@_ihi!5+k@6sv3x1(pbq+r5dwve69eidt7t'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "rest_framework",
    "knowledgebase",
    "chat",
    "chat_pipeline",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

#AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],#["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES":[], # ["rest_framework.permissions.IsAuthenticated"],
    "UNAUTHENTICATED_USER": None,
}
#CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]

ROOT_URLCONF = 'onecare_chat.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'onecare_chat.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = build_database_config(os.environ)      # chatbot DB only, from env
DATABASE_ROUTERS = []


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = []


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

CHATBOT_STORAGE_DIR = Path(os.environ.get("CHATBOT_STORAGE_DIR") or BASE_DIR / "storage").resolve()

CHATBOT_SERVICE_TOKEN = os.environ.get("CHATBOT_SERVICE_TOKEN", "")
if len(CHATBOT_SERVICE_TOKEN) < 32:
    raise ImproperlyConfigured("CHATBOT_SERVICE_TOKEN must be at least 32 characters.")


# ---- Knowledge base (KB-01 .. KB-09) ----
APPEND_SLASH = False
KB_MAX_UPLOAD_BYTES = int(os.environ.get("KB_MAX_UPLOAD_BYTES", "10485760"))   # keep equal to Spring's max-file-size
KB_URL_ALLOWLIST = [d.strip().lower() for d in os.environ.get("KB_URL_ALLOWLIST", "").split(",") if d.strip()]
KB_FETCH_MAX_BYTES = int(os.environ.get("KB_FETCH_MAX_BYTES", "5242880"))
KB_MIN_TEXT_CHARS = int(os.environ.get("KB_MIN_TEXT_CHARS", "50"))
KB_LANG_DOMINANCE = float(os.environ.get("KB_LANG_DOMINANCE", "0.9"))
KB_CHUNK_MAX_TOKENS = int(os.environ.get("KB_CHUNK_MAX_TOKENS", "450"))
KB_CHUNK_MIN_TOKENS = int(os.environ.get("KB_CHUNK_MIN_TOKENS", "300"))
KB_CHUNK_OVERLAP_TOKENS = int(os.environ.get("KB_CHUNK_OVERLAP_TOKENS", "50"))
KB_EMBED_BATCH = int(os.environ.get("KB_EMBED_BATCH", "32"))
KB_EMBEDDER_CLASS = os.environ.get("KB_EMBEDDER_CLASS", "knowledgebase.embedding.SentenceTransformerEmbedder")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
KB_EMBEDDING_LOCAL_FILES_ONLY = os.environ.get('KB_EMBEDDING_LOCAL_FILES_ONLY', 'false').lower() == 'true'
KB_PRELOAD_EMBEDDER = os.environ.get('KB_PRELOAD_EMBEDDER', 'false').lower() == 'true'
CHAT_FIXED_CLINIC_ENABLED = os.environ.get("CHAT_FIXED_CLINIC_ENABLED", "true").lower() == "true"

# ---- Chat pipeline, DDP-#37 Stage 3 (CHAT-01 .. CHAT-07) ----
CHAT_MAX_QUERY_CHARS = int(os.environ.get("CHAT_MAX_QUERY_CHARS", "500"))               # NFRS-007: confirm the real limit
CHAT_TAMIL_SHARE_THRESHOLD = float(os.environ.get("CHAT_TAMIL_SHARE_THRESHOLD", "0.5"))
CHAT_SEARCH_K = int(os.environ.get("CHAT_SEARCH_K", "5"))
CHAT_SEARCH_MAX_K = int(os.environ.get("CHAT_SEARCH_MAX_K", "10"))
CHAT_SEARCH_TIMEOUT_SECONDS = float(os.environ.get("CHAT_SEARCH_TIMEOUT_SECONDS", "5"))
# CHAT-05: best score >= threshold counts as a match (inclusive). CALIBRATE on EN and TA fixture sets before release.
CHAT_SCORE_THRESHOLDS = {
    "EN": float(os.environ.get("CHAT_SCORE_THRESHOLD_EN", "0.80")),
    "TA": float(os.environ.get("CHAT_SCORE_THRESHOLD_TA", "0.75")),      # cross-lingual scores are usually lower
    "DEFAULT": float(os.environ.get("CHAT_SCORE_THRESHOLD_DEFAULT", "0.80")),
}
CHAT_GENERATOR_CLASS = os.environ.get("CHAT_GENERATOR_CLASS", "chat_pipeline.generation.ExtractiveGenerator")   # CHAT-09 replaces it

# Django -> Spring Boot (CHAT-07). SPRING_SERVICE_TOKEN is the INT-01 service credential. Never a user JWT.
SPRING_BASE_URL = os.environ.get("SPRING_BASE_URL", "http://127.0.0.1:9090")          # mock server now, real Spring later
SPRING_SERVICE_TOKEN = os.environ.get("SPRING_SERVICE_TOKEN", "")
SPRING_CONNECT_TIMEOUT = float(os.environ.get("SPRING_CONNECT_TIMEOUT", "2"))
SPRING_READ_TIMEOUT = float(os.environ.get("SPRING_READ_TIMEOUT", "3"))
SPRING_CLINIC_HOURS_PATH = os.environ.get("SPRING_CLINIC_HOURS_PATH", "/api/internal/clinic/hours")
SPRING_CLINIC_AVAILABILITY_PATH = os.environ.get("SPRING_CLINIC_AVAILABILITY_PATH", "/api/internal/clinic/availability")

# ---- DDP-#38 Stage 4: LLM integration (CHAT-08, CHAT-09, CHAT-10) ----
# CHAT-09: which model answers. LLM_PROVIDER = groq | openai_compatible | fake
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai_compatible")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")                 # secret: .env only, never in git, never logged
if LLM_PROVIDER.lower() == "groq":
    LLM_API_KEY = os.environ.get("GROQ_API_KEY", "") or LLM_API_KEY
LLM_MODEL = os.environ.get("LLM_MODEL", "")                     # model ID from your provider's console
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")               # empty = the provider's default URL
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "400"))
_temperature = os.environ.get("LLM_TEMPERATURE", "0")
LLM_TEMPERATURE = float(_temperature) if _temperature != "" else None      # empty = do not send the parameter
LLM_CONNECT_TIMEOUT = float(os.environ.get("LLM_CONNECT_TIMEOUT", "3"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "20"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "1"))
LLM_REASONING_EFFORT = os.environ.get('LLM_REASONING_EFFORT', '')
CHAT_GENERATOR_CLASS = os.environ.get("CHAT_GENERATOR_CLASS", "chat_pipeline.generation.LLMGenerator")   # replaces the Stage 3 default

# CHAT-08: how much context the model sees, and the same-language check
CHAT_CONTEXT_CHUNKS = int(os.environ.get("CHAT_CONTEXT_CHUNKS", "4"))
CHAT_CONTEXT_CHARS_PER_CHUNK = int(os.environ.get("CHAT_CONTEXT_CHARS_PER_CHUNK", "1200"))
CHAT_LANGUAGE_CHECK = os.environ.get("CHAT_LANGUAGE_CHECK", "true").lower() == "true"
CHAT_LANG_TA_MIN_SHARE = float(os.environ.get("CHAT_LANG_TA_MIN_SHARE", "0.30"))
CHAT_LANG_EN_MAX_SHARE = float(os.environ.get("CHAT_LANG_EN_MAX_SHARE", "0.20"))

# CHAT-10: audit log of every query and response
CHAT_LOG_ENABLED = os.environ.get("CHAT_LOG_ENABLED", "true").lower() == "true"
CHAT_LOG_REDACT = os.environ.get("CHAT_LOG_REDACT", "true").lower() == "true"
CHAT_LOG_MAX_CHARS = int(os.environ.get("CHAT_LOG_MAX_CHARS", "4000"))
CHAT_LOG_RETENTION_DAYS = int(os.environ.get("CHAT_LOG_RETENTION_DAYS", "90"))
