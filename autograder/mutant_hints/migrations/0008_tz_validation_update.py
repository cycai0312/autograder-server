# Generated by Django 3.2.2 on 2024-01-29 20:21

import autograder.core.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mutant_hints', '0007_mutationtestsuitehintconfig_obfuscate_mutant_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mutationtestsuitehintconfig',
            name='hint_limit_reset_timezone',
            field=models.TextField(default='UTC', help_text='A string representing the timezone to use when computing\n            how many hints a group has unlocked in a 24 hour period.', validators=[autograder.core.utils.validate_timezone]),
        ),
    ]