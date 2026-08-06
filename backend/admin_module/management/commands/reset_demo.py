"""Reset the database to the seeded demo BASELINE — DEV/TEST ONLY.

Empties all transactional data and rebuilds the initial-state demo (requirements
Open, positions Open, candidates New-CV with their own skills, review-pool tags,
no pipeline mappings / screenings / logs). Master/reference data is preserved.

    python manage.py reset_demo            # interactive confirmation
    python manage.py reset_demo --yes      # non-interactive (CI/scripts)

Guarded: refuses unless DEBUG is on OR ALLOW_DEMO_RESET=1 is set in the
environment, so it can never run against a production database by accident.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from admin_module.models import UserMaster
from admin_module.services.demo_reset import reset_to_baseline
from core.constants import Roles


class Command(BaseCommand):
    help = "Reset transactional data to the seeded demo baseline (dev/test only)."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true",
                            help="Skip the interactive confirmation (for CI).")

    def handle(self, *args, **options):
        # --- Production guard --------------------------------------------- #
        allow = getattr(settings, "DEBUG", False) or os.environ.get("ALLOW_DEMO_RESET") == "1"
        if not allow:
            raise CommandError(
                "Refusing to reset: DEBUG is off and ALLOW_DEMO_RESET != '1'. "
                "This command is for development/testing databases only."
            )

        db_name = settings.DATABASES["default"].get("NAME", "?")

        # --- Confirmation ------------------------------------------------- #
        if not options["yes"]:
            self.stdout.write(self.style.WARNING(
                f"This will DELETE all transactional data in '{db_name}' and rebuild the demo baseline."
            ))
            typed = input(f"Type the database name ('{db_name}') to confirm: ").strip()
            if typed != db_name:
                raise CommandError("Confirmation did not match — aborted. Nothing was changed.")

        # An actor for the audit stamps (created_by/tagged_by). Prefer the demo
        # admin; fall back to any admin.
        actor = (UserMaster.objects.filter(username="priya.sharma").first()
                 or UserMaster.objects.filter(role__role_code=Roles.ADMIN, is_active=True).first())
        if actor is None:
            raise CommandError(
                "No admin user found to attribute the reset to. Run `seed_demo` (or seed the "
                "master data) at least once first."
            )

        self.stdout.write("Resetting to the seeded demo baseline…")
        summary = reset_to_baseline(actor)
        self.stdout.write(self.style.SUCCESS(
            f"Done. Rebuilt {summary['requirements']} requirements (Open), "
            f"{summary['candidates']} candidates (New CV), and "
            f"{summary['review_tags']} review-pool tags. No pipeline data. Masters preserved."
        ))
