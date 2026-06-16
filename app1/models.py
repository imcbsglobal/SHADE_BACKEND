from django.db import models


class ClientRegistration(models.Model):
    client_id = models.CharField(max_length=20, unique=True)
    machine_name = models.CharField(max_length=100, null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'client_registration'

    def __str__(self):
        return self.client_id


class HmsDoctors(models.Model):
    code = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=40, null=True, blank=True)
    rate = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    department = models.CharField(max_length=5, null=True, blank=True)
    avgcontime = models.IntegerField(null=True, blank=True)
    qualification = models.CharField(max_length=160, null=True, blank=True)
    client_id = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'hms_doctors'
        managed = False   # table already exists in your DB

    def __str__(self):
        return f"{self.code} - {self.name}"


class HmsDoctorstiming(models.Model):
    slno = models.DecimalField(max_digits=10, decimal_places=0, primary_key=True)
    code = models.CharField(max_length=5, null=True, blank=True)
    time1 = models.TimeField(null=True, blank=True)
    time2 = models.TimeField(null=True, blank=True)
    client_id = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'hms_doctorstiming'
        managed = False   # table already exists in your DB

    def __str__(self):
        return f"{self.slno} - {self.code}"


class Misel(models.Model):
    misel_primary = models.CharField(max_length=1, primary_key=True)
    firm_name = models.CharField(max_length=150, null=True, blank=True)
    address = models.CharField(max_length=40, null=True, blank=True)
    mobile = models.CharField(max_length=60, null=True, blank=True)
    address1 = models.CharField(max_length=50, null=True, blank=True)
    address2 = models.CharField(max_length=50, null=True, blank=True)
    address3 = models.CharField(max_length=50, null=True, blank=True)
    tinno = models.CharField(max_length=30, null=True, blank=True)
    client_id = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'misel'
        managed = False   # table already exists in your DB

    def __str__(self):
        return self.firm_name or self.misel_primary
