from typing import Sequence
import pytz

from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

import autograder.core.models as ag_models
from autograder.utils.testing import UnitTestBase
import autograder.utils.testing.model_obj_builders as obj_build


class ExtraLateDaysTestCase(UnitTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.course = obj_build.make_course(num_late_days=4)
        self.user = obj_build.make_user()
        self.course.students.add(self.user)
        self.course.validate_and_update()

    def test_valid_create_with_defaults(self) -> None:
        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=self.user
        )

        from_db = ag_models.ExtraLateDays.objects.get(
            course=self.course, user=self.user
        )
        self.assertEqual(from_db.extra_late_days, 0)

    def test_valid_create_with_extra_days(self) -> None:
        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=self.user,
            extra_late_days=2
        )
        from_db = ag_models.ExtraLateDays.objects.get(
            course=self.course, user=self.user
        )
        self.assertEqual(from_db.extra_late_days, 2)

    def test_invalid_create_not_in_course(self) -> None:
        new_user = obj_build.make_user()
        with self.assertRaises(ValidationError) as cm:
            ag_models.ExtraLateDays.objects.validate_and_create(
                course=self.course,
                user=new_user
            )

    def test_invalid_create_negative_value(self) -> None:
        with self.assertRaises(ValidationError) as cm:
            ag_models.ExtraLateDays.objects.validate_and_create(
                course=self.course,
                user=self.user,
                extra_late_days=-1
            )


class LateDaysForUserTestBase(UnitTestBase):
    def setUp(self) -> None:
        super().setUp()

        self.base_time = pytz.utc.localize(datetime.now())

        self.course = obj_build.make_course(num_late_days=4)

        self.p1 = self.make_project(
            closing_time=self.base_time,
            name="p1",
            max_group_size=3
        )
        self.p2 = self.make_project(
            closing_time=self.base_time + timedelta(days=5),
            name="p2",
            max_group_size=3
        )
        self.p3 = self.make_project(
            closing_time=self.base_time + timedelta(days=10),
            name="p3",
            max_group_size=3
        )
        self.p_no_late_days = self.make_project(
            closing_time=self.base_time + timedelta(days=15),
            name="p4",
            allow_late_days=False,
            max_group_size=3
        )

    def make_project(
        self,
        closing_time,
        name,
        max_group_size=1,
        allow_late_days=True
    ) -> ag_models.Project:
        return obj_build.make_project(
            course=self.course,
            name=name,
            allow_late_days=allow_late_days,
            closing_time=closing_time,
            max_group_size=max_group_size
        )

    def make_student(self) -> User:
        user = obj_build.make_user()
        self.course.students.add(user)
        self.course.validate_and_update()
        return user

    def make_students(self, num_students: int) -> Sequence[User]:
        return [self.make_student() for _ in range(num_students)]

    def assert_late_days_correct(self,
                                 user: User,
                                 late_days: ag_models.LateDaysForUser,
                                 used: int = 0,
                                 extra: int = 0,
                                 ) -> None:
        self.assertEqual(late_days.course.pk, self.course.pk)
        self.assertEqual(late_days.user.pk, user.pk)
        self.assertEqual(late_days.extra_late_days, extra)
        self.assertEqual(late_days.late_days_used, used)
        self.assertEqual(
            late_days.late_days_remaining,
            self.course.num_late_days + extra - used
        )


class LateDaysForUserGetTestCase(LateDaysForUserTestBase):
    def test_not_a_student_error(self):
        user = obj_build.make_user()
        with self.assertRaises(ValueError):
            ag_models.LateDaysForUser.get(user, self.course)

    def test_no_submissions_no_extra(self):
        user = self.make_student()
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
        )

    def test_no_submissions_with_extra(self):
        user = self.make_student()
        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=user,
            extra_late_days=1
        )
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            extra=1
        )

    def test_one_used_no_extra(self):
        user = self.make_student()
        group = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })

        obj_build.make_finished_submission(
            group,
            timestamp=self.p1.closing_time + timedelta(hours=1)
        )
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=1,
        )

    def test_one_used_with_extra(self):
        user = self.make_student()
        group = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })

        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=user,
            extra_late_days=1
        )
        obj_build.make_finished_submission(
            group,
            timestamp=self.p1.closing_time + timedelta(seconds=1)
        )
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            group.members.first(),
            late_days,
            used=1,
            extra=1,
        )

    def test_two_used_same_project_no_extra(self):
        user = self.make_student()
        group = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })

        obj_build.make_finished_submission(
            group,
            timestamp=self.p1.closing_time + timedelta(days=1, seconds=1)
        )
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=2,
        )

    def test_two_used_same_project_with_extra(self):
        user = self.make_student()
        group = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })

        obj_build.make_finished_submission(
            group,
            timestamp=self.p1.closing_time + timedelta(days=1, seconds=1)
        )
        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=user,
            extra_late_days=1
        )
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=group.members.first(),
            late_days=late_days,
            used=2,
            extra=1
        )

    def test_two_used_diff_projects_no_extra(self):
        user = self.make_student()
        g1 = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })
        g2 = obj_build.build_group(group_kwargs={
            'project': self.p2,
            'members': [user]
        })

        obj_build.make_finished_submission(
            g1,
            timestamp=self.p1.closing_time + timedelta(seconds=1)
        )
        obj_build.make_finished_submission(
            g2,
            timestamp=self.p2.closing_time + timedelta(seconds=1)
        )
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=2,
        )

    def test_two_used_diff_projects_with_extra(self):
        user = self.make_student()
        g1 = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })
        g2 = obj_build.build_group(group_kwargs={
            'project': self.p2,
            'members': [user]
        })

        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=user,
            extra_late_days=1
        )

        obj_build.make_finished_submission(
            g1,
            timestamp=self.p1.closing_time + timedelta(seconds=1)
        )
        obj_build.make_finished_submission(
            g2,
            timestamp=self.p2.closing_time + timedelta(seconds=1)
        )
        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=2,
            extra=1
        )

    def test_multiple_submissions_multiple_projects(self):
        user = self.make_student()

        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=user,
            extra_late_days=1
        )

        g1 = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })
        g2 = obj_build.build_group(group_kwargs={
            'project': self.p2,
            'members': [user]
        })
        g3 = obj_build.build_group(group_kwargs={
            'project': self.p3,
            'members': [user]
        })
        g_no_late_days = obj_build.build_group(group_kwargs={
            'project': self.p_no_late_days,
            'members': [user]
        })

        # 2 submissions on p1, with the latest submission being 2 days late
        obj_build.make_finished_submission(
            g1,
            timestamp=self.p1.closing_time + timedelta(days=1, seconds=1)
        )
        obj_build.make_finished_submission(
            g1,
            timestamp=self.p1.closing_time + timedelta(days=1, seconds=2)
        )

        # 3 submissions on p2, with the latest submission being 3 days late
        obj_build.make_finished_submission(
            g2,
            timestamp=self.p2.closing_time  # not late
        )
        obj_build.make_finished_submission(
            g2,
            timestamp=self.p2.closing_time + timedelta(days=1, seconds=1)
        )
        obj_build.make_finished_submission(
            g2,
            timestamp=self.p2.closing_time + timedelta(days=2, seconds=1)
        )

        # 1 submission on p3 that doesn't count for user
        p3_sub = obj_build.make_finished_submission(
            g3,
            timestamp=self.p3.closing_time + timedelta(seconds=1),
        )
        p3_sub.does_not_count_for.append(user.username)
        p3_sub.validate_and_update()

        # 1 late submission for p_no_late_days
        obj_build.make_finished_submission(
            g_no_late_days,
            timestamp=self.p_no_late_days.closing_time + timedelta(seconds=1),
        )

        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=5,
            extra=1
        )

    def test_multiple_submissions_multiple_projects_with_extension(self):
        user = self.make_student()

        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=user,
            extra_late_days=1
        )

        g1 = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user],
            'extended_due_date': self.p1.closing_time + timedelta(days=1)
        })
        g2 = obj_build.build_group(group_kwargs={
            'project': self.p2,
            'members': [user]
        })

        # 2 submissions on p1, with the latest submission being 2 day late
        obj_build.make_finished_submission(
            g1,
            timestamp=g1.extended_due_date  # not late
        )
        obj_build.make_finished_submission(
            g1,
            timestamp=g1.extended_due_date + timedelta(days=1, seconds=2)
        )

        # 2 submissions on p2, with the latest submission being 3 days late
        obj_build.make_finished_submission(
            g2,
            timestamp=self.p2.closing_time  # not late
        )
        obj_build.make_finished_submission(
            g2,
            timestamp=self.p2.closing_time + timedelta(days=2, seconds=1)
        )

        late_days = ag_models.LateDaysForUser.get(user, self.course)

        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=5,
            extra=1
        )

    def test_updating_closing_time_updates_late_days(self):
        user = self.make_student()
        g1 = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })
        obj_build.make_finished_submission(
            g1,
            timestamp=self.p1.closing_time + timedelta(seconds=1)
        )

        late_days = ag_models.LateDaysForUser.get(user, self.course)
        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=1,
        )

        self.p1.closing_time = self.p1.closing_time + timedelta(days=1)
        self.p1.validate_and_update()

        late_days = ag_models.LateDaysForUser.get(user, self.course)
        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=0,
        )

        self.p1.closing_time = self.p1.closing_time - timedelta(days=2)
        self.p1.validate_and_update()

        late_days = ag_models.LateDaysForUser.get(user, self.course)
        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=2,
        )

    def test_updating_extension_updates_late_days(self):
        user = self.make_student()
        g1 = obj_build.build_group(group_kwargs={
            'project': self.p1,
            'members': [user]
        })
        obj_build.make_finished_submission(
            g1,
            timestamp=self.p1.closing_time + timedelta(seconds=1)
        )

        late_days = ag_models.LateDaysForUser.get(user, self.course)
        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=1,
        )

        g1.extended_due_date = self.p1.closing_time + timedelta(days=1)
        g1.validate_and_update()

        late_days = ag_models.LateDaysForUser.get(user, self.course)
        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=0
        )

        g1.extended_due_date = None
        g1.validate_and_update()

        late_days = ag_models.LateDaysForUser.get(user, self.course)
        self.assert_late_days_correct(
            user=user,
            late_days=late_days,
            used=1,
        )

# class LateDaysForUserGetAllTestCase(LateDaysForUserTestBase):
#     def test_multiple_users_same_groups(self):
#         group = obj_build.make_group(project=self.p1)
#         u1 = self.make_student()
#         u2 = self.make_student()
#         group.members.add(u1)
#         group.members.add(u2)
#         group.save()
