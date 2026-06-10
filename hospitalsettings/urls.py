from django.urls import path
from . import views

urlpatterns = [
    path('',        views.get_settings,    name='settings-get'),
    path('update/', views.update_settings, name='settings-update'),
    path('reset/',  views.reset_settings,  name='settings-reset'),
]
