from django.contrib import admin
from .models import HospitalSettings


@admin.register(HospitalSettings)
class HospitalSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ('updated_at',)
    list_display    = ('__str__',)
