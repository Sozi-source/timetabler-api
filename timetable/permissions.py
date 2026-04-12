from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Allow access only to admin/staff users."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsCoordinator(BasePermission):
    """Allow access to staff users or users with a lecturer profile that is full-time."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        # Coordinators are full-time lecturers
        lecturer = getattr(request.user, 'lecturer_profile', None)
        return lecturer is not None and lecturer.lecturer_type == 'FT'


class IsLecturer(BasePermission):
    """Allow access only to users with an associated lecturer profile."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return hasattr(request.user, 'lecturer_profile')