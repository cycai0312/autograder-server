import os
import shutil

from django.db import models
from django.conf import settings
from django.core import exceptions

import autograder.core.utils as core_ut
import autograder.core.constants as const

from ..ag_model_base import AutograderModel
from .project import Project


def _get_project_file_upload_to_path(instance, filename):
    return os.path.join(
        core_ut.get_project_files_relative_dir(instance.project), filename)


# For migrations backwards compatibility
def _get_project_file_upload_to_dir(instance, filename):
    return _get_project_file_upload_to_path(instance, filename)


def _validate_filename(file_obj):
    core_ut.check_user_provided_filename(file_obj.name)


class UploadedFile(AutograderModel):
    """
    These objects provide a means for storing uploaded files
    to be used in project test cases.
    """
    _DEFAULT_TO_DICT_FIELDS = frozenset([
        'project',
        'name',
        'size',
    ])

    @classmethod
    def get_default_to_dict_fields(class_):
        return class_._DEFAULT_TO_DICT_FIELDS

    @classmethod
    def is_read_only(class_):
        return True

    project = models.ForeignKey(Project, related_name='uploaded_files')
    file_obj = models.FileField(
        upload_to=_get_project_file_upload_to_path,
        validators=[_validate_filename],
        max_length=const.MAX_CHAR_FIELD_LEN * 2)

    @property
    def name(self):
        return self.basename

    def rename(self, new_name):
        """
        Renames the file stored in this model instance.
        Any path information in new_name is stripped before renaming the
        file, for security reasons.
        """
        new_name = os.path.basename(new_name)
        try:
            core_ut.check_user_provided_filename(new_name)
        except exceptions.ValidationError as e:
            raise exceptions.ValidationError({'name': e.message})

        old_abspath = self.abspath
        self.file_obj.name = _get_project_file_upload_to_path(self, new_name)
        new_abspath = self.abspath

        shutil.move(old_abspath, new_abspath)
        self.save()

    @property
    def abspath(self):
        return os.path.join(settings.MEDIA_ROOT, self.file_obj.name)

    @property
    def basename(self):
        return os.path.basename(self.file_obj.name)

    @property
    def size(self):
        return self.file_obj.size
