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
        student = obj_build.make_student_user(self.course)
        self.do_get_late_days_test(student, student, self.course, 0, 0)

    def test_guest_view_own_late_days(self):
        guest = obj_build.make_user()
        self.do_get_late_days_test(guest, guest, self.course, 0, 0)

    def test_staff_view_other_students_late_days(self):
        staff = obj_build.make_staff_user(self.course)
        student = obj_build.make_student_user(self.course)
        self.do_get_late_days_test(staff, student, self.course, 0, 0)

    def test_admin_change_extra_late_days_by_pk(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_pk_url(student, self.course),
                                   {'extra_late_days': 42})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual({
            'extra_late_days': 42,
            'late_days_used': 0,
            'late_days_remaining': self.course.num_late_days + 42,
            'user': serialize_user(student),
            'course': self.course.to_dict()
        }, response.data)

        extra = ag_models.ExtraLateDays.objects.get(user=student, course=self.course)
        self.assertEqual(42, extra.extra_late_days)

    def test_admin_change_extra_late_days_by_username(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_username_url(student, self.course),
                                   {'extra_late_days': 42})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual({
            'extra_late_days': 42,
            'late_days_used': 0,
            'late_days_remaining': self.course.num_late_days + 42,
            'user': serialize_user(student),
            'course': self.course.to_dict()
        }, response.data)

        extra = ag_models.ExtraLateDays.objects.get(user=student, course=self.course)
        self.assertEqual(42, extra.extra_late_days)

    def test_admin_change_extra_late_days_by_pk_object_exists(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        ag_models.ExtraLateDays.objects.validate_and_create(user=student, course=self.course)
        self.do_get_late_days_test(admin, student, self.course, 0, 0)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_pk_url(student, self.course),
                                   {'extra_late_days': 27})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual({
            'late_days_used': 0,
            'late_days_remaining': 27 + self.course.num_late_days,
            'extra_late_days': 27,
            'user': serialize_user(student),
            'course': self.course.to_dict()
        }, response.data)

        extra = ag_models.ExtraLateDays.objects.get(user=student, course=self.course)
        self.assertEqual(27, extra.extra_late_days)

    def test_admin_change_extra_late_days_by_username_object_exists(self):
        admin = obj_build.make_admin_user(self.course)
        student = obj_build.make_student_user(self.course)

        ag_models.ExtraLateDays.objects.validate_and_create(user=student, course=self.course)
        self.do_get_late_days_test(admin, student, self.course, 0, 0)

        self.client.force_authenticate(admin)
        response = self.client.put(self.get_username_url(student, self.course),
                                   {'extra_late_days': 27})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual({
            'late_days_used': 0,
            'late_days_remaining': 27 + self.course.num_late_days,
            'extra_late_days': 27,
            'user': serialize_user(student),
            'course': self.course.to_dict()
        }, response.data)

        extra = ag_models.ExtraLateDays.objects.get(user=student, course=self.course)
        self.assertEqual(27, extra.extra_late_days)

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
            student,
            student,
            self.course,
            1,
            1
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
        self.do_get_late_days_test(student, student, self.course, 0, 0)

    def do_get_late_days_test(self, requestor: User, requestee: User, course: ag_models.Course,
                              expected_late_days_used: int, expected_extra_late_days: int):
        self.client.force_authenticate(requestor)

        for url in self.get_pk_url(requestee, course), self.get_username_url(requestee, course):
            response = self.client.get(url)

            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertEqual({
                'late_days_remaining': course.num_late_days + expected_extra_late_days
                - expected_late_days_used,
                'late_days_used': expected_late_days_used,
                'extra_late_days': expected_extra_late_days,
                'course': course.to_dict(),
                'user': serialize_user(requestee)
            }, response.data)

    def get_pk_url(self, requestee: User, course: ag_models.Course):
        url = reverse('user-late-days', kwargs={'pk': course.pk, 'username_or_pk': requestee.pk})
        return url

    def get_username_url(self, requestee: User, course: ag_models.Course):
        url = reverse('user-late-days', kwargs={'pk': course.pk,
                      'username_or_pk': requestee.username})
        return url


class ListUserLateDaysViewTestCase(UnitTestBase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

        self.initial_num_late_days = 4
        self.course = obj_build.make_course(num_late_days=self.initial_num_late_days)
        self.url = reverse('list-user-late-days', kwargs={'pk': self.course.pk, })
        self.admin = obj_build.make_admin_user(self.course)
        self.client.force_authenticate(self.admin)

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

    def test_view_no_students(self):
        resp = self.client.get(self.url)
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual([], resp.data)

    def test_course_dne(self):
        resp = self.client.get(reverse('list-user-late-days', kwargs={'pk': 999}))
        self.assertEqual(status.HTTP_404_NOT_FOUND, resp.status_code)
