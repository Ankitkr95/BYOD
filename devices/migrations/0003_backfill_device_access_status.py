# Generated migration to backfill existing devices

from django.db import migrations


def backfill_device_data(apps, schema_editor):
    """
    Backfill existing devices with:
    - access_status='active' (all existing devices should be active)
    - registered_by=user (device owner)
    """
    Device = apps.get_model('devices', 'Device')
    
    for device in Device.objects.all():
        # Set access_status to 'active' for all existing devices
        device.access_status = 'active'
        
        # Set registered_by to device owner if not set
        if not device.registered_by_id:
            device.registered_by = device.user
        
        device.save(update_fields=['access_status', 'registered_by'])


def reverse_backfill(apps, schema_editor):
    """
    Reverse migration - set all devices back to pending
    """
    Device = apps.get_model('devices', 'Device')
    Device.objects.all().update(access_status='pending', registered_by=None)


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0002_device_access_status_device_registered_by_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_device_data, reverse_backfill),
    ]
