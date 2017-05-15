# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2017-05-15 21:40
from __future__ import unicode_literals

import autograder.core.models.ag_model_base
import autograder.core.tests.test_models.models
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='_DummyAutograderModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pos_num_val', models.IntegerField(validators=[django.core.validators.MinValueValidator(0)])),
                ('non_empty_str_val', models.TextField(validators=[django.core.validators.MinLengthValidator(1)])),
                ('read_only_field', models.TextField(blank=True)),
                ('not_settable_on_create_field', models.IntegerField(blank=True, default=77)),
            ],
            options={
                'abstract': False,
            },
            bases=(autograder.core.models.ag_model_base._AutograderModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='_DummyForeignAutograderModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
            bases=(autograder.core.models.ag_model_base._AutograderModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='_DummyToManyModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(autograder.core.models.ag_model_base._AutograderModelMixin, models.Model),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='another_many_to_many',
            field=models.ManyToManyField(to='test_models._DummyToManyModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='foreign_key',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rev_foreign_key', to='test_models._DummyForeignAutograderModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='many_to_many',
            field=models.ManyToManyField(related_name='many_to_manys', to='test_models._DummyToManyModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='nullable_foreign_key',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='test_models._DummyForeignAutograderModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='nullable_one_to_one',
            field=models.OneToOneField(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='test_models._DummyForeignAutograderModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='one_to_one',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='rev_one_to_one', to='test_models._DummyForeignAutograderModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='transparent_foreign_key',
            field=models.OneToOneField(default=autograder.core.tests.test_models.models._make_default_dummy_foreign_ag_model, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='test_models._DummyForeignAutograderModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='transparent_to_one',
            field=models.OneToOneField(default=autograder.core.tests.test_models.models._make_default_dummy_foreign_ag_model, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='test_models._DummyForeignAutograderModel'),
        ),
        migrations.AddField(
            model_name='_dummyautogradermodel',
            name='users',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL),
        ),
    ]
