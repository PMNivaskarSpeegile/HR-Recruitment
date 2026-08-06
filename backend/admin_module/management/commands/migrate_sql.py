"""
Apply a raw SQL migration file from database/migrations/.

Because this project's tables are managed outside Django (models use
`managed = False`), we version schema changes as ordered .sql files and apply
them with this command instead of `manage.py migrate`.

Usage:
    python manage.py migrate_sql 0001_phase1_pipeline.sql
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Apply a raw SQL migration file from database/migrations/"

    def add_arguments(self, parser):
        parser.add_argument(
            "filename",
            help="SQL file name located inside database/migrations/",
        )

    def handle(self, *args, **options):
        filename = options["filename"]
        migrations_dir = Path(settings.BASE_DIR).parent / "database" / "migrations"
        sql_path = migrations_dir / filename

        if not sql_path.exists():
            raise CommandError(f"Migration file not found: {sql_path}")

        sql = sql_path.read_text(encoding="utf-8")
        self.stdout.write(f"Applying migration: {filename}")

        try:
            # PostgreSQL supports transactional DDL — so the whole file applies
            # atomically (all-or-nothing). If anything fails, nothing is committed.
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql)
        except Exception as exc:  # noqa: BLE001 - surface the DB error verbatim
            raise CommandError(f"Migration failed (rolled back): {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Applied {filename} successfully."))
