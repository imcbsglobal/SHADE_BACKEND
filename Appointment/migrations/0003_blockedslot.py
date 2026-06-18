from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Appointment', '0002_appointment_client_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlockedSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doctor_code', models.CharField(max_length=20)),
                ('slot_date',   models.DateField()),
                ('start_time',  models.TimeField()),
                ('client_id',   models.CharField(blank=True, default='', max_length=20)),
                ('blocked_at',  models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['slot_date', 'start_time'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='blockedslot',
            unique_together={('doctor_code', 'slot_date', 'start_time', 'client_id')},
        ),
    ]
