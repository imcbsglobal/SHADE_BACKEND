from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .models import Appointment
from .serializers import (
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentStatusSerializer,
)


# ── List + Create ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_appointments(request):
    """
    GET /api/appointments/
    Returns all appointments ordered by newest first.
    Supports ?status=pending|accepted|rejected filter.
    """
    qs = Appointment.objects.all()
    s = request.query_params.get('status')
    if s in ('pending', 'accepted', 'rejected'):
        qs = qs.filter(status=s)
    serializer = AppointmentSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_appointment(request):
    """
    POST /api/appointments/create/
    Body: {
        patient_name, phone, email,
        doctor_name, doctor_code, department_name,
        appointment_date (YYYY-MM-DD),
        appointment_time (HH:MM),
        appointment_type,
        status (optional, default 'pending')
    }
    """
    serializer = AppointmentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    appointment = serializer.save()
    return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


# ── Single appointment actions ────────────────────────────────────────────────

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_status(request, pk):
    """
    PATCH /api/appointments/<id>/status/
    Body: { "status": "accepted" | "rejected" | "pending" }
    """
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'detail': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = AppointmentStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    appointment.status = serializer.validated_data['status']
    appointment.save()
    return Response(AppointmentSerializer(appointment).data)


@api_view(['DELETE'])
@permission_classes([IsAdminUser])
def delete_appointment(request, pk):
    """
    DELETE /api/appointments/<id>/delete/
    """
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'detail': 'Appointment not found.'}, status=status.HTTP_404_NOT_FOUND)

    appointment.delete()
    return Response({'id': pk, 'success': True}, status=status.HTTP_200_OK)
