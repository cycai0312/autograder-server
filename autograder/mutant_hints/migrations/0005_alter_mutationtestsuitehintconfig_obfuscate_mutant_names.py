# Generated by Django 3.2.2 on 2024-01-04 15:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mutant_hints', '0004_auto_20240102_2129'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mutationtestsuitehintconfig',
            name='obfuscate_mutant_names',
            field=models.TextField(blank=True, choices=[('none', 'None'), ('sequential', 'Sequential'), ('hash', 'Hash')], default='none', help_text='Determines whether the mutant names included with\n            unlocked hints should be obfuscated. The options are as follows:\n            - "none": Do not obfuscate mutant names\n            - "sequential": Mutant names are obfuscated as "Mutant X",\n            where X is replaced with the index of the mutant in the\n            mutation test suite settings.\n            - "hash": Mutant names are obfuscated as "Mutant X", where X\n            is replaced with a hash generated using the mutant name and\n            some information unique to the current group. This ensures that\n            obfuscated mutant names are deterministic but unique to the\n            group they are shown to.\n\n        Note that the "Mutant" part of "Mutant X" in the above examples can\n        be changed in the obfuscated_mutant_name_prefix field.\n        '),
        ),
    ]
