from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, date, timedelta

from .models import Appointment, BlockedSlot
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
    as 'Booked', 'Blocked', or 'Vacant' based on existing appointments
    and admin-blocked slots.

    Response: list of slot objects:
    [
      {
        "slot_number": 1,
        "start_time":  "09:00",
        "end_time":    "09:15",
        "status":      "Vacant" | "Booked" | "Blocked"
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

    try:
        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'date must be YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        doctor = HmsDoctors.objects.get(code=doctor_code)
        slot_duration = int(doctor.avgcontime or 15)
    except HmsDoctors.DoesNotExist:
        return Response(
            {'error': f'Doctor {doctor_code!r} not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    timings = HmsDoctorstiming.objects.filter(code=doctor_code).order_by('slno')
    if not timings.exists():
        return Response([])

    # Booked appointment times
    booked_times = set(
        Appointment.objects.filter(
            doctor_code=doctor_code,
            appointment_date=appt_date,
            status__in=['pending', 'accepted'],
        ).values_list('appointment_time', flat=True)
    )

    # Admin-blocked times (client-aware)
    client_id = get_client_id(request)
    blocked_qs = BlockedSlot.objects.filter(
        doctor_code=doctor_code,
        slot_date=appt_date,
    )
    if client_id:
        blocked_qs = blocked_qs.filter(client_id=client_id)
    blocked_times = set(blocked_qs.values_list('start_time', flat=True))

    slots = []
    for t in timings:
        if not t.time1 or not t.time2:
            continue

        current = datetime.combine(appt_date, t.time1)
        end     = datetime.combine(appt_date, t.time2)

        while current + timedelta(minutes=slot_duration) <= end:
            slot_start = current.time()
            slot_end   = (current + timedelta(minutes=slot_duration)).time()

            if slot_start in booked_times:
                slot_status = 'Booked'
            elif slot_start in blocked_times:
                slot_status = 'Blocked'
            else:
                slot_status = 'Vacant'

            slots.append({
                'slot_number': int(t.slno),
                'start_time':  slot_start.strftime('%H:%M'),
                'end_time':    slot_end.strftime('%H:%M'),
                'status':      slot_status,
            })
            current += timedelta(minutes=slot_duration)

    return Response(slots)


# ── Admin: Get blocked slots for a doctor/date ────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_blocked_slots(request):
    """
    GET /api/appointments/blocked-slots/?doctor_code=D001&date=2026-06-16
    Returns all blocked start_times for that doctor/date.
    """
    doctor_code = request.query_params.get('doctor_code', '').strip()
    date_str    = request.query_params.get('date', '').strip()

    if not doctor_code or not date_str:
        return Response({'error': 'doctor_code and date are required.'}, status=400)

    try:
        slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'date must be YYYY-MM-DD.'}, status=400)

    client_id = get_client_id(request)
    qs = BlockedSlot.objects.filter(doctor_code=doctor_code, slot_date=slot_date)
    if client_id:
        qs = qs.filter(client_id=client_id)

    blocked = [b.start_time.strftime('%H:%M') for b in qs]
    return Response({'blocked_times': blocked})


# ── Admin: Apply block/unblock changes ────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAdminUser])
def apply_slot_changes(request):
    """
    POST /api/appointments/blocked-slots/apply/
    Body: {
      "doctor_code": "D001",
      "date": "2026-06-17",
      "block":   ["09:00", "09:15"],
      "unblock": ["09:30"]
    }
    """
    doctor_code = request.data.get('doctor_code', '').strip()
    date_str    = request.data.get('date', '').strip()
    to_block    = request.data.get('block',   [])
    to_unblock  = request.data.get('unblock', [])

    if not doctor_code or not date_str:
        return Response({'error': 'doctor_code and date are required.'}, status=400)

    try:
        slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'date must be YYYY-MM-DD.'}, status=400)

    client_id = get_client_id(request) or ''

    # Block
    for t in to_block:
        try:
            parsed = datetime.strptime(t, '%H:%M').time()
            BlockedSlot.objects.get_or_create(
                doctor_code=doctor_code,
                slot_date=slot_date,
                start_time=parsed,
                client_id=client_id,
            )
        except ValueError:
            pass  # skip malformed times

    # Unblock
    for t in to_unblock:
        try:
            parsed = datetime.strptime(t, '%H:%M').time()
            BlockedSlot.objects.filter(
                doctor_code=doctor_code,
                slot_date=slot_date,
                start_time=parsed,
                client_id=client_id,
            ).delete()
        except ValueError:
            pass

    return Response({'success': True})


# ── Doctor Dashboard Stats ────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def doctor_dashboard_stats(request):
    """
    GET /api/appointments/doctor-dashboard-stats/

    Returns stats for the logged-in doctor's dashboard:
    - today's appointments, pending, accepted, recent activity list
    - today's schedule (appointment_date = today)
    Reads doctor_code from the JWT claim.
    """
    auth        = getattr(request, 'auth', None)
    doctor_code = (auth.get('doctor_code') if auth else None) or \
                  request.query_params.get('doctor_code', '').strip()

    if not doctor_code:
        return Response({'error': 'doctor_code not found in token.'}, status=400)

    today = date.today()

    base_qs   = Appointment.objects.filter(doctor_code=doctor_code)
    today_qs  = base_qs.filter(appointment_date=today)

    today_total = today_qs.count()
    pending     = today_qs.filter(status='pending').count()
    accepted    = today_qs.filter(status='accepted').count()

    # Recent activity — last 6 appointments (any date)
    recent = base_qs.order_by('-created_at')[:6]
    recent_list = [
        {
            'id':               a.id,
            'patient_name':     a.patient_name,
            'doctor_name':      a.doctor_name or a.doctor_code,
            'appointment_date': a.appointment_date.isoformat(),
            'appointment_time': a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'status':           a.status,
        }
        for a in recent
    ]

    # Today's schedule — for the table
    today_schedule = [
        {
            'id':               a.id,
            'patient_name':     a.patient_name,
            'department_name':  a.department_name or 'General',
            'appointment_time': a.appointment_time.strftime('%H:%M') if a.appointment_time else '',
            'status':           a.status,
        }
        for a in today_qs.order_by('appointment_time')
    ]

    return Response({
        'today_total':    today_total,
        'pending':        pending,
        'accepted':       accepted,
        'recent_activity': recent_list,
        'today_schedule':  today_schedule,
    })


# ── List + Create ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def list_appointments(request):
    """
    GET /api/appointments/
    Returns all appointments ordered by newest first.
    Supports ?status=pending|accepted|rejected filter.
    Also supports ?doctor=<code> for doctor-scoped access (doctor JWT).
    """
    from rest_framework_simplejwt.authentication import JWTAuthentication

    qs = Appointment.objects.all()

    # If called with a doctor JWT (non-admin), filter to that doctor's appointments
    auth = getattr(request, 'auth', None)
    doctor_code_claim = auth.get('doctor_code') if auth else None
    if doctor_code_claim:
        qs = qs.filter(doctor_code=doctor_code_claim)
    else:
        # Admin path — filter by client_id
        client_id = get_client_id(request)
        if client_id:
            qs = qs.filter(client_id=client_id)
        # Allow ?doctor= filter for admin too
        doc = request.query_params.get('doctor', '').strip()
        if doc:
            qs = qs.filter(doctor_code=doc)

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

    # Public bookings (no status in payload) default to 'accepted' automatically
    if not data.get('status'):
        data['status'] = 'accepted'
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


# ── Dashboard Stats ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAdminUser])
def dashboard_stats(request):
    """
    GET /api/appointments/dashboard-stats/

    Returns all data needed to render the admin dashboard in one call:
    - Metric counters (doctors, total, today, accepted, pending, rejected)
    - Last 6 appointments for the activity feed (with doctor_name)
    - Weekly trend (last 7 days) — per-day totals, accepted, pending
    - Monthly trend (last 6 months) — per-month totals, accepted, pending

    All counts are scoped to the client_id from the JWT.
    """
    from app1.models import HmsDoctors
    from django.db.models import Count
    from django.db.models.functions import TruncDate, TruncMonth

    client_id = get_client_id(request)

    # ── Base queryset ─────────────────────────────────────────────────────
    qs = Appointment.objects.all()
    if client_id:
        qs = qs.filter(client_id=client_id)

    today = date.today()

    # ── Metric counts ─────────────────────────────────────────────────────
    total_apts   = qs.count()
    today_apts   = qs.filter(appointment_date=today).count()
    accepted     = qs.filter(status='accepted').count()
    pending      = qs.filter(status='pending').count()
    rejected     = qs.filter(status='rejected').count()

    # Doctor count (client-scoped)
    doc_qs = HmsDoctors.objects.all()
    if client_id:
        doc_qs = doc_qs.filter(client_id=client_id)
    total_doctors = doc_qs.count()

    # ── Recent activity — last 6 appointments ────────────────────────────
    recent = qs.order_by('-created_at')[:6]
    recent_list = [
        {
            'id':               a.id,
            'patient_name':     a.patient_name,
            'doctor_name':      a.doctor_name or a.doctor_code,
            'appointment_date': a.appointment_date.isoformat(),
            'status':           a.status,
        }
        for a in recent
    ]

    # ── Weekly trend — last 7 calendar days ──────────────────────────────
    week_start = today - timedelta(days=6)
    week_qs    = qs.filter(appointment_date__gte=week_start)

    # Build a dict: date_str → {total, accepted, pending}
    week_map = {}
    for i in range(7):
        d = week_start + timedelta(days=i)
        week_map[d.isoformat()] = {'day': d.strftime('%a'), 'appointments': 0, 'completed': 0, 'pending': 0}

    for a in week_qs.values('appointment_date', 'status'):
        key = a['appointment_date'].isoformat() if hasattr(a['appointment_date'], 'isoformat') else str(a['appointment_date'])
        if key in week_map:
            week_map[key]['appointments'] += 1
            if a['status'] == 'accepted':
                week_map[key]['completed'] += 1
            elif a['status'] == 'pending':
                week_map[key]['pending'] += 1

    weekly_trend = list(week_map.values())

    # ── Monthly trend — last 6 months ─────────────────────────────────────
    month_start = (today.replace(day=1) - timedelta(days=150)).replace(day=1)
    month_qs    = qs.filter(appointment_date__gte=month_start)

    month_map = {}
    for i in range(6):
        # Build month keys going back 5 months from current
        m_date = (today.replace(day=1) - timedelta(days=30 * (5 - i)))
        key = m_date.strftime('%Y-%m')
        month_map[key] = {'month': m_date.strftime('%b'), 'appointments': 0, 'completed': 0, 'pending': 0}

    for a in month_qs.values('appointment_date', 'status'):
        key = a['appointment_date'].strftime('%Y-%m') if hasattr(a['appointment_date'], 'strftime') else str(a['appointment_date'])[:7]
        if key in month_map:
            month_map[key]['appointments'] += 1
            if a['status'] == 'accepted':
                month_map[key]['completed'] += 1
            elif a['status'] == 'pending':
                month_map[key]['pending'] += 1

    monthly_trend = list(month_map.values())

    return Response({
        'metrics': {
            'total_doctors':   total_doctors,
            'total_apts':      total_apts,
            'today_apts':      today_apts,
            'accepted':        accepted,
            'pending':         pending,
            'rejected':        rejected,
        },
        'recent_activity': recent_list,
        'weekly_trend':    weekly_trend,
        'monthly_trend':   monthly_trend,
    })

