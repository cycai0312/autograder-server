from datetime import timedelta, datetime
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from .ag_model_base import (
    AutograderModel, AutograderModelManager, DictSerializable)
from .group import Group
from .submission import Submission
from .course import Course

from autograder.rest_api.serialize_user import serialize_user


class ExtraLateDays(AutograderModel):
    objects = AutograderModelManager['ExtraLateDays']()

    class Meta:
        unique_together = ('course', 'user')

    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='late_days')

    extra_late_days = models.IntegerField(blank=True, default=0)

    SERIALIZABLE_FIELDS = ('course', 'user', 'extra_late_days')
    EDITABLE_FIELDS = ('extra_late_days')

    def clean(self) -> None:
        super().clean()
        if self.extra_late_days < 0:
            raise ValidationError('extra_late_days must be non-negative')


class LateDaysForUser(DictSerializable):
    def __init__(self,
                 user: User,
                 course: Course,
                 extra_late_days: int,
                 late_days_used_per_project: dict[int, int],
                 late_days_used: int,
                 late_days_remaining: int):
        self.user = user
        self.course = course
        self.extra_late_days = extra_late_days
        self.late_days_used = late_days_used
        self.late_days_remaining = late_days_remaining
        self.late_days_used_per_project = late_days_used_per_project

    @staticmethod
    def _days_late(group: Group, submission_timestamp: datetime) -> int:
        if group.project.closing_time is None:
            return 0
        elif group.extended_due_date is None:
            delta = submission_timestamp - group.project.closing_time
        else:
            deadline = max(group.project.closing_time, group.extended_due_date)
            delta = submission_timestamp - deadline

        return delta.days + 1 if delta > timedelta() else 0

    def to_dict(self) -> dict[str, object]:
        return {
            'user': serialize_user(self.user),
            'course': self.course.to_dict(),
            'extra_late_days': self.extra_late_days,
            'late_days_used': self.late_days_used,
            'late_days_remaining': self.late_days_remaining,
            'late_days_used_per_project': self.late_days_used_per_project
        }

    @staticmethod
    def get(user: User, course: Course) -> "LateDaysForUser":
        queryset = User.objects.filter(pk=user.pk)
        return LateDaysForUser.get_many(queryset, course)[0]

    @staticmethod
    def get_many(users_queryset: models.QuerySet[User], course: Course) -> list["LateDaysForUser"]:
        # Fetch all submissions for the course's groups, ordered by descending timestamp
        groups_with_submissions = Group.objects.filter(
            project__course=course,
            project__allow_late_days=True
        ).prefetch_related(
            models.Prefetch(
                'submissions',
                queryset=Submission.objects.order_by('-timestamp'),
                to_attr='all_submissions'
            )
        )

        # Prefetch groups and late days for each user
        prefetch_groups = models.Prefetch(
            'groups_is_member_of',
            queryset=groups_with_submissions,
            to_attr='groups_with_submissions'
        )
        prefetch_late_days = models.Prefetch(
            'late_days',
            queryset=ExtraLateDays.objects.filter(course=course),
            to_attr='late_days_for_course'
        )

        users_with_groups = users_queryset.prefetch_related(
            prefetch_groups,
            prefetch_late_days
        )

        results = []
        for user in users_with_groups:
            if user.late_days_for_course:  # type:ignore
                extra = user.late_days_for_course[0].extra_late_days  # type:ignore
            else:
                extra = 0

            used = 0
            used_per_project = {}

            for group in user.groups_with_submissions:  # type:ignore
                # Filter submissions that count for the user
                user_submissions = [
                    submission for submission in group.all_submissions
                    if user.username not in submission.does_not_count_for
                ]

                # Get the first (latest) submission that counts for the user
                if user_submissions:
                    latest_submission = user_submissions[0]
                    used_this_project = LateDaysForUser._days_late(
                        group,
                        latest_submission.timestamp
                    )
                    used_per_project[group.project.pk] = used_this_project
                    used += used_this_project

            remaining = course.num_late_days + extra - used
            results.append(
                LateDaysForUser(user, course, extra, used_per_project, used, remaining)
            )

        return results

    @staticmethod
    def get_all(course: Course) -> list["LateDaysForUser"]:
        queryset = User.objects.filter(courses_is_enrolled_in=course)
        return LateDaysForUser.get_many(queryset, course)
