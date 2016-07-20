# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2016-07-20 16:50
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_auto_20160719_0136'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='autogradertestcasebase',
            name='post_deadline_final_submission_feedback_configuration',
        ),
        migrations.AddField(
            model_name='autogradertestcasebase',
            name='past_submission_limit_fdbk_conf',
            field=models.OneToOneField(blank=True, help_text='The feedback configuration to be used when a result\n            belongs to a submission that is past the daily submission\n            limit. If not specified, this field is set to a default\n            initialized FeedbackConfig object.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.FeedbackConfig'),
        ),
        migrations.AddField(
            model_name='autogradertestcasebase',
            name='staff_viewer_fdbk_conf',
            field=models.OneToOneField(blank=True, help_text='The feedback configuration to be used when a result\n            belongs to a submission being viewed by an outside staff\n            member. If not specified, this field is set to\n            FeedbackConfig.create_with_max_fdbk().', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.FeedbackConfig'),
        ),
        migrations.AddField(
            model_name='autogradertestcasebase',
            name='ultimate_submission_fdbk_conf',
            field=models.OneToOneField(blank=True, help_text="The feedback configuration to be used when a result\n            belongs to a group's ultimate submission. If not specified,\n            this field is set to\n            FeedbackConfig.create_ultimate_submission_default()", null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.FeedbackConfig'),
        ),
        migrations.AddField(
            model_name='autogradertestcasebase',
            name='visible_in_past_limit_submission',
            field=models.BooleanField(default=False, help_text='Indicates whether results for this test case should\n            be shown to students when part of a submission that is past\n            the daily limit.'),
        ),
        migrations.AddField(
            model_name='autogradertestcasebase',
            name='visible_in_ultimate_submission',
            field=models.BooleanField(default=True, help_text="Indicates whether results for this test case should\n            be shown to students when part of a group's ultimate\n            submission."),
        ),
        migrations.AddField(
            model_name='autogradertestcasebase',
            name='visible_to_staff_viewer',
            field=models.BooleanField(default=True, help_text="Indicates whether results for this test case should\n            be shown to staff members viewing another group's\n            submission."),
        ),
        migrations.AddField(
            model_name='autogradertestcasebase',
            name='visible_to_students',
            field=models.BooleanField(default=False, help_text='Indicates whether results for this test case should\n            be shown to students under normal circumstances.'),
        ),
        migrations.AlterField(
            model_name='autogradertestcasebase',
            name='feedback_configuration',
            field=models.OneToOneField(blank=True, help_text='Specifies how much information should be included\n            in serialized test case results in normal situations. If not\n            specified, this field is set to a default-constructed\n            FeedbackConfig object.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ag_test', to='core.FeedbackConfig'),
        ),
    ]
