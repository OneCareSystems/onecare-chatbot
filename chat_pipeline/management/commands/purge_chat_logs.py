from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from chat_pipeline.models import ChatLog


class Command(BaseCommand):
    help = "CHAT-10: delete chat logs older than the retention period (default CHAT_LOG_RETENTION_DAYS). Run it daily."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        days = opts["days"] if opts["days"] is not None else getattr(settings, "CHAT_LOG_RETENTION_DAYS", 90)
        old = ChatLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=days))
        count = old.count()
        if not opts["dry_run"]:
            old.delete()
        self.stdout.write(f"{'would delete' if opts['dry_run'] else 'deleted'} {count} chat log rows older than {days} days")