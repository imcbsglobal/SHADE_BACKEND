from django.contrib.auth import authenticate
import requests as http_requests
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import AdminLoginSerializer

LICENSE_API = 'https://activate.imcbs.com/mobileapp/api/project/shadehms/'


def validate_client_id(client_id: str) -> dict | None:
    """
    Calls the license server and returns the matching customer dict
    if client_id is found and Active, otherwise None.
    """
    try:
        resp = http_requests.get(LICENSE_API, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        for customer in data.get('customers', []):
            if (
                customer.get('client_id') == client_id
                and customer.get('status') == 'Active'
                and not customer.get('license_validity', {}).get('is_expired', True)
            ):
                return customer
    except Exception:
        pass
    return None


def get_tokens_for_user(user, client_id: str):
    """Return a fresh access/refresh token pair, embedding client_id in the payload."""
    refresh = RefreshToken.for_user(user)
    refresh['client_id'] = client_id          # custom claim — available on every request
    return {
        'refresh': str(refresh),
        'access':  str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    POST /api/auth/admin/login/
    Body: { "username": "...", "password": "...", "client_id": "..." }

    1. Validates client_id against the license server.
    2. Authenticates the Django user.
    3. Returns JWT tokens with client_id embedded in the payload.
    """
    serializer = AdminLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username  = serializer.validated_data['username']
    password  = serializer.validated_data['password']
    client_id = serializer.validated_data.get('client_id', '').strip()

    # ── 1. Validate client_id ──────────────────────────────────────────────
    if not client_id:
        return Response(
            {'detail': 'Client ID is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    customer = validate_client_id(client_id)
    if customer is None:
        return Response(
            {'detail': 'Invalid or expired Client ID. Please check your license.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ── 2. Authenticate Django user ───────────────────────────────────────
    # Support login with either username or email
    from django.contrib.auth.models import User as DjangoUser
    actual_username = username
    if '@' in username:
        try:
            actual_username = DjangoUser.objects.get(email=username).username
        except (DjangoUser.DoesNotExist, DjangoUser.MultipleObjectsReturned):
            actual_username = username

    user = authenticate(request, username=actual_username, password=password)

    if user is None:
        return Response(
            {'detail': 'Invalid username or password.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not (user.is_staff or user.is_superuser):
        return Response(
            {'detail': 'You do not have admin privileges.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not user.is_active:
        return Response(
            {'detail': 'This account has been deactivated.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ── 3. Issue tokens ───────────────────────────────────────────────────
    tokens = get_tokens_for_user(user, client_id)

    return Response({
        'access_token':  tokens['access'],
        'refresh_token': tokens['refresh'],
        'client_id':     client_id,
        'customer_name': customer.get('customer_name', ''),
        'user': {
            'id':           user.id,
            'username':     user.username,
            'email':        user.email,
            'first_name':   user.first_name,
            'last_name':    user.last_name,
            'is_staff':     user.is_staff,
            'is_superuser': user.is_superuser,
            'role':         'ADMIN',
        },
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh(request):
    """
    POST /api/auth/token/refresh/
    Body: { "refresh": "<refresh_token>" }
    """
    from rest_framework_simplejwt.serializers import TokenRefreshSerializer
    serializer = TokenRefreshSerializer(data=request.data)
    try:
        serializer.is_valid(raise_exception=True)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_401_UNAUTHORIZED)

    return Response(serializer.validated_data, status=status.HTTP_200_OK)


@api_view(['POST'])
def logout(request):
    """
    POST /api/auth/logout/
    Blacklists the refresh token.
    """
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)
    except Exception:
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════════════════════
# DOCTOR CREDENTIALS  — scoped to client_id from JWT
# ═══════════════════════════════════════════════════════════════════════════

def _get_client_id(request) -> str:
    auth = getattr(request, 'auth', None)
    return (auth.get('client_id') or '') if auth else ''


@api_view(['GET', 'POST'])
def doctor_credentials_list(request):
    """
    GET  /api/auth/doctor/credentials/  — list all credentials for this client
    POST /api/auth/doctor/credentials/  — create a new credential
    """
    from django.contrib.auth.hashers import make_password
    from .models import DoctorCredential

    client_id = _get_client_id(request)

    if request.method == 'GET':
        qs = DoctorCredential.objects.filter(client_id=client_id)
        data = [
            {
                'id':          c.id,
                'doctor_code': c.doctor_code,
                'doctor_name': c.doctor_name,
                'department':  c.department,
                'email':       c.email,
                'password':    '',          # never expose the hash
                'created_at':  c.created_at.isoformat(),
            }
            for c in qs
        ]
        return Response(data)

    # POST — create
    d = request.data
    doctor_code = d.get('doctor_code', '').strip()
    email       = d.get('email', '').strip()
    password    = d.get('password', '').strip()

    if not doctor_code or not email or not password:
        return Response(
            {'detail': 'doctor_code, email and password are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Look up doctor name/dept from hms_doctors if available
    doctor_name = d.get('doctor_name') or d.get('doctorName', '')
    department  = d.get('department', '')
    try:
        from app1.models import HmsDoctors
        doc = HmsDoctors.objects.get(code=doctor_code)
        doctor_name = doctor_name or doc.name or doctor_code
        department  = department  or doc.department or ''
    except Exception:
        doctor_name = doctor_name or doctor_code

    cred, created = DoctorCredential.objects.update_or_create(
        doctor_code=doctor_code,
        client_id=client_id,
        defaults={
            'doctor_name': doctor_name,
            'department':  department,
            'email':       email,
            'password':    make_password(password),
        },
    )
    return Response(
        {
            'id':          cred.id,
            'doctor_code': cred.doctor_code,
            'doctor_name': cred.doctor_name,
            'department':  cred.department,
            'email':       cred.email,
            'password':    '',
            'created_at':  cred.created_at.isoformat(),
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['PATCH', 'DELETE'])
def doctor_credentials_detail(request, doctor_code):
    """
    PATCH  /api/auth/doctor/credentials/<doctor_code>/  — update email / password
    DELETE /api/auth/doctor/credentials/<doctor_code>/  — remove credential
    """
    from django.contrib.auth.hashers import make_password
    from .models import DoctorCredential

    client_id = _get_client_id(request)

    try:
        cred = DoctorCredential.objects.get(doctor_code=doctor_code, client_id=client_id)
    except DoctorCredential.DoesNotExist:
        return Response({'detail': 'Credential not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        cred.delete()
        return Response({'doctor_code': doctor_code, 'success': True})

    # PATCH
    d = request.data
    if 'email' in d:
        cred.email = d['email'].strip()
    if d.get('password'):
        cred.password = make_password(d['password'].strip())
    if 'doctor_name' in d or 'doctorName' in d:
        cred.doctor_name = d.get('doctor_name') or d.get('doctorName', cred.doctor_name)
    if 'department' in d:
        cred.department = d['department']
    cred.save()

    return Response({
        'id':          cred.id,
        'doctor_code': cred.doctor_code,
        'doctor_name': cred.doctor_name,
        'department':  cred.department,
        'email':       cred.email,
        'password':    '',
        'created_at':  cred.created_at.isoformat(),
    })
