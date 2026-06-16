from django.contrib import admin
from django.urls import path, include
from app1.views import get_hospital_info

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('api/auth/', include('Login.urls')),

    # Hospital Settings
    path('api/settings/', include('hospitalsettings.urls')),

    # Appointments
    path('api/appointments/', include('Appointment.urls')),

    # Doctors and Hospital Info
    path('api/doctors/', include('app1.urls')),
    path('api/hospital-info/', get_hospital_info, name='get_hospital_info'),
]
