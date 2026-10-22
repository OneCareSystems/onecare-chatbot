"""
WSGI config for onecare_chat project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

from knowledgebase.embedding import preload_embedder

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'onecare_chat.settings')

application = get_wsgi_application()

preload_embedder()
