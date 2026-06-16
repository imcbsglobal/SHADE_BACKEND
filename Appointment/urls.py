from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.list_appointments,  name='appointment-list'),
    path('slots/',              views.get_doctor_slots,   name='appointment-slots'),
    path('create/',             views.create_appointment, name='appointment-create'),
    path('<int:pk>/status/',    views.update_status,      name='appointment-status'),
    path('<int:pk>/delete/',    views.delete_appointment, name='appointment-delete'),
]
