"""
Pytest configuration and shared fixtures.

DB strategy: ATS tables are `managed = False` (created by SQL migrations, not
Django migrations), so we REUSE the existing database rather than building a
Django test DB. Each `@pytest.mark.django_db` test runs inside a transaction
that is rolled back, so nothing persists.

CI note: for full isolation, provision a dedicated database from
`database/migrations/*.sql` and point DB_NAME at it.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")


@pytest.fixture(scope="session")
def django_db_setup():
    # No-op: use the already-existing database (see module docstring).
    yield


def _user_by_role(role_code):
    from admin_module.models import UserMaster
    return UserMaster.objects.filter(role__role_code=role_code, is_active=True).first()


@pytest.fixture
def admin_user(db):
    return _user_by_role("ADM")


@pytest.fixture
def recruiter_user(db):
    return _user_by_role("REC")


@pytest.fixture
def hm_user(db):
    return _user_by_role("HM")


@pytest.fixture
def a_domain_id(db):
    """An existing (referenced) domain — Skills now require a domain FK."""
    from admin_module.models import DomainMaster
    return DomainMaster.objects.filter(is_active=True).first().domain_id


@pytest.fixture
def api():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api):
    """Return a function that authenticates the APIClient as a given user
    (builds a JWT directly, bypassing the throttled login endpoint)."""
    from django.conf import settings

    def _as(user):
        import jwt
        token = jwt.encode(
            {
                "user_id": user.user_id,
                "username": user.username,
                "role": user.role.role_code,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "iat": datetime.now(timezone.utc),
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return api

    return _as
