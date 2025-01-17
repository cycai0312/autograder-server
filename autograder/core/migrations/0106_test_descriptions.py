# Generated by Django 3.2.2 on 2024-08-05 21:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0105_tz_validation_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='agtestcase',
            name='staff_description',
            field=models.TextField(blank=True, help_text='Text description shown only to staff. Rendered as markdown.'),
        ),
        migrations.AddField(
            model_name='agtestcase',
            name='student_description',
            field=models.TextField(blank=True, help_text='Text description shown to students. Rendered as markdown.'),
        ),
        migrations.AddField(
            model_name='agtestcommand',
            name='staff_description',
            field=models.TextField(blank=True, help_text='Text description shown only to staff. Rendered as markdown.'),
        ),
        migrations.AddField(
            model_name='agtestcommand',
            name='student_description',
            field=models.TextField(blank=True, help_text='Text description shown to students. Rendered as markdown.'),
        ),
        migrations.AddField(
            model_name='agtestcommand',
            name='student_on_fail_description',
            field=models.TextField(blank=True, help_text='Additional text shown to students failing this test. Rendered as markdown.'),
        ),
        migrations.AddField(
            model_name='agtestsuite',
            name='staff_description',
            field=models.TextField(blank=True, help_text='Text description shown only to staff. Rendered as markdown.'),
        ),
        migrations.AddField(
            model_name='agtestsuite',
            name='student_description',
            field=models.TextField(blank=True, help_text='Text description shown to students. Rendered as markdown.'),
        ),
    ]
