from django.db import models
from django.core import validators, exceptions

from ..ag_model_base import AutograderModel
from .project import Project

import autograder.core.shared.global_constants as gc
import autograder.utilities.fields as ag_fields


class ExpectedStudentFilePattern(AutograderModel):
    """
    These objects describe Unix-style shell patterns that files
    submitted by students can or should match.
    """
    class Meta:
        unique_together = ('pattern', 'project')

    project = models.ForeignKey(Project)

    pattern = ag_fields.ShortStringField(
        validators=[validators.RegexValidator(
            gc.PROJECT_FILE_PATTERN_WHITELIST_REGEX)],
        help_text='''A shell-style file pattern suitable for
            use with Python's fnmatch.fnmatch()
            function (https://docs.python.org/3.4/library/fnmatch.html)
            This string may contain the same characters allowed in
            project or student files as well as special pattern
            matching characters. This string must not be empty.''')

    min_num_matches = models.IntegerField(
        validators=[validators.MinValueValidator(0)],
        help_text='''The minimum number of submitted student files that
            should match the pattern. Must be non-negative.''')

    max_num_matches = models.IntegerField(
        help_text='''The maximum number of submitted student files that
            can match the pattern. Must be >= min_num_matches''')

    def clean(self):
        if self.max_num_matches < self.min_num_matches:
            raise exceptions.ValidationError(
                {'max_num_matches': (
                    'Maximum number of matches must be greater than or '
                    'equal to minimum number of matches')})
