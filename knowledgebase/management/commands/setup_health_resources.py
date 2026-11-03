import hashlib
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from knowledgebase import ingestion, services, url_safety, validators, vector_index
from knowledgebase.health_resources import PDFS, WEBSITES
from knowledgebase.models import KnowledgeDocument as Doc


class Command(BaseCommand):
    help = 'Register and optionally ingest project health resources using existing approved pipelines.'

    def add_arguments(self, parser):
        parser.add_argument('--actor', required=True, help='Existing external administrator ID for audit attribution')
        parser.add_argument('--pdf-dir', default=str(settings.BASE_DIR))
        parser.add_argument('--ingest', action='store_true')
        parser.add_argument('--retry-failed', action='store_true')

    def handle(self, *args, **opts):
        failed = []
        for source in (*WEBSITES, *PDFS):
            try:
                normalized = url_safety.validate_submission(source) if source.startswith('https:') else None
                # Serialize setup runs with the same lock used by the indexer. This prevents
                # duplicate PDF registration without changing the existing database schema.
                with vector_index.index_lock():
                    if source.startswith('https:'):
                        digest = hashlib.sha256(normalized.encode()).hexdigest()
                        doc = Doc.objects.filter(url_hash=digest).first()
                        if doc is None:
                            doc = services.submit_link(url=source, actor=opts['actor'])
                    else:
                        path = Path(opts['pdf_dir']) / source
                        with path.open('rb') as stream:
                            uploaded = File(stream, name=source)
                            validators.validate_pdf_upload(uploaded, settings.KB_MAX_UPLOAD_BYTES)
                            digest = validators.sha256_of(uploaded)
                            doc = Doc.objects.filter(source_type='PDF', content_sha256=digest).exclude(status='REMOVED').first()
                            if doc is None:
                                doc = services.upload_pdf(uploaded_file=uploaded, title=source, actor=opts['actor'])
                if opts['retry_failed'] and doc.status == Doc.Status.FAILED:
                    with transaction.atomic():
                        Doc.objects.filter(pk=doc.pk, status=Doc.Status.FAILED).update(status=Doc.Status.PENDING)
                if opts['ingest']:
                    ingestion.ingest_document(doc.pk)
                doc.refresh_from_db()
                self.stdout.write(f'{source}: {doc.status} (id={doc.pk}) {doc.failure_reason}')
                if doc.status == Doc.Status.FAILED:
                    failed.append(source)
            except Exception as exc:  # noqa: BLE001 - report each resource failure and continue, then exit nonzero.
                failed.append(source)
                self.stderr.write(f'{source}: FAILED: {exc}')
        if failed:
            raise CommandError(f'{len(failed)} resource(s) failed; see individual results above.')
