# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-04-17 03:11
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_uploadedfile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadedfile',
            name='file_obj',
            field=models.FileField(max_length=510, upload_to=''),
        ),
    ]