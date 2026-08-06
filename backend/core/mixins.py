"""
Reusable view behaviour for the audit columns.

WHY: almost every table has created_by / created_on / updated_by / updated_on.
Setting them by hand in every view is repetitive and easy to forget. A ViewSet
that mixes this in gets them filled automatically from the authenticated user.

Only use it on ViewSets whose model actually has these columns.
"""
from django.utils import timezone


class AuditModelMixin:
    def _current_user(self):
        user = getattr(self.request, "user", None)
        # Our custom JWT auth attaches a UserMaster instance; anonymous -> None.
        return user if getattr(user, "is_authenticated", False) or user is not None else None

    def perform_create(self, serializer):
        user = self._current_user()
        serializer.save(created_by=user, created_on=timezone.now())

    def perform_update(self, serializer):
        user = self._current_user()
        serializer.save(updated_by=user, updated_on=timezone.now())
