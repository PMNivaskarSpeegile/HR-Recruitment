"""Daily candidate lifecycle maintenance (schedule via cron/Task Scheduler).

  python manage.py run_candidate_lifecycle

- Reject Hold -> Talent Pool once the 6-month cool-off elapses (counter reset).
- Joined -> Talent Pool after the 2-year retention window.
History is never modified - only the working counter + status move.
"""
from django.core.management.base import BaseCommand

from candidates.services import run_lifecycle_maintenance


class Command(BaseCommand):
    help = "Release Reject-Hold (6mo) and Joined (2yr) candidates back to the Talent Pool."

    def handle(self, *args, **options):
        summary = run_lifecycle_maintenance()
        self.stdout.write(self.style.SUCCESS(
            f"Reject-holds released: {summary['reject_hold_released']}; "
            f"joins released: {summary['joined_released']}."
        ))
