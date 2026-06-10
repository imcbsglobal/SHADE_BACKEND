from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import AdminLoginSerializer


def get_tokens_for_user(user):
    """Return a fresh access/refresh token pair for a User instance."""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access':  str(refresh.access_token),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    POST /api/auth/admin/login/
    Body: { "username": "...", "password": "..." }

    Returns JWT tokens + basic user info on success.
    Only staff/superuser accounts are allowed.
    """
    serializer = AdminLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data['username']
    password = serializer.validated_data['password']

    user = authenticate(request, username=username, password=password)

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

    tokens = get_tokens_for_user(user)

    return Response({
        'access_token':  tokens['access'],
        'refresh_token': tokens['refresh'],
        'user': {
            'id':         user.id,
            'username':   user.username,
            'email':      user.email,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'is_staff':   user.is_staff,
            'is_superuser': user.is_superuser,
            'role':       'ADMIN',
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
    Header: Authorization: Bearer <access_token>
    Body: { "refresh": "<refresh_token>" }

    Blacklists the refresh token so it can't be reused.
    """
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)
    except Exception:
        # Even if blacklist fails, treat as logged out
        return Response({'detail': 'Logged out.'}, status=status.HTTP_200_OK)
