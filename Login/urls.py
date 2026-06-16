from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('admin/login/',     views.admin_login,   name='admin-login'),
    path('token/refresh/',   views.token_refresh, name='token-refresh'),
    path('logout/',          views.logout,        name='logout'),

    # Doctor credentials (admin JWT required)
    path('doctor/credentials/',
         views.doctor_credentials_list,   name='doctor-credentials-list'),
    path('doctor/credentials/<str:doctor_code>/',
         views.doctor_credentials_detail, name='doctor-credentials-detail'),
]
