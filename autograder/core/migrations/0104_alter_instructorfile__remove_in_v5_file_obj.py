# Generated by Django 3.2.2 on 2022-04-13 14:48

import autograder.core.models.project.instructor_file
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0103_rename_file_obj_instructorfile__remove_in_v5_file_obj'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instructorfile',
            name='_remove_in_v5_file_obj',
            field=models.FileField(blank=True, max_length=510, null=True, upload_to=autograder.core.models.project.instructor_file._get_project_file_upload_to_path),
        ),
    ]
