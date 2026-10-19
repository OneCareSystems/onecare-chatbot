from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from django.utils import timezone

from chat_pipeline.models import ChatLog


class Command(BaseCommand):
    help = "CHAT-10: counts by response type, fallback path and language for the last N days (later evaluation)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **opts):
        rows = ChatLog.objects.filter(created_at__gte=timezone.now() - timedelta(days=opts["days"]))
        self.stdout.write(f"last {opts['days']} days: {rows.count()} queries, avg latency "
                          f"{int(rows.aggregate(a=Avg('latency_ms'))['a'] or 0)} ms")
        for title, field in (("by type", "response_type"), ("by fallback path", "fallback_path"), ("by language", "detected_language")):
            self.stdout.write(f"-- {title}")
            for item in rows.values(field).annotate(n=Count("id")).order_by("-n"):
                self.stdout.write(f"   {item[field] or '(none)'}: {item['n']}")