"""AC6: the Django DB user can touch ONLY the chatbot schema. Spring Boot's schema is off limits.
Set SPRING_SCHEMA to the real Spring Boot schema name when running against a shared instance."""
import os
import re

import pytest
from django.db import DatabaseError, connection

pytestmark = [pytest.mark.mysql, pytest.mark.django_db]

SPRING_SCHEMA = os.environ.get("SPRING_SCHEMA", "onecare_core")
SPRING_TABLE = os.environ.get("SPRING_TABLE", "users")
ACCESS_DENIED = {1142, 1044, 1143}          # table / database / column access denied


def mysql_error_code(exc):
    return exc.args[0] if exc.args and isinstance(exc.args[0], int) else None


def test_cannot_read_spring_boot_tables():
    with connection.cursor() as c, pytest.raises(DatabaseError) as exc:
        c.execute(f"SELECT * FROM `{SPRING_SCHEMA}`.`{SPRING_TABLE}`")
    assert mysql_error_code(exc.value) in ACCESS_DENIED


def test_cannot_write_spring_boot_tables():
    with connection.cursor() as c, pytest.raises(DatabaseError) as exc:
        c.execute(
            f"INSERT INTO `{SPRING_SCHEMA}`.`{SPRING_TABLE}` (email) "
            "SELECT 'x@example.com' WHERE 1 = 0"
        )
    assert mysql_error_code(exc.value) in ACCESS_DENIED


def test_cannot_even_see_spring_boot_schema():
    with connection.cursor() as c:
        c.execute("SHOW DATABASES")
        visible = {r[0] for r in c.fetchall()}
    assert SPRING_SCHEMA not in visible


def test_grants_reference_only_the_chatbot_schemas():
    with connection.cursor() as c:
        c.execute("SHOW GRANTS FOR CURRENT_USER()")
        grants = [r[0] for r in c.fetchall()]
    allowed = {"onecare_chatbot", "test_onecare_chatbot"}           # test_ one exists only for pytest-django
    for g in grants:
        target = re.search(r" ON (.+?) TO ", g).group(1).replace("`", "").replace("\\", "")
        if target == "*.*":
            assert g.startswith("GRANT USAGE ON"), f"global privilege found: {g}"
        else:
            assert target.split(".")[0] in allowed, f"unexpected grant: {g}"
            