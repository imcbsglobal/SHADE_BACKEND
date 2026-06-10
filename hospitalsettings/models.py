from django.db import models


class HospitalSettings(models.Model):
    """
    Singleton model — there is always exactly one row (id=1).
    All settings are stored as a single JSON blob so the frontend
    schema can evolve freely without DB migrations for every field.
    """
    settings_data = models.JSONField(default=dict, blank=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Hospital Settings'
        verbose_name_plural = 'Hospital Settings'

    def __str__(self):
        return f'Hospital Settings (updated {self.updated_at:%Y-%m-%d %H:%M})'

    @classmethod
    def get_singleton(cls):
        """Always returns the single settings object, creating it if needed."""
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
