from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .models import HospitalSettings
from .serializers import HospitalSettingsSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def get_settings(request):
    """
    GET /api/settings/
    Public endpoint — returns the full settings JSON.
    Used by the public site (Home, Login pages) to apply branding.
    """
    obj = HospitalSettings.get_singleton()
    serializer = HospitalSettingsSerializer(obj)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAdminUser])
def update_settings(request):
    """
    PATCH /api/settings/update/
    Admin-only — merges the incoming JSON into the stored settings.

    Supports partial updates: only the top-level keys you send are
    overwritten; everything else is preserved.
    """
    obj = HospitalSettings.get_singleton()

    incoming = request.data.get('settings_data')
    if incoming is None:
        # Accept flat payload too (the whole body IS the settings)
        incoming = request.data

    if not isinstance(incoming, dict):
        return Response(
            {'detail': 'settings_data must be a JSON object.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Deep-merge: update only the top-level keys that were sent
    merged = {**obj.settings_data, **incoming}
    obj.settings_data = merged
    obj.save()

    serializer = HospitalSettingsSerializer(obj)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reset_settings(request):
    """
    POST /api/settings/reset/
    Admin-only — clears all settings back to an empty dict.
    """
    obj = HospitalSettings.get_singleton()
    obj.settings_data = {}
    obj.save()
    return Response({'detail': 'Settings reset to defaults.'}, status=status.HTTP_200_OK)
