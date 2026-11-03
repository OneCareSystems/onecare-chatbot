import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from knowledgebase import ingestion, services, vector_index
from knowledgebase.models import KnowledgeDocument as Doc


class Command(BaseCommand):
    help = "Process PENDING knowledge documents (the ingestion queue)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process the queue once and exit")
        parser.add_argument("--interval", type=int, default=5)
        parser.add_argument("--reindex", type=int, help="Re-embed one INDEXED document id")
        parser.add_argument("--rebuild-index", action="store_true", help="Rebuild the FAISS index from the database")

    def handle(self, *args, **opts):
        if opts["reindex"]:
            self.stdout.write(ingestion.ingest_document(opts["reindex"], reindex=True))
            return
        if opts["rebuild_index"]:
            with vector_index.index_lock():
                vector_index.build_index()
            self.stdout.write("Index rebuilt.")
            return
        while True:
            # a worker that died mid-run leaves PROCESSING rows: give them back after 30 minutes
            Doc.objects.filter(status=Doc.Status.PROCESSING, updated_at__lt=timezone.now() - timedelta(minutes=30)) \
                .update(status=Doc.Status.PENDING)
            for doc in Doc.objects.filter(status=Doc.Status.REMOVED, chunks__isnull=False).distinct():
                services.purge_artifacts(doc.id)                # finish a cleanup that failed earlier
            for doc_id in list(Doc.objects.filter(status=Doc.Status.PENDING).order_by("id").values_list("id", flat=True)[:10]):
                self.stdout.write(f"document {doc_id}: {ingestion.ingest_document(doc_id)}")
            if opts["once"]:
                return
            time.sleep(opts["interval"])