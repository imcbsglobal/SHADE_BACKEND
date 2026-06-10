from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display  = ('patient_name', 'doctor_name', 'department_name',
                     'appointment_date', 'appointment_time', 'status', 'created_at')
    list_filter   = ('status', 'appointment_date', 'department_name')
    search_fields = ('patient_name', 'doctor_name', 'phone', 'email')
    ordering      = ('-created_at',)
