from django.core.management.base import BaseCommand

from chat_pipeline import search
from chat_pipeline.errors import VectorStoreUnavailable


class Command(BaseCommand):
    help = "CHAT-04: run searches and print p50/p95 latency (note the p95 in the PR)."

    def add_arguments(self, parser):
        parser.add_argument("queries", nargs="+")
        parser.add_argument("--repeat", type=int, default=20)

    def handle(self, *args, **opts):
        search.reset_latencies()
        for _ in range(opts["repeat"]):
            for query in opts["queries"]:
                try:
                    search.similarity_search(query)
                except VectorStoreUnavailable as exc:
                    self.stderr.write(f"search failed: {exc}")
        p95 = search.latency_p95_ms()
        self.stdout.write(f"searches={len(search._latencies)} p95_ms={p95:.1f}" if p95 is not None else "no successful searches")