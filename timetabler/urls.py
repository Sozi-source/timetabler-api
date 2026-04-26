from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # ── Root redirect ─────────────────────────────────────────────────────
    path("", RedirectView.as_view(url="/swagger/"), name="root"),

    # ── Django admin ──────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── API Documentation ─────────────────────────────────────────────────
    # FIX: Moved docs paths ABOVE the broad `api/` include so that
    # /api/schema/ is matched here and never forwarded to the timetable
    # router, which would return a 404 for an unregistered prefix.
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # ── Timetable API ─────────────────────────────────────────────────────
    # Placed after docs so specific /api/schema/ path wins over this prefix.
    path("api/", include("timetable.urls")),
]

# ── Media files (development only) ────────────────────────────────────────
# FIX: Guard with DEBUG check — static() returns [] in production anyway,
# but being explicit prevents accidental media exposure behind a real server.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)