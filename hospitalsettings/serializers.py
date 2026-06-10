from rest_framework import serializers
from .models import HospitalSettings


class HospitalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = HospitalSettings
        fields = ['settings_data', 'updated_at']
        read_only_fields = ['updated_at']
