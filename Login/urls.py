from django.urls import path
from . import views

urlpatterns = [
    path('admin/login/',     views.admin_login,   name='admin-login'),
    path('token/refresh/',   views.token_refresh, name='token-refresh'),
    path('logout/',          views.logout,        name='logout'),
]
