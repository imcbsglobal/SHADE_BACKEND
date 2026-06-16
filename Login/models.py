from django.db import models


class DoctorCredential(models.Model):
    """Stores login credentials for doctor accounts, scoped to a client."""
    doctor_code = models.CharField(max_length=20)
    doctor_name = models.CharField(max_length=200, blank=True, default='')
    department  = models.CharField(max_length=200, blank=True, default='')
    email       = models.EmailField()
    password    = models.CharField(max_length=255)   # stored hashed via Django's make_password
    client_id   = models.CharField(max_length=20, blank=True, default='')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['doctor_name']
        unique_together = [('doctor_code', 'client_id')]

    def __str__(self):
        return f'{self.doctor_name} ({self.doctor_code})'
