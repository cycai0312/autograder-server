# Generated by Django 3.2.2 on 2024-11-24 01:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0110_alter_extralatedays_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='group',
            name='late_days_used',
        ),
    ]
