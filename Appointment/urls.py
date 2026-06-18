from django.urls import path
from . import views

urlpatterns = [
    path('',                          views.list_appointments,       name='appointment-list'),
    path('dashboard-stats/',          views.dashboard_stats,         name='dashboard-stats'),
    path('doctor-dashboard-stats/',   views.doctor_dashboard_stats,  name='doctor-dashboard-stats'),
    path('slots/',                    views.get_doctor_slots,        name='appointment-slots'),
    path('blocked-slots/',            views.get_blocked_slots,       name='blocked-slots-list'),
    path('blocked-slots/apply/',      views.apply_slot_changes,      name='blocked-slots-apply'),
    path('create/',                   views.create_appointment,      name='appointment-create'),
    path('<int:pk>/status/',          views.update_status,           name='appointment-status'),
    path('<int:pk>/delete/',          views.delete_appointment,      name='appointment-delete'),
]
