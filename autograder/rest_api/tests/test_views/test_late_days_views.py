from typing import TypedDict
from datetime import datetime, timedelta
import pytz

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

import autograder.core.models as ag_models
import autograder.utils.testing.model_obj_builders as obj_build
from autograder.rest_api.serialize_user import serialize_user
from autograder.utils.testing import UnitTestBase


class UserLateDaysViewTestCase(UnitTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.initial_num_late_days = 4
        self.course = obj_build.make_course(num_late_days=self.initial_num_late_days)

    def test_student_view_own_late_days(self):
        self.maxDiff = None
        student = obj_build.make_student_user(self.course)
        self.do_get_late_days_test(student, student, self.course)

    def test_guest_view_own_late_days(self):
        guest = obj_build.make_user()
        self.do_get_late_days_test(guest, guest, self.course)

    def test_staff_view_other_students_late_days(self):
        staff = obj_build.make_staff_user(self.course)
        student = obj_build.make_student_user(self.course)
        self.do_get_late_days_test(staff, student, self.course)

    def test_admin_change_extra_late_days_by_pk(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_pk_url(student, self.course),
                                   {'extra_late_days': 42})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.response_data_is_expected(response.data, user=student,
                                       course=self.course, extra_late_days=42)
        self.do_get_late_days_test(requestor=student, requestee=student,
                                   course=self.course, extra_late_days=42)

    def test_admin_change_extra_late_days_by_username(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_username_url(student, self.course),
                                   {'extra_late_days': 42})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.response_data_is_expected(response.data, user=student,
                                       course=self.course, extra_late_days=42)
        self.do_get_late_days_test(requestor=student, requestee=student,
                                   course=self.course, extra_late_days=42)

    def test_admin_change_extra_late_days_by_pk_object_exists(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        ag_models.ExtraLateDays.objects.validate_and_create(user=student, course=self.course)
        self.do_get_late_days_test(admin, student, self.course)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_pk_url(student, self.course),
                                   {'extra_late_days': 27})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.response_data_is_expected(response.data, user=student,
                                       course=self.course, extra_late_days=27)
        self.do_get_late_days_test(admin, student, self.course, extra_late_days=27)

    def test_admin_change_extra_late_days_by_username_object_exists(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        ag_models.ExtraLateDays.objects.validate_and_create(user=student, course=self.course)
        self.do_get_late_days_test(admin, student, self.course, 0, 0)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_username_url(student, self.course),
                                   {'extra_late_days': 27})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.response_data_is_expected(response.data, user=student,
                                       course=self.course, extra_late_days=27)
        self.do_get_late_days_test(admin, student, self.course, extra_late_days=27)

    def test_admin_change_extra_late_days_for_other_course_permission_denied(self):
        admin = obj_build.make_admin_user(self.course)

        # Student for other course
        other_course = obj_build.make_course()
        other_course_student = obj_build.make_student_user(other_course)
        self.assertFalse(other_course.is_admin(admin))

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_pk_url(other_course_student, other_course),
                                   {'extra_late_days': 10})
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        response = self.client.put(self.get_username_url(other_course_student, other_course),
                                   {'extra_late_days': 10})
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        # Guest for other course
        other_guest = obj_build.make_user()
        response = self.client.put(self.get_pk_url(other_guest, other_course),
                                   {'extra_late_days': 7})
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        other_guest = obj_build.make_user()
        response = self.client.put(self.get_username_url(other_guest, other_course),
                                   {'extra_late_days': 7})
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_staff_view_late_days_for_other_course_permission_denied(self):
        staff = obj_build.make_staff_user(self.course)

        # Student for other course
        other_course = obj_build.make_course()
        other_course_student = obj_build.make_student_user(other_course)
        self.assertFalse(other_course.is_staff(staff))

        self.client.force_authenticate(staff)
        response = self.client.get(self.get_pk_url(other_course_student, other_course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        response = self.client.get(self.get_username_url(other_course_student, other_course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        # Guest for other course
        other_guest = obj_build.make_user()
        response = self.client.get(self.get_pk_url(other_guest, other_course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        response = self.client.get(self.get_username_url(other_guest, other_course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_student_view_other_users_late_days_permission_denied(self):
        student1 = obj_build.make_student_user(self.course)
        student2 = obj_build.make_student_user(self.course)

        self.client.force_authenticate(student1)
        response = self.client.get(self.get_pk_url(student2, self.course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        response = self.client.get(self.get_username_url(student2, self.course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_guest_view_other_users_late_days_denied(self):
        guest1 = obj_build.make_user()
        guest2 = obj_build.make_user()

        self.client.force_authenticate(guest1)
        response = self.client.get(self.get_pk_url(guest2, self.course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

        response = self.client.get(self.get_username_url(guest2, self.course))
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)

    def test_get_late_day_count_object_exists(self):
        base_time = pytz.utc.localize(datetime.now())
        project = obj_build.make_project(
            course=self.course,
            closing_time=base_time,
            allow_late_days=True
        )
        group = obj_build.build_group(group_kwargs={'project': project})

        student = group.members.first()

        ag_models.ExtraLateDays.objects.validate_and_create(
            course=self.course,
            user=student,
            extra_late_days=1
        )

        obj_build.make_finished_submission(
            group,
            timestamp=project.closing_time + timedelta(seconds=1)
        )

        self.do_get_late_days_test(
            requestor=student,
            requestee=student,
            course=self.course,
            late_days_used=1,
            extra_late_days=1,
            late_days_used_per_project={project.pk: 1}
        )

    def test_put_missing_body_param(self):
        admin = obj_build.make_admin_user(self.course)
        self.client.force_authenticate(admin)

        response = self.client.put(self.get_pk_url(admin, self.course), {})
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

        response = self.client.put(self.get_username_url(admin, self.course), {})
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_get_late_days_course_has_no_late_days(self):
        self.course.validate_and_update(num_late_days=0)
        student = obj_build.make_student_user(self.course)
        self.do_get_late_days_test(
            requestor=student,
            requestee=student,
            course=self.course,
        )

    def do_get_late_days_test(
        self, requestor: User,
        requestee: User,
        course: ag_models.Course,
        late_days_used: int = 0,
        extra_late_days: int = 0,
        late_days_used_per_project: dict[int, int] = {}
    ) -> None:
        self.client.force_authenticate(requestor)

        for url in self.get_pk_url(requestee, course), self.get_username_url(requestee, course):
            response = self.client.get(url)

            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.response_data_is_expected(
                response_data=response.data,
                user=requestee,
                course=course,
                late_days_used=late_days_used,
                extra_late_days=extra_late_days,
                late_days_used_per_project=late_days_used_per_project
            )

    def response_data_is_expected(self,
                                  response_data,
                                  user: User,
                                  course: ag_models.Course,
                                  late_days_used: int = 0,
                                  extra_late_days: int = 0,
                                  late_days_used_per_project: dict[int, int] = {}
                                  ) -> None:
        expected = {
            'late_days_remaining': course.num_late_days + extra_late_days - late_days_used,
            'late_days_used': late_days_used,
            'extra_late_days': extra_late_days,
            'late_days_used_per_project': late_days_used_per_project,
            'course': course.to_dict(),
            'user': serialize_user(user)
        }
        self.assertEqual(expected, response_data)

    def get_pk_url(self, requestee: User, course: ag_models.Course):
        url = reverse('user-late-days', kwargs={'pk': course.pk, 'username_or_pk': requestee.pk})
        return url

    def get_username_url(self, requestee: User, course: ag_models.Course):
        url = reverse('user-late-days', kwargs={'pk': course.pk,
                      'username_or_pk': requestee.username})
        return url


ExpectedLateDaysForUser = TypedDict(
    'ExpectedLateDaysForUser',
    user=User,
    used=int,
    extra=int
)


class ListUserLateDaysViewTestCase(UnitTestBase):

    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.num_late_days = 4
        self.course = obj_build.make_course(num_late_days=self.num_late_days)
        self.url = reverse('list-user-late-days', kwargs={'pk': self.course.pk, })
        self.admin = obj_build.make_admin_user(self.course)
        self.client.force_authenticate(self.admin)
        self.base_time = pytz.utc.localize(datetime.now())

    def do_permission_denied_test(self, user: User):
        self.client.force_authenticate(user)
        resp = self.client.get(self.url)
        self.assertEqual(status.HTTP_403_FORBIDDEN, resp.status_code)

    def test_student_view_permission_denied(self):
        student = obj_build.make_student_user(self.course)
        self.do_permission_denied_test(student)

    def test_guest_view_permission_denied(self):
        guest = obj_build.make_allowed_domain_guest_user(self.course)
        self.do_permission_denied_test(guest)

    def test_staff_view_permission_denied(self):
        staff = obj_build.make_staff_user(self.course)
        self.do_permission_denied_test(staff)

    def test_admin_other_course_permission_denied(self):
        other_course = obj_build.build_course()
        admin = obj_build.make_admin_user(other_course)
        self.do_permission_denied_test(admin)

    def test_course_dne(self):
        resp = self.client.get(reverse('list-user-late-days', kwargs={'pk': 999}))
        self.assertEqual(status.HTTP_404_NOT_FOUND, resp.status_code)

    def test_no_students_but_student_in_other_course(self):
        other_course = obj_build.make_course()
        obj_build.make_student_user(other_course)
        self.do_list_late_days_test([])

    def test_no_projects_no_submissions(self):
        students = obj_build.make_student_users(self.course, 3)
        self.do_list_late_days_test([
            {'user': stud, 'extra': 0, 'used': 0}
            for stud in students
        ])

    def test_one_project_no_late_submissions(self):
        project = obj_build.make_project(self.course, closing_time=self.base_time)
        groups = [obj_build.make_group(project=project) for _ in range(3)]

        expected = []
        for g in groups:
            obj_build.make_finished_submission(g, timestamp=self.base_time)
            expected.append({'user': g.members.first(), 'used': 0, 'extra': 0})
        self.do_list_late_days_test(expected)

    def test_one_project_some_late(self):
        project = obj_build.make_project(
            self.course,
            closing_time=self.base_time,
            allow_late_days=True
        )
        groups = [obj_build.make_group(project=project) for _ in range(3)]

        obj_build.make_finished_submission(
            groups[1],
            timestamp=self.base_time + timedelta(hours=1)  # one day late
        )
        obj_build.make_finished_submission(
            groups[2],
            timestamp=self.base_time + timedelta(days=1, hours=1)  # two days late
        )
        expected: list[ExpectedLateDaysForUser] = [
            {'user': groups[0].members.first(), 'used': 0, 'extra': 0},
            {'user': groups[1].members.first(), 'used': 1, 'extra': 0},
            {'user': groups[2].members.first(), 'used': 2, 'extra': 0}
        ]
        self.do_list_late_days_test(expected)

    def test_no_project_some_extra(self):
        students = obj_build.make_student_users(self.course, 3)
        self.add_extra_late_days(students[1], 1)
        self.add_extra_late_days(students[2], 2)
        expected: list[ExpectedLateDaysForUser] = [
            {'user': students[0], 'used': 0, 'extra': 0},
            {'user': students[1], 'used': 0, 'extra': 1},
            {'user': students[2], 'used': 0, 'extra': 2}
        ]
        self.do_list_late_days_test(expected)

    def add_extra_late_days(self, user: User, num_extra: int) -> None:
        resp = self.client.put(
            reverse('user-late-days', kwargs={
                'pk': self.course.pk, 'username_or_pk': user.pk
            }),
            {'extra_late_days': num_extra}
        )

        # sanity check that this succeeded
        assert status.HTTP_200_OK == resp.status_code

    def do_list_late_days_test(self, expected: list[ExpectedLateDaysForUser]) -> None:
        # sanity check that expected is a list of data for unique users
        seen = set()
        for elem in expected:
            assert elem['user'].pk not in seen
            seen.add(elem['user'].pk)

        resp = self.client.get(self.url)
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual(len(expected), len(resp.data))

        for exp in expected:
            pk = exp['user'].pk
            used = exp['used']
            extra = exp['extra']
            remaining = self.num_late_days + extra - used

            # Grab the datum for the user, and check that there is only one match
            matches = [elem for elem in resp.data if elem['user']['pk'] == pk]
            self.assertEqual(1, len(matches))

            actual = matches[0]
            self.assertEqual(used, actual['late_days_used'])
            self.assertEqual(remaining, actual['late_days_remaining'])
            self.assertEqual(extra, actual['extra_late_days'])
