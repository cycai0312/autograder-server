import os
from typing import Any

from django.db import transaction

import autograder.core.utils as core_ut
from autograder.core.models.ag_model_base import AutograderModelManager

from .ag_command_result_base import AGCommandResultBase


class AGCommandResult(AGCommandResultBase):
    """
    Contains the core run results of a Command.
    """
    objects = AutograderModelManager['AGCommandResult']()

    @property
    def stdout_filename(self) -> str:
        if not self.pk:
            raise AttributeError(
                'stdout_filename is not available until the AGCommandResult has been saved')

        return os.path.join(core_ut.misc_cmd_output_dir(), 'cmd_result_{}_stdout'.format(self.pk))

    @property
    def stderr_filename(self) -> str:
        if not self.pk:
            raise AttributeError(
                'stderr_filename is not available until the AGCommandResult has been saved')

        return os.path.join(core_ut.misc_cmd_output_dir(), 'cmd_result_{}_stderr'.format(self.pk))

    def save(self, *args: Any, **kwargs: Any) -> None:
        is_create = self.pk is None

        with transaction.atomic():
            super().save(*args, **kwargs)

            if is_create:
                os.makedirs(core_ut.misc_cmd_output_dir(), exist_ok=True)
                open(self.stdout_filename, 'w').close()
                open(self.stderr_filename, 'w').close()

                self.save()

    # We won't define any serialization settings here because run results
    # are typically processed through some sort of "result feedback" class
    # before being serialized.
