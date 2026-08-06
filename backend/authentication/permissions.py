"""
Role-based permission classes.

Roles are compared via core.constants.Roles (which map to role_master.role_code)
so we never sprinkle the literal "ADM"/"REC"/"HM" strings through the codebase.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.constants import Roles


def _role_code(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None
    role = getattr(user, "role", None)
    return getattr(role, "role_code", None)


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return _role_code(request) == Roles.ADMIN


class IsRecruiter(BasePermission):
    def has_permission(self, request, view):
        return _role_code(request) == Roles.RECRUITER


class IsHiringManager(BasePermission):
    def has_permission(self, request, view):
        return _role_code(request) == Roles.HIRING_MANAGER


class IsHiringManagerOrAdmin(BasePermission):
    """Hiring Managers create/own requirements; Admins can do anything."""
    def has_permission(self, request, view):
        return _role_code(request) in (Roles.HIRING_MANAGER, Roles.ADMIN)


class IsRecruiterOrAdmin(BasePermission):
    """Recruiters work the candidate pipeline; Admins can do anything."""
    def has_permission(self, request, view):
        return _role_code(request) in (Roles.RECRUITER, Roles.ADMIN)


class IsAdminOrReadOnly(BasePermission):
    """Any authenticated user may read; only Admins may write.
    Used for master/reference data (everyone needs to read dropdowns; only
    admins curate them)."""
    def has_permission(self, request, view):
        role = _role_code(request)
        if request.method in SAFE_METHODS:
            return role is not None  # authenticated
        return role == Roles.ADMIN


class CanManageReferenceData(BasePermission):
    """Reference masters that support inline creation from a workflow form
    (Skills, Locations):
      - read  → any authenticated user;
      - create (POST) → Admin or Hiring Manager (HM adds a missing skill/location
        while creating a requirement, without leaving the form);
      - edit / delete → Admin only.
    """
    def has_permission(self, request, view):
        role = _role_code(request)
        if role is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            return role in (Roles.ADMIN, Roles.HIRING_MANAGER)
        return role == Roles.ADMIN  # PUT/PATCH/DELETE (incl. soft + permanent delete)
