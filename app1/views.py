from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def get_client_id(request) -> str | None:
    """
    Extract the client_id custom claim from the validated JWT token.
    Returns None for unauthenticated / public requests.
    """
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        auth = getattr(request, 'auth', None)   # the decoded token dict
        if auth:
            return auth.get('client_id') or None
    return None


@api_view(['GET'])
@permission_classes([AllowAny])
def get_hospital_info(request):
    """
    GET /api/hospital-info/
    Returns firm_name, address, mobile etc. from the Misel table.
    Filters by client_id from JWT when authenticated.
    """
    from .models import Misel
    try:
        client_id = get_client_id(request)
        qs = Misel.objects.all()
        if client_id:
            qs = qs.filter(client_id=client_id)
        row = qs.first()
        if not row:
            return Response({})
        return Response({
            'firm_name': row.firm_name or '',
            'address':   row.address   or '',
            'address1':  row.address1  or '',
            'address2':  row.address2  or '',
            'address3':  row.address3  or '',
            'mobile':    row.mobile    or '',
            'tinno':     row.tinno     or '',
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_doctors(request):
    """
    GET /api/doctors/
    Public endpoint — no authentication required.

    When called with a valid JWT (admin panel), results are filtered
    to the client_id embedded in the token.

    Response shape per doctor:
    {
        "code": "D001",
        "name": "Dr. Deepak Kumar",
        "department": "CARD",
        "qualification": "MBBS, MD",
        "timings": [
            { "slno": 1, "time1": "09:00", "time2": "13:00" },
            { "slno": 2, "time1": "17:00", "time2": "20:00" }
        ]
    }
    """
    from .models import HmsDoctors, HmsDoctorstiming

    client_id = get_client_id(request)

    # Filter timings by client_id when available
    timing_qs = HmsDoctorstiming.objects.order_by('slno')
    if client_id:
        timing_qs = timing_qs.filter(client_id=client_id)

    timings_by_code: dict = {}
    for t in timing_qs:
        if t.code:
            timings_by_code.setdefault(t.code, []).append(t)

    # Filter doctors by client_id when available
    doctor_qs = HmsDoctors.objects.order_by('code')
    if client_id:
        doctor_qs = doctor_qs.filter(client_id=client_id)

    data = []
    for doc in doctor_qs:
        timings = timings_by_code.get(doc.code, [])
        data.append({
            'code':          doc.code,
            'name':          doc.name or '',
            'department':    doc.department or '',
            'qualification': doc.qualification or '',
            'timings': [
                {
                    'slno':  int(t.slno),
                    'time1': t.time1.strftime('%H:%M') if t.time1 else None,
                    'time2': t.time2.strftime('%H:%M') if t.time2 else None,
                }
                for t in timings
            ],
        })

    return Response(data)
