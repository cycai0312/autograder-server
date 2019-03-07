# Generated by Django 2.0.1 on 2019-03-07 20:07

import sys

from django.db import migrations

from autograder.core.constants import SupportedImages, DOCKER_IMAGE_IDS_TO_URLS

import autograder_sandbox


def create_default_image(apps, schemea_editor):
    # The fixture autograder/core/fixture/default_sandbox_image.json handles
    # creating the default image during testing.
    if sys.argv[1] == 'test':
        return

    SandboxDockerImage = apps.get_model('core', 'SandboxDockerImage')
    SandboxDockerImage.objects.create(
        name='default',
        display_name='Default',
        tag=f'jameslp/autograder-sandbox:{autograder_sandbox.VERSION}'
    )


def migrate_legacy_images(apps, schema_editor):
    """
    Create a DB row for all images listed in constants.SupportedImages
    """
    SandboxDockerImage = apps.get_model('core', 'SandboxDockerImage')

    for image_name, image_tag in DOCKER_IMAGE_IDS_TO_URLS.items():
        print(image_name, image_tag)
        if image_name != SupportedImages.default:
            print(
                SandboxDockerImage.objects.create(
                    name=image_name.value, display_name=image_name.value, tag=image_tag))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_sandboxdockerimage'),
    ]

    operations = [
        migrations.RunPython(create_default_image, reverse_code=lambda apps, schema_editor: None),
        migrations.RunPython(migrate_legacy_images, reverse_code=lambda apps, schema_editor: None),
    ]
