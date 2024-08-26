from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, cast
from datetime import datetime
import zoneinfo

import django.contrib.postgres.fields as pg_fields
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

import autograder.core.utils as core_ut
from autograder import utils
from autograder.core import constants

from .. import ag_model_base
from ..project import Project
from ..submission import Submission
from . import verification


class GroupManager(ag_model_base.AutograderModelManager['Group']):
    # Technically this violates the Liskov Substitution Principal.
    # However, Group.objects will always be an instance of
    # GroupManager typed as such, so we know this to be safe.
    def validate_and_create(  # type: ignore
        self,
        members: Iterable[User],
        check_group_size_limits: bool = True,
        **kwargs: object
    ) -> Group:
        """
        New parameters:
            check_group_size_limits -- When False, validation of whether
                the number of users is within the specified project limits
                will NOT be run.
                Default value: True
        """
        with transaction.atomic():
            verification.verify_users_can_be_in_group(
                members,
                cast(Project, kwargs['project']),
                'members',
                check_group_size_limits=check_group_size_limits
            )

            member_names = [
                user.username for user in sorted(members, key=lambda user: user.username)]
            group = self.model(_member_names=member_names, **kwargs)
            group.full_clean()
            group.save()
            group.members.add(*members)
            return group


class Group(ag_model_base.AutograderModel):
    """
    This class represents a group of students that can submit
    to a particular project.

    Related object fields:
        submissions -- The Submissions that this group has made for the
            associated Project.
    """

    class Meta:
        ordering = ('_member_names',)

    objects = GroupManager()

    members = models.ManyToManyField(
        User, related_name="groups_is_member_of",
        help_text="""The Users that belong to this submission group.
            This list must contain at least one member and no more than
            project.max_group_size members. A User can only be a member
            of one submission group per project.
            This field is REQUIRED.""")

    @property
    def member_names(self) -> List[str]:
        """A list of usernames of the group members, sorted alphabetically."""
        return self._member_names

    _member_names = pg_fields.ArrayField(
        models.CharField(max_length=constants.MAX_USERNAME_LEN),
        default=list,
        help_text="""A list of usernames of the group members, sorted alphabetically.
                     This field is updated automatically when self.members is updated
                     through self.validate_and_update""")

    project = models.ForeignKey(Project, related_name="groups",
                                on_delete=models.CASCADE)

    @property
    def extended_due_date(self) -> Optional[datetime]:
        return self.soft_extended_due_date

    @extended_due_date.setter
    def extended_due_date(self, value: Optional[datetime]) -> None:
        self.soft_extended_due_date = value
        self.hard_extended_due_date = value

    hard_extended_due_date = models.DateTimeField(
        null=True, default=None, blank=True,
        help_text="""When this field is set, it indicates that members
            of this submission group can submit until this specified
            date, overriding the project closing time.
            Default value: None""")

    soft_extended_due_date = models.DateTimeField(
        null=True, default=None, blank=True,
        help_text="""When this field is set, it indicates the extended due date
            that is visible to members of the group. Members of the group will
            still be able to submit after this date but before the
            extended_due_date.
            Default value: None""")

    # Remove in version 5.0.0
    old_bonus_submissions_remaining = models.IntegerField(
        blank=True,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="""The number of bonus submissions this group has left.
            This field is automatically initialized to self.project.num_bonus_submissions"""
    )

    @property
    def bonus_submissions_remaining(self) -> int:
        """The number of unused bonus submission tokens this group has."""
        return max(0, self._true_bonus_submissions_remaining)

    @bonus_submissions_remaining.setter
    def bonus_submissions_remaining(self, value: int) -> None:
        if value < 0:
            raise ValidationError({
                'bonus_submissions_remaining': 'This value cannot be negative.'
            })

        self._extra_bonus_submissions_granted += value - self._true_bonus_submissions_remaining

    @property
    def _true_bonus_submissions_remaining(self) -> int:
        """
        This internal computation of the Group's bonus submission count
        can be negative and is used in computations to update the total.
        """
        return (
            self.project.num_bonus_submissions + self._extra_bonus_submissions_granted
            - self.bonus_submissions_used
        )

    _extra_bonus_submissions_granted = models.IntegerField(blank=True, default=0)
    bonus_submissions_used = models.IntegerField(
        blank=True, default=0, validators=[MinValueValidator(0)])

    late_days_used = models.JSONField(
        default=dict, blank=True,
        help_text=r"""Keeps track of how many late days each user in this
            group has used.
            Data format: {
                "\<username\>": \<num late days used\>,
                ...
            }
            NOTE: This field is updated only when a group member uses a
            late day. If a user is moved to another group or this group
            is merged with another one, this field will NOT be updated.
        """
    )

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def num_submissions(self) -> int:
        return self.submissions.count()

    @property
    def num_submits_towards_limit(self) -> int:
        """
        The number of submissions this group has made in the current 24
        hour period that are counted towards the daily submission limit.
        """
        # We put the filtering logic here so that we can prefetch all
        # submissions in the list groups view.
        start_datetime, end_datetime = core_ut.get_24_hour_period(
            self.project.submission_limit_reset_time,
            timezone.now().astimezone(
                zoneinfo.ZoneInfo(self.project.submission_limit_reset_timezone)
            )
        )

        def _is_towards_limit(submission: Submission) -> bool:
            return (start_datetime <= submission.timestamp < end_datetime
                    and submission.status in Submission.count_towards_limit_statuses)

        return utils.count_if(self.submissions.all(), _is_towards_limit)

    def clean(self) -> None:
        super().clean()

        try:
            clean_soft, clean_hard = core_ut.clean_and_validate_soft_and_hard_deadlines(
                self.soft_extended_due_date, self.hard_extended_due_date)
        except core_ut.InvalidSoftDeadlineError:
            raise ValidationError(
                {'soft_extended_due_date': (
                    'Soft extended due date must be a valid date')})
        except core_ut.InvalidHardDeadlineError:
            raise ValidationError(
                {'extended_due_date': (
                    'Hard extended due date must be a valid date')})
        except core_ut.HardDeadlineBeforeSoftDeadlineError:
            raise ValidationError(
                {'soft_extended_due_date': (
                    'Soft extended due date must not be after hard extended due date')})

        self.soft_extended_due_date = clean_soft
        self.hard_extended_due_date = clean_hard

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)

        group_dir = core_ut.get_student_group_dir(self)
        if not os.path.isdir(group_dir):
            os.makedirs(group_dir)

    # IMPORTANT: If you add additional non-field arguments
    # (like check_group_size_limits), update group patching
    # in autograder/rest_api/views/group_views.py - GroupDetailView.patch
    def validate_and_update(  # type: ignore
        self,
        *,
        check_group_size_limits: bool = True,
        ignore_guest_restrictions: bool = False,
        **kwargs: object
    ) -> None:
        """
        New parameters:
            check_group_size_limits -- When False, validation of
                whether the group size is within specified project limits
                will NOT be performed. Defaults to True.

            ignore_guest_restrictions -- When True, validation of
                whether the group members are a mix of students and
                guests and whether guests can submit will NOT be
                performed. Defaults to False.

        This method is overridden to provide validation and atomicity
        when overwriting the members field.
        """
        members = cast(Iterable[User], kwargs.pop('members', None))
        with transaction.atomic():
            super().validate_and_update(**kwargs)
            if members is None:
                return

            verification.verify_users_can_be_in_group(
                members,
                self.project,
                'members',
                group_to_ignore=self,
                check_group_size_limits=check_group_size_limits,
                ignore_guest_restrictions=ignore_guest_restrictions
            )

            self.members.set(members, clear=True)
            self._member_names = [
                user.username for user in sorted(members, key=lambda user: user.username)]
            self.full_clean()
            self.save()

    SERIALIZABLE_FIELDS = (
        'pk',
        'project',
        'hard_extended_due_date',
        'soft_extended_due_date',
        'extended_due_date',
        'member_names',
        'members',

        'bonus_submissions_remaining',

        'late_days_used',

        'num_submissions',
        'num_submits_towards_limit',

        'created_at',
        'last_modified',
    )
    SERIALIZE_RELATED = ('members',)

    EDITABLE_FIELDS = (
        'extended_due_date',
        'hard_extended_due_date',
        'soft_extended_due_date',
        'bonus_submissions_remaining'
    )

    def to_dict(self) -> Dict[str, object]:
        result = super().to_dict()
        cast(
            List[Dict[str, object]], result['members']
        ).sort(key=lambda user: cast(str, user['username']))
        return result
