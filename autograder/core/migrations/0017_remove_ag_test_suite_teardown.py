# Generated by Django 2.0.1 on 2018-06-05 15:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_add_new_ag_test_cmd_fdbk_conf_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='agtestsuite',
            name='teardown_suite_cmd',
        ),
        migrations.RemoveField(
            model_name='agtestsuite',
            name='teardown_suite_cmd_name',
        ),
        migrations.RemoveField(
            model_name='agtestsuiteresult',
            name='teardown_return_code',
        ),
        migrations.RemoveField(
            model_name='agtestsuiteresult',
            name='teardown_stderr',
        ),
        migrations.RemoveField(
            model_name='agtestsuiteresult',
            name='teardown_stderr_truncated',
        ),
        migrations.RemoveField(
            model_name='agtestsuiteresult',
            name='teardown_stdout',
        ),
        migrations.RemoveField(
            model_name='agtestsuiteresult',
            name='teardown_stdout_truncated',
        ),
        migrations.RemoveField(
            model_name='agtestsuiteresult',
            name='teardown_timed_out',
        ),
    ]