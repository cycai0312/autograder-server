# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-05-15 18:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_remove_agtestcommandfeedbackconfig_show_whether_timed_out'),
    ]

    operations = [
        migrations.AddField(
            model_name='agtestcommandfeedbackconfig',
            name='show_whether_timed_out',
            field=models.BooleanField(default=False),
        ),
    ]