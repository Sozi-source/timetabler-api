"""
timetable/permissions.py
========================
Custom DRF permission classes for the timetable system.

Permission hierarchy
--------------------
TimetableAdmin     — full access (institution staff, superusers)
Coordinator        — can generate, publish, edit entries, resolve conflicts
Trainer (self)     — read-only access to their own timetable/dashboard
Student/ReadOnly   — read-only access to published timetables

Django group names expected: "Timetable Admin", "Coordinator"
The Trainer read-only access is derived from request.user.trainer_profile.

Usage in views (example)
------------------------
    from .permissions import IsCoordinatorOrAdmin, IsTrainerOwnerOrAdmin

    class GenerateView(APIView):
        permission_classes = [IsAuthenticated, IsCoordinatorOrAdmin]
"""

from rest_framework.permissions import BasePermission, IsAuthenticated, SAFE_METHODS


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _in_group(user, *group_names: str) -> bool:
    """Return True if the user belongs to ANY of the named groups."""
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=group_names).exists()


# ─────────────────────────────────────────────────────────────────────────────
# Permission classes
# ─────────────────────────────────────────────────────────────────────────────

class IsTimetableAdmin(BasePermission):
    """
    Full read/write access.
    Granted to: superusers, members of the "Timetable Admin" group.
    """
    message = "You must be a Timetable Administrator to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and _in_group(request.user, "Timetable Admin")
        )


class IsCoordinatorOrAdmin(BasePermission):
    """
    Coordinators and admins can read + write.
    Suitable for: generate, publish, constraint CRUD, conflict resolution.
    """
    message = "Coordinator or Admin access required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and _in_group(request.user, "Timetable Admin", "Coordinator")
        )


class IsTrainerOrCoordinatorOrAdmin(BasePermission):
    """
    Read-only for authenticated trainers; write access for coordinators/admins.
    Trainers may only read their own timetable (enforced at view level).
    """
    message = "You must be authenticated as a trainer, coordinator, or admin."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.method in SAFE_METHODS:
            # Any authenticated user may read
            return True

        # Write requires coordinator/admin
        return _in_group(request.user, "Timetable Admin", "Coordinator")


class IsTrainerOwnerOrAdmin(BasePermission):
    """
    Object-level: a trainer may only access their own records.
    Admins/coordinators have unrestricted access.
    """
    message = "You can only access your own timetable data."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if _in_group(request.user, "Timetable Admin", "Coordinator"):
            return True
        trainer_profile = getattr(request.user, "trainer_profile", None)
        if trainer_profile is None:
            return False
        # obj may be a Trainer instance or a ScheduledUnit with .trainer
        if hasattr(obj, "trainer"):
            return obj.trainer == trainer_profile
        return obj == trainer_profile


class IsReadOnly(BasePermission):
    """Allow only safe (GET/HEAD/OPTIONS) HTTP methods."""
    message = "This endpoint is read-only."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.method in SAFE_METHODS
        )


class IsAdminOrReadOnly(BasePermission):
    """
    Admins can do anything; everyone else is read-only.
    Useful for setup endpoints (rooms, periods, programmes).
    """
    message = "Admin access required to modify this resource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return _in_group(request.user, "Timetable Admin")