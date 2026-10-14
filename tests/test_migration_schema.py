"""AC1: the migration builds the table with the right columns/constraints, no manual SQL.
Also: second `migrate` is a no-op, no stray auth/admin/session tables."""
import io
import re

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]

# column -> (data_type, nullable, max_length)
EXPECTED = {
    "id": ("bigint", "NO", None),
    "file_name": ("varchar", "NO", 255),
    "source_type": ("varchar", "NO", 10),
    "language": ("varchar", "YES", 5),
    "storage_path": ("varchar", "NO", 500),
    "content_hash": ("varchar", "NO", 64),
    "status": ("varchar", "NO", 10),
    "failure_reason": ("varchar", "YES", 500),
    "uploaded_by": ("bigint", "NO", None),
    "uploaded_at": ("datetime", "NO", None),
    "updated_at": ("datetime", "NO", None),
    "removed_at": ("datetime", "YES", None),
}


def q(sql, *params):
    with connection.cursor() as c:
        c.execute(sql, params)
        return c.fetchall()


def test_mysql_version_supports_check_constraints():
    version = q("SELECT VERSION()")[0][0]
    major, minor, patch = (int(x) for x in re.match(r"(\d+)\.(\d+)\.(\d+)", version).groups())
    assert (major, minor, patch) >= (8, 0, 16), version


def test_columns_types_and_nullability():
    rows = q("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH FROM information_schema.COLUMNS "
             "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'knowledge_document'")
    actual = {r[0]: (r[1], r[2], r[3]) for r in rows}
    assert actual == EXPECTED


def test_all_names_are_snake_case():
    names = [r[0] for r in q("SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                             "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'knowledge_document'")]
    names.append("knowledge_document")
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", n) for n in names), names


def test_uploaded_by_is_plain_unsigned_integer():
    col_type = q("SELECT COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                 "AND TABLE_NAME = 'knowledge_document' AND COLUMN_NAME = 'uploaded_by'")[0][0]
    assert col_type == "bigint unsigned"


def test_check_constraints_exist_and_table_has_no_foreign_keys():
    rows = q("SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE FROM information_schema.TABLE_CONSTRAINTS "
             "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'knowledge_document'")
    checks = {n for n, t in rows if t == "CHECK"}
    # Django also adds an unnamed CHECK (uploaded_by >= 0) for PositiveBigIntegerField, hence >= not ==
    assert {"chk_knowledge_document_status", "chk_knowledge_document_source_type",
            "chk_knowledge_document_language"} <= checks
    assert not [n for n, t in rows if t == "FOREIGN KEY"]          # AC4: no FKs / cascades
    referencing = q("SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME = "
                    "'knowledge_document' AND TABLE_SCHEMA = DATABASE()")[0][0]
    assert referencing == 0                                        # nothing points at it either


def test_status_and_source_type_use_case_sensitive_collation():
    rows = q("SELECT COLUMN_NAME, COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
             "AND TABLE_NAME = 'knowledge_document' AND COLUMN_NAME IN ('status','source_type','language')")
    assert {c: coll for c, coll in rows} == {"status": "utf8mb4_0900_as_cs", "source_type": "utf8mb4_0900_as_cs",
                                             "language": "utf8mb4_0900_as_cs"}


def test_no_vector_columns():
    names = [r[0].lower() for r in q("SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                                     "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'knowledge_document'")]
    assert not [n for n in names if any(w in n for w in ("vector", "embedding", "faiss", "index"))]


def test_only_chatbot_tables_exist():
    """Minimal INSTALLED_APPS: no auth_user, django_session, django_admin_log, django_content_type..."""
    tables = {r[0] for r in q("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")}
    assert tables == {"knowledge_document", "django_migrations"}


def test_installed_apps_are_minimal():
    assert not [a for a in settings.INSTALLED_APPS if a.startswith("django.contrib")]


@pytest.mark.django_db(transaction=True)
def test_second_migrate_is_a_noop_and_no_pending_model_changes():
    out = io.StringIO()
    call_command("migrate", interactive=False, stdout=out)
    assert "No migrations to apply" in out.getvalue()
    call_command("makemigrations", "--check", "--dry-run")           # raises SystemExit if a migration is missing


def test_health_endpoint_still_works_without_auth_app(client):
    r = client.get("/api/chatbot/health/")
    assert r.status_code == 200 and r.json() == {"status": "ok"}