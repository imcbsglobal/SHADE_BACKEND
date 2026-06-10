from rest_framework import serializers
from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Appointment
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class AppointmentCreateSerializer(serializers.ModelSerializer):
    """Used for POST — accepts the fields sent from the admin create form."""
    class Meta:
        model  = Appointment
        fields = [
            'patient_name', 'phone', 'email',
            'doctor_name', 'doctor_code', 'department_name',
            'appointment_date', 'appointment_time', 'appointment_type',
            'status',
        ]

    def validate_appointment_time(self, value):
        return value  # TimeField handles HH:MM strings automatically

    def create(self, validated_data):
        return Appointment.objects.create(**validated_data)


class AppointmentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['pending', 'accepted', 'rejected'])
