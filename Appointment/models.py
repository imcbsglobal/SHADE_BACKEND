from django.db import models


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    # Patient info
    patient_name = models.CharField(max_length=200)
    phone        = models.CharField(max_length=30, blank=True, default='')
    email        = models.EmailField(blank=True, default='')

    # Doctor / department (stored as plain text — no FK to keep it simple)
    doctor_name      = models.CharField(max_length=200, blank=True, default='')
    doctor_code      = models.CharField(max_length=20,  blank=True, default='')
    department_name  = models.CharField(max_length=200, blank=True, default='')

    # Scheduling
    appointment_date = models.DateField()
    appointment_time = models.TimeField()          # stored as HH:MM:SS
    appointment_type = models.CharField(max_length=100, blank=True, default='Consultation')

    # Status
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Client isolation
    client_id  = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.patient_name} — {self.doctor_name} ({self.appointment_date})'
