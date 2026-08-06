"""
Seed one user per role so the full workflow is testable.

Idempotent: re-running updates the same users instead of creating duplicates.
All demo users share the password below — change it for any real deployment.
"""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from admin_module.models import RoleMaster, UserMaster
from core.constants import Roles

DEMO_PASSWORD = "Speegile@123"

DEMO_USERS = [
    # username,        full_name,        email,                         mobile,       role_code
    ("priya.sharma",  "Priya Sharma",   "priya.sharma@speegile.com",   "9820011001", Roles.ADMIN),
    ("ankit.desai",   "Ankit Desai",    "ankit.desai@speegile.com",    "9820011004", Roles.HIRING_MANAGER),
    ("rajeev.mehta",  "Rajeev Mehta",   "rajeev.mehta@speegile.com",   "9820011002", Roles.RECRUITER),
]


class Command(BaseCommand):
    help = "Create/refresh one demo user per role (Admin, Hiring Manager, Recruiter)."

    def handle(self, *args, **kwargs):
        roles = {r.role_code: r for r in RoleMaster.objects.all()}
        hashed = make_password(DEMO_PASSWORD)

        for username, full_name, email, mobile, role_code in DEMO_USERS:
            role = roles.get(role_code)
            if role is None:
                self.stderr.write(f"  ! Role '{role_code}' missing in role_master — skipping {username}")
                continue

            _, created = UserMaster.objects.update_or_create(
                username=username,
                defaults={
                    "full_name": full_name,
                    "email": email,
                    "mobile": mobile,
                    "role": role,
                    "is_active": True,
                    "password_hash": hashed,
                    "created_on": timezone.now(),
                },
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {verb}: {username} ({role_code})"))

        self.stdout.write(self.style.SUCCESS(f"Done. All demo users share password: {DEMO_PASSWORD}"))
