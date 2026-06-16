from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, date, timedelta

from .models import Appointment
from .serializers import (
    AppointmentSerializer,
    AppointmentCreateSerializer,
    AppointmentStatusSerializer,
)


def get_client_id(request) -> str | None:
    """Extract client_id custom claim from the validated JWT token."""
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        auth = getattr(request, 'auth', None)
        if auth:
            return auth.get('client_id') or None
    return None


# ── Slots ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def get_doctor_slots(request):
    """
    GET /api/appointments/slots/?doctor_code=D001&date=2026-06-16

    Generates time slots for a doctor on a given date based on
    their timing windows in hms_doctorstiming, then marks each slot
    as 'Booked' or 'Vacant' based on existing appointments.

    Response: list of slot objects:
    [
      {
        "slot_number": 1,        ← hms_doctorstiming.slno
        "start_time":  "09:00",
        "end_time":    "09:15",
        "status":      "Vacant" | "Booked"
      },
      ...
    ]
    """
    from app1.models import HmsDoctors, HmsDoctorstiming

    doctor_code = request.query_params.get('doctor_code', '').strip()
    date_str    = request.query_params.get('date', '').strip()

    if not doctor_code or not date_str:
        return Response(
            {'error': 'doctor_code and date are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate / parse date
    try:
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'date must be YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get doctor's average consultation time (minutes); default 15
    try:
        doctor = HmsDoctors.objects.get(code=doctor_code)
        slot_duration = int(doctor.avgcontime or 15)
    except HmsDoctors.DoesNotExist:
        return Response(
            {'error': f'Doctor {doctor_code!r} not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Fetch this doctor's timing windows
    timings = HmsDoctorstiming.objects.filter(code=doctor_code).order_by('slno')
    if not timings.exists():
        return Response([])  # no timings configured → empty slot list

    # Fetch already-booked times for this doctor on this date
    booked_times = set(
        Appointment.objects.filter(
            doctor_code=doctor_code,
            appointment_date=appt_date,
            status__in=['pending', 'accepted'],
        ).values_list('appointment_time', flat=True)
    )
    # Generate slots for each timing window
    slots = []
    for t in timings:
        if not t.time1 or not t.time2:
            continue

        current = datetime.combine(appt_date, t.time1)
        end     = datetime.combine(appt_date, t.time2)

        while current + timedelta(minutes=slot_duration) <= end:
            slot_start = current.time()
            slot_end   = (current + timedelta(minutes=slot_duration)).time()

            is_booked = slot_start in booked_times

            slots.append({
                'slot_number': int(t.slno),
                'start_time':  slot_start.strftime('%H:%M'),
                'end_time':    slot_end.strftime('%H:%M'),
                'status':      'Booked' if is_booked else 'Vacant',
            })
            current += timedelta(minutes=slot_duration)

    return Response(slots)


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
    # Filter to this client's appointments only
    client_id = get_client_id(request)
    if client_id:
        qs = qs.filter(client_id=client_id)
    s = request.query_params.get('status')
    if s in ('pending', 'accepted', 'rejected'):
        qs = qs.filter(status=s)
    serializer = AppointmentSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_appointment(request):
    """
    POST /api/appointments/create/
    Accepts two payload shapes:

    Shape A (from RequestAppointment page — public booking):
      { patient_name, phone_number, doctor_code, department_code,
        appointment_date (ISO datetime string), slot_number }

    Shape B (from Admin panel):
      { patient_name, phone, doctor_name, doctor_code, department_name,
        appointment_date (YYYY-MM-DD), appointment_time (HH:MM),
        appointment_type, status }
    """
    from app1.models import HmsDoctors

    data = request.data.copy()

    # ── Normalise phone field ─────────────────────────────────────────────
    if 'phone_number' in data and 'phone' not in data:
        data['phone'] = data.pop('phone_number')

    # ── Normalise doctor_name ─────────────────────────────────────────────
    if not data.get('doctor_name') and data.get('doctor_code'):
        try:
            doc = HmsDoctors.objects.get(code=data['doctor_code'])
            data['doctor_name'] = doc.name or data['doctor_code']
        except HmsDoctors.DoesNotExist:
            data['doctor_name'] = data['doctor_code']

    # ── Normalise department_name ─────────────────────────────────────────
    if not data.get('department_name') and data.get('department_code'):
        data['department_name'] = data.pop('department_code')

    # ── Parse appointment_date / appointment_time ─────────────────────────
    # Shape A sends a single ISO datetime in appointment_date.
    # Shape B sends separate YYYY-MM-DD + HH:MM fields.
    raw_date = data.get('appointment_date', '')
    if 'T' in str(raw_date) or 'Z' in str(raw_date):
        # ISO datetime → split into date + time
        try:
            dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
            # Convert UTC → IST for storage
            ist_dt = dt + timedelta(hours=5, minutes=30)
            data['appointment_date'] = ist_dt.strftime('%Y-%m-%d')
            if not data.get('appointment_time'):
                data['appointment_time'] = ist_dt.strftime('%H:%M')
        except Exception:
            pass  # let the serializer report the error

    # ── If slot_number is present, fill appointment_time from slot ────────
    if 'slot_number' in data and not data.get('appointment_time'):
        from app1.models import HmsDoctorstiming
        try:
            timing = HmsDoctorstiming.objects.get(
                code=data.get('doctor_code', ''),
                slno=data['slot_number'],
            )
            if timing.time1:
                data['appointment_time'] = timing.time1.strftime('%H:%M')
        except HmsDoctorstiming.DoesNotExist:
            pass

    # Default appointment_type if missing
    if not data.get('appointment_type'):
        data['appointment_type'] = 'Consultation'

    serializer = AppointmentCreateSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Stamp client_id from JWT (or from payload for public bookings)
    client_id = get_client_id(request) or data.get('client_id', '')
    appointment = serializer.save(client_id=client_id)
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

