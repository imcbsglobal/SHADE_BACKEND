from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── Auth ──────────────────────────────────────────────────────────────
    path('api/auth/', include('Login.urls')),

    # ── Hospital Settings ─────────────────────────────────────────────────
    path('api/settings/', include('hospitalsettings.urls')),

    # ── Appointments ──────────────────────────────────────────────────────
    # GET    /api/appointments/              — list all (admin JWT)
    # POST   /api/appointments/create/       — create  (admin JWT)
    # PATCH  /api/appointments/<id>/status/  — update status (admin JWT)
    # DELETE /api/appointments/<id>/delete/  — delete  (admin JWT)
    path('api/appointments/', include('Appointment.urls')),
]
