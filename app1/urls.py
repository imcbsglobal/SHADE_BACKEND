from django.urls import path
from .views import get_all_doctors

urlpatterns = [
    # GET /api/doctors/
    path('', get_all_doctors, name='get_all_doctors'),
]
