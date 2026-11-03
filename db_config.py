"""Chatbot database configuration, built only from environment variables."""
from django.core.exceptions import ImproperlyConfigured

CHATBOT_DB_NAME = "onecare_chatbot"
_REQUIRED = ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST")


def build_database_config(env):
    missing = [k for k in _REQUIRED if not env.get(k)]
    if missing:
        raise ImproperlyConfigured(f"Missing environment variables: {', '.join(missing)}")
    if env["DB_NAME"] != CHATBOT_DB_NAME:
        raise ImproperlyConfigured(
            f"DB_NAME must be '{CHATBOT_DB_NAME}'. The chatbot must never use the main OneCare database."
        )
    if env["DB_USER"].lower() == "root" or env["DB_USER"] == env.get("MAIN_DB_USER"):
        raise ImproperlyConfigured("DB_USER must be the dedicated chatbot user, not root or the Spring Boot user.")
    return {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env["DB_NAME"],
            "USER": env["DB_USER"],
            "PASSWORD": env["DB_PASSWORD"],
            "HOST": env["DB_HOST"],
            "PORT": env.get("DB_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
            "TEST": {"NAME": "test_onecare_chatbot", "CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
        }
    }