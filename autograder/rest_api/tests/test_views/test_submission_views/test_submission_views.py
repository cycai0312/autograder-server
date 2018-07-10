import datetime
import os
import random
from typing import Optional
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

import autograder.core.models as ag_models
import autograder.rest_api.serializers as ag_serializers
import autograder.rest_api.tests.test_views.ag_view_test_base as test_impls
import autograder.rest_api.tests.test_views.common_generic_data as test_data
import autograder.utils.testing.model_obj_builders as obj_build
from autograder import utils
from autograder.core.models import Submission
from autograder.utils.testing import UnitTestBase


class ListSubmissionsTestCase(test_data.Client,
                              test_data.Project,
                              test_data.Group,
                              test_data.Submission,
                              test_impls.ListObjectsTest,
                              UnitTestBase):
    def setUp(self):
        super().setUp()
        self.maxDiff = None

    def test_admin_or_staff_list_submissions(self):
        for project in self.all_projects:
            for group in self.at_least_enrolled_groups(project):
                expected_data = ag_serializers.SubmissionSerializer(
                    self.build_submissions(group), many=True).data
                for user in self.admin, self.staff:
                    self.do_list_objects_test(
                        self.client, user, self.submissions_url(group),
                        expected_data)

        for project in self.hidden_public_project, self.visible_public_project:
            group = self.non_enrolled_group(project)
            expected_data = ag_serializers.SubmissionSerializer(
                self.build_submissions(group), many=True).data
            for user in self.admin, self.staff:
                self.do_list_objects_test(
                    self.client, user, self.submissions_url(group),
                    expected_data)

    def test_enrolled_list_submissions(self):
        for project in self.visible_projects:
            group = self.enrolled_group(project)
            expected_data = ag_serializers.SubmissionSerializer(
                self.build_submissions(group), many=True).data
            self.do_list_objects_test(
                self.client, self.enrolled, self.submissions_url(group),
                expected_data)

    def test_handgrader_list_student_group_submissions_permission_denied(self):
        for project in self.visible_projects:
            group = self.enrolled_group(project)
            expected_data = ag_serializers.SubmissionSerializer(
                self.build_submissions(group), many=True).data
            self.do_permission_denied_get_test(
                self.client, self.handgrader, self.submissions_url(group), expected_data)

    def test_non_enrolled_list_submissions(self):
        group = self.non_enrolled_group(self.visible_public_project)
        expected_data = ag_serializers.SubmissionSerializer(
            self.build_submissions(group), many=True).data
        self.do_list_objects_test(
            self.client, self.nobody, self.submissions_url(group),
            expected_data)

    def test_non_group_member_list_submissions_permission_denied(self):
        group = self.enrolled_group(self.visible_public_project)
        self.build_submissions(group)
        non_member = self.clone_user(self.enrolled)
        for user in non_member, self.nobody:
            self.do_permission_denied_get_test(
                self.client, user, self.submissions_url(group))

    def test_enrolled_list_submissions_project_hidden_permission_denied(self):
        for project in self.hidden_projects:
            group = self.enrolled_group(project)
            self.build_submissions(group)
            self.do_permission_denied_get_test(
                self.client, self.enrolled, self.submissions_url(group))

    def test_non_enrolled_list_submissions_project_hidden_permission_denied(self):
        group = self.non_enrolled_group(self.hidden_public_project)
        self.build_submissions(group)
        self.do_permission_denied_get_test(
            self.client, self.nobody, self.submissions_url(group))

    def test_non_enrolled_list_submissions_project_private_permission_denied(self):
        group = self.non_enrolled_group(self.visible_public_project)
        self.build_submissions(group)
        self.visible_public_project.validate_and_update(
            guests_can_submit=False)
        self.do_permission_denied_get_test(
            self.client, self.nobody, self.submissions_url(group))


class CreateSubmissionTestCase(test_data.Client,
                               test_data.Project,
                               test_data.Group,
                               test_data.Submission,
                               test_impls.CreateObjectTest,
                               UnitTestBase):
    def test_admin_or_staff_submit(self):
        for project in self.all_projects:
            project.validate_and_update(
                closing_time=timezone.now() + timezone.timedelta(minutes=1))
            for group in (self.admin_group(project),
                          self.staff_group(project)):
                self.do_normal_submit_test(group, group.members.last())

    def test_admin_or_staff_submit_deadline_past(self):
        self.project.validate_and_update(
            closing_time=timezone.now() + timezone.timedelta(seconds=-1))
        for group in (self.admin_group(self.project),
                      self.staff_group(self.project)):
            self.do_normal_submit_test(group, group.members.first())

    def test_admin_or_staff_submit_submissions_disallowed(self):
        self.project.validate_and_update(disallow_student_submissions=True)
        for group in (self.admin_group(self.project),
                      self.staff_group(self.project)):
            self.do_normal_submit_test(group, group.members.last())

    def test_enrolled_submit(self):
        for project in self.visible_projects:
            closing_time = timezone.now() + timezone.timedelta(minutes=1)
            project.validate_and_update(closing_time=closing_time)
            group = self.enrolled_group(project)
            self.do_normal_submit_test(group, group.members.last())

    def test_non_enrolled_submit(self):
        closing_time = timezone.now() + timezone.timedelta(minutes=1)
        self.visible_public_project.validate_and_update(
            closing_time=closing_time)
        group = self.non_enrolled_group(self.visible_public_project)
        self.do_normal_submit_test(group, group.members.first())

    def test_all_submit_no_closing_time(self):
        for group in self.all_groups(self.visible_public_project):
            self.do_normal_submit_test(group, group.members.first())

    def test_submit_missing_and_discarded_files_tracked(self):
        self.add_expected_patterns(self.visible_private_project)
        group = self.enrolled_group(self.visible_private_project)
        self.client.force_authenticate(self.enrolled)
        bad_filename = 'not a needed file'
        request_data = {
            'submitted_files': [
                SimpleUploadedFile(bad_filename, b'merp')]}
        response = self.client.post(
            self.submissions_url(group), request_data, format='multipart')
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertCountEqual([], response.data['submitted_filenames'])
        self.assertCountEqual([bad_filename],
                              response.data['discarded_files'])
        self.assertIn('*.txt', response.data['missing_files'])
        self.assertIn('spam.cpp', response.data['missing_files'])

    # Note that non-group members in this case includes staff, admin, and handgrader.
    def test_non_group_member_submit_permission_denied(self):
        group = self.enrolled_group(self.visible_public_project)
        other_user = self.clone_user(self.enrolled)
        for user in self.admin, self.staff, other_user, self.nobody, self.handgrader:
            self.do_permission_denied_submit_test(group, user)

    def test_handgraders_that_are_also_students_submit(self):
        for project in self.visible_projects:
            group = self.enrolled_group(project)
            project.course.handgraders.add(group.members.last())
            self.do_normal_submit_test(group, group.members.last())

    def test_enrolled_submit_hidden_project_permission_denied(self):
        for project in self.hidden_projects:
            group = self.enrolled_group(project)
            self.do_permission_denied_submit_test(group, group.members.first())

    def test_non_enrolled_submit_hidden_project_permission_denied(self):
        group = self.non_enrolled_group(self.hidden_public_project)
        self.do_permission_denied_submit_test(group, group.members.first())

    def test_non_enrolled_submit_private_project_permission_denied(self):
        group = self.non_enrolled_group(self.visible_public_project)
        self.visible_public_project.validate_and_update(
            guests_can_submit=False)
        for user in group.members.all():
            self.do_permission_denied_submit_test(group, user)

    def test_non_staff_submit_deadline_past(self):
        self.visible_public_project.validate_and_update(
            closing_time=timezone.now() + timezone.timedelta(seconds=-1))
        for group in self.non_staff_groups(self.visible_public_project):
            response = self.do_bad_request_submit_test(
                group, group.members.first())
            self.assertIn('submission', response.data)

    def test_non_staff_submit_deadline_past_but_has_extension(self):
        closing_time = timezone.now() + timezone.timedelta(seconds=-1)
        self.visible_public_project.validate_and_update(
            closing_time=closing_time)
        for group in self.non_staff_groups(self.visible_public_project):
            extension = timezone.now() + timezone.timedelta(minutes=1)
            group.validate_and_update(extended_due_date=extension)
            self.do_normal_submit_test(group, group.members.last())

    def test_non_staff_submit_deadline_and_extension_past(self):
        closing_time = timezone.now() + timezone.timedelta(minutes=-1)
        self.visible_public_project.validate_and_update(
            closing_time=closing_time)
        for group in self.non_staff_groups(self.visible_public_project):
            extension = timezone.now() + timezone.timedelta(seconds=-1)
            group.validate_and_update(extended_due_date=extension)
            response = self.do_bad_request_submit_test(group, group.members.first())
            self.assertIn('submission', response.data)

    def test_non_staff_submit_submissions_disallowed(self):
        self.visible_public_project.validate_and_update(
            disallow_student_submissions=True)
        future_closing_time = timezone.now() + timezone.timedelta(minutes=1)
        for group in self.non_staff_groups(self.visible_public_project):
            for closing_time in None, future_closing_time:
                self.visible_public_project.validate_and_update(
                    closing_time=closing_time)
            response = self.do_bad_request_submit_test(group, group.members.first())
            self.assertIn('submission', response.data)

    def test_all_users_already_has_submission_being_processed(self):
        for group in self.all_groups(self.visible_public_project):
            ag_models.Submission.objects.validate_and_create(
                [], group=group)
            response = self.do_bad_request_submit_test(group, group.members.last())
            self.assertIn('submission', response.data)

    def test_can_resubmit_non_being_processed_status(self):
        for group in self.all_groups(self.visible_public_project):
            for grading_status in ag_models.Submission.GradingStatus.values:
                if grading_status in (
                        ag_models.Submission.GradingStatus.active_statuses):
                    continue

                obj_build.make_submission(group=group, status=grading_status)

                self.do_normal_submit_test(group, group.members.first())

    def test_no_submission_limit(self):
        self.assertIsNone(self.visible_public_project.submission_limit_per_day)
        for group in self.all_groups(self.visible_public_project):
            for i in range(5):
                self.do_normal_submit_test(group, group.members.first())

    def test_submission_not_past_limit(self):
        limit = 3
        self.visible_public_project.validate_and_update(
            submission_limit_per_day=limit)
        for group in self.all_groups(self.visible_public_project):
            for i in range(limit):
                self.do_normal_submit_test(group, group.members.last())
            for sub in group.submissions.all():
                self.assertTrue(sub.count_towards_daily_limit)

    def test_submission_past_limit_allowed(self):
        limit = 3
        self.visible_public_project.validate_and_update(
            submission_limit_per_day=limit,
            allow_submissions_past_limit=True)
        for group in self.all_groups(self.visible_public_project):
            for i in range(limit + 2):
                self.do_normal_submit_test(group, group.members.last())
            num_not_past_limit = utils.count_if(
                group.submissions.all(),
                lambda sub: not sub.is_past_daily_limit)
            self.assertEqual(limit, num_not_past_limit)
            for sub in group.submissions.all():
                self.assertTrue(sub.count_towards_daily_limit)

    def test_submission_past_limit_not_allowed_bad_request(self):
        limit = 2
        self.visible_public_project.validate_and_update(
            submission_limit_per_day=limit,
            allow_submissions_past_limit=False)
        for group in self.non_staff_groups(self.visible_public_project):
            for i in range(limit):
                self.do_normal_submit_test(group, group.members.first())

            for i in range(3):
                response = self.do_bad_request_submit_test(group, group.members.first())
                self.assertIn('submission', response.data)
            self.assertEqual(limit, group.submissions.count())

            for sub in group.submissions.all():
                self.assertTrue(sub.count_towards_daily_limit)
                self.assertFalse(sub.is_past_daily_limit)

    def test_submission_past_limit_not_allowed_but_group_has_bonus_submission(self):
        num_bonus_submissions = 2
        limit = 3
        project = obj_build.make_project(
            visible_to_students=True,
            submission_limit_per_day=limit,
            allow_submissions_past_limit=False,
            num_bonus_submissions=num_bonus_submissions
        )
        group = obj_build.make_group(project=project)
        self.assertEqual(num_bonus_submissions, group.bonus_submissions_remaining)
        for i in range(limit + num_bonus_submissions):
            self.do_normal_submit_test(group, group.members.first())

        response = self.do_bad_request_submit_test(group, group.members.first())
        self.assertIn('submission', response.data)

    def test_admin_or_staff_submissions_never_count_towards_limit(self):
        limit = 1
        num_submissions = limit + 4
        self.hidden_private_project.validate_and_update(
            submission_limit_per_day=limit)
        for group in self.staff_groups(self.hidden_private_project):
            for i in range(num_submissions):
                self.do_normal_submit_test(group, group.members.last())

            self.assertEqual(num_submissions, group.submissions.count())

    def test_invalid_fields_fields_other_than_submitted_files_in_request(self):
        group = self.admin_group(self.project)
        response = self.do_invalid_create_object_test(
            group.submissions, self.client,
            group.members.first(),
            self.submissions_url(group),
            {'submitted_files': self.files_to_submit,
             'count_towards_daily_limit': False,
             'count_towards_total_limit': False},
            format='multipart')
        self.assertIn('invalid_fields', response.data)
        self.assertIn('count_towards_daily_limit', response.data['invalid_fields'])
        self.assertIn('count_towards_total_limit', response.data['invalid_fields'])

    def do_normal_submit_test(self, group, user):
        self.add_expected_patterns(group.project)
        response = self.do_create_object_test(
            ag_models.Submission.objects, self.client, user,
            self.submissions_url(group),
            {'submitted_files': self.files_to_submit},
            format='multipart', check_data=False)

        loaded = ag_models.Submission.objects.get(pk=response.data['pk'])
        self.assertEqual(loaded.to_dict(), response.data)

        # We don't know the exact timestamp assigned by the server, so
        # make sure it's reasonably close to what it should be.
        timestamp_difference = loaded.timestamp - timezone.now()
        self.assertLess(timestamp_difference, timezone.timedelta(seconds=2))

        self.assertEqual(group.pk, response.data['group'])
        self.assertEqual(ag_models.Submission.GradingStatus.received,
                         response.data['status'])
        self.assertCountEqual([file_.name for file_ in self.files_to_submit],
                              response.data['submitted_filenames'])
        self.assertCountEqual([], response.data['missing_files'])
        self.assertCountEqual([], response.data['discarded_files'])
        self.assertEqual(user.username, response.data['submitter'])

        loaded.status = ag_models.Submission.GradingStatus.finished_grading
        loaded.save()

    def do_permission_denied_submit_test(self, group, user):
        self.add_expected_patterns(group.project)
        return self.do_permission_denied_create_test(
            ag_models.Submission.objects, self.client,
            user, self.submissions_url(group),
            {'submitted_files': self.files_to_submit}, format='multipart')

    def do_bad_request_submit_test(self, group, user):
        self.add_expected_patterns(group.project)
        return self.do_invalid_create_object_test(
            group.submissions, self.client, user,
            self.submissions_url(group),
            {'submitted_files': self.files_to_submit}, format='multipart')


class CreateSubmissionWithLateDaysTestCase(UnitTestBase):
    def setUp(self):
        super().setUp()

        self.client = APIClient()

        self.num_late_days = 3
        self.course = obj_build.make_course(num_late_days=self.num_late_days)

        self.closing_time = timezone.now()
        self.project = obj_build.make_project(
            self.course, closing_time=self.closing_time, visible_to_students=True,
            allow_late_days=True)
        self.group = obj_build.make_group(2, project=self.project)

    def test_submission_uses_late_day(self):
        submitter = self.group.members.first()
        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)
        self.fail()

    def test_multiple_submissions_in_one_late_day(self):
        submitter = self.group.members.first()
        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)

        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(hours=2),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)
        self.fail()

    def test_multiple_late_days_used_one_at_a_time_same_project(self):
        submitter = self.group.members.first()
        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)

        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(days=1, hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(2, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 2, remaining.late_days_remaining)
        self.fail()

    def test_multiple_late_days_used_different_projects(self):
        other_project = obj_build.make_project(
            self.course, closing_time=self.closing_time, visible_to_students=True)
        other_group = obj_build.make_group(
            project=other_project, members=list(self.group.members.all()))

        submitter = self.group.members.first()
        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)

        self.submit(other_group, submitter,
                    self.closing_time + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()
        other_group.refresh_from_db()

        for user in other_group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])
            self.assertEqual(1, other_group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 2, remaining.late_days_remaining)
        self.fail()

    def test_late_days_used_on_top_of_extension(self):
        extension = self.closing_time + datetime.timedelta(days=2)

        submitter = self.group.members.first()
        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()
        self.assertEqual({}, self.group.late_days_used)

        self.submit(self.group, submitter, extension + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)
        self.fail()

    def test_user_with_no_late_days_in_group_cannot_submit_after_deadline(self):
        submitter = self.group.members.first()
        ag_models.LateDaysRemaining.objects.filter(
            user=submitter, course=self.course
        ).update(late_days_remaining=0)

        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(hours=1),
                    expect_failure=True)
        self.group.refresh_from_db()

        self.assertEqual(self.num_late_days, self.group.late_days_used[submitter.username])
        self.assertEqual(
            0, ag_models.LateDaysRemaining.objects.get(user=submitter, course=self.course))

        for user in self.group.members.exclude(pk=submitter.pk):
            self.assertEqual(0, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days, remaining.late_days_remaining)
        self.fail()

    def test_non_submitting_member_has_no_late_days_submission_does_not_count_for_them(self):
        submitter = self.group.members.first()
        non_submitter = self.group.members.exclude(pk=submitter.pk).first()
        ag_models.LateDaysRemaining.objects.filter(
            user=non_submitter, course=self.course
        ).update(late_days_remaining=0)

        submission = self.submit(self.group, submitter,
                                 self.closing_time + datetime.timedelta(hours=1),
                                 expect_failure=False)
        self.assertEqual([non_submitter.username], submission.does_not_count_for)

        self.group.refresh_from_db()

        self.assertEqual(1, self.group.late_days_used[submitter.username])

        remaining = ag_models.LateDaysRemaining.objects.get(user=submitter, course=self.course)
        self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)
        self.fail()

    def test_group_with_no_late_days_cannot_submit_past_deadline(self):
        for user in self.group.members.all():
            ag_models.LateDaysRemaining.objects.filter(
                user=user, course=self.course
            ).update(late_days_remaining=0)

            self.submit(self.group, user,
                        self.closing_time + datetime.timedelta(hours=1),
                        expect_failure=True)
        self.fail()

    def test_multiple_late_days_used_by_one_submission(self):
        submitter = self.group.members.first()
        self.submit(self.group, submitter,
                    self.closing_time + datetime.timedelta(days=1, hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(2, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 2, remaining.late_days_remaining)
        self.fail()

    def test_submit_far_past_deadline_not_enough_late_days_late_day_total_preserved(self):
        for user in self.group.members.all():
            self.submit(self.group, user,
                        self.closing_time + datetime.timedelta(days=self.num_late_days, hours=1),
                        expect_failure=True)
            self.group.refresh_from_db()

            self.assertEqual(0, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days, remaining.late_days_remaining)
        self.fail()

    def test_late_day_use_disallowed_for_project(self):
        self.project.validate_and_update(allow_late_days=False)
        for user in self.group.members.all():
            self.submit(self.group, user,
                        self.closing_time + datetime.timedelta(hours=1),
                        expect_failure=True)
            self.group.refresh_from_db()

            self.assertEqual(0, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days, remaining.late_days_remaining)
        self.fail()

    def test_late_days_allowed_but_no_closing_time(self):
        self.project.validate_and_update(closing_time=None, soft_closing_time=timezone.now())

        submitter = self.group.members.first()
        self.submit(self.group, submitter,
                    timezone.now() + datetime.timedelta(hours=1),
                    expect_failure=False)
        self.group.refresh_from_db()

        for user in self.group.members.all():
            self.assertEqual(0, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days, remaining.late_days_remaining)
        self.fail()

    def test_bonus_submission_used_on_late_day(self):
        self.project.validate_and_update(
            submission_limit_per_day=1, allow_submissions_past_limit=False,
            num_bonus_submissions=1)
        submitter = self.group.members.first()
        submission1 = self.submit(
            self.group, submitter, self.closing_time + datetime.timedelta(hours=1),
            expect_failure=False)
        self.assertFalse(submission1.is_past_daily_limit)
        self.assertFalse(submission1.is_bonus_submission)

        submission2 = self.submit(
            self.group, submitter, self.closing_time + datetime.timedelta(hours=1),
            expect_failure=False)
        self.assertFalse(submission2.is_past_daily_limit)
        self.assertTrue(submission2.is_bonus_submission)

        for user in self.group.members.all():
            self.assertEqual(1, self.group.late_days_used[user.username])

            remaining = ag_models.LateDaysRemaining.objects.get(user=user, course=self.course)
            self.assertEqual(self.num_late_days - 1, remaining.late_days_remaining)
        self.fail()

    def submit(self, group: ag_models.Group, user: User, timestamp: datetime.datetime,
               *, expect_failure: bool) -> Optional[ag_models.Submission]:
        with mock.patch('autograder.rest_api.views.submission_views.submission_views.timezone.now',
                        new=lambda: timestamp):
            self.client.force_authenticate(user)
            response = self.client.post(reverse('submissions', kwargs={'pk': group.pk}),
                                        {'submitted_files': []}, format='multipart')
            if expect_failure:
                self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
            else:
                self.assertEqual(status.HTTP_201_CREATED, response.status_code)

                submission = ag_models.Submission.objects.get(pk=response.data['pk'])
                submission.status = ag_models.Submission.GradingStatus.finished_grading
                submission.save()

                return submission


class CreateSubmissionDailyLimitBookkeepingTestCase(UnitTestBase):
    def setUp(self):
        super().setUp()
        self.project = obj_build.make_project(
            visible_to_students=True, allow_submissions_past_limit=True)
        self.group = obj_build.make_group(project=self.project)

        # We want to make sure that only submissions for the specified
        # group are counted, so we'll create an extra other submission
        # to make sure it isn't counted.
        other_group = obj_build.build_group()
        self.assertNotEqual(other_group, self.group)
        ag_models.Submission.objects.validate_and_create([], group=other_group)

    def test_no_daily_limit(self):
        self.assertIsNone(self.project.submission_limit_per_day)
        for i in range(10):
            sub = self._create_submission(group=self.group)
            self.assertTrue(sub.count_towards_daily_limit)
            self.assertFalse(sub.is_past_daily_limit)

    def test_not_past_daily_limit(self):
        limit = random.randint(2, 5)
        self.project.validate_and_update(submission_limit_per_day=limit)
        timestamp = timezone.datetime.combine(
            timezone.now().date(), self.project.submission_limit_reset_time)
        timestamp = timestamp.replace(tzinfo=timezone.now().tzinfo)
        for i in range(limit):
            sub = self._create_submission(group=self.group, timestamp=timestamp)
            self.assertTrue(sub.count_towards_daily_limit)
            self.assertFalse(sub.is_past_daily_limit)

        # Place submission at exact beginning of next cycle
        next_cycle_timestamp = timestamp + timezone.timedelta(days=1)
        sub = self._create_submission(group=self.group, timestamp=next_cycle_timestamp)
        self.assertTrue(sub.count_towards_daily_limit)
        self.assertFalse(sub.is_past_daily_limit)

    def test_past_daily_limit(self):
        limit = random.randint(2, 5)
        self.project.validate_and_update(submission_limit_per_day=limit)
        not_past_limit = []
        for i in range(limit):
            not_past_limit.append(self._create_submission(group=self.group))

        for i in range(2):
            sub = self._create_submission(group=self.group)

            self.assertTrue(sub.count_towards_daily_limit)
            self.assertTrue(sub.is_past_daily_limit)

        # Verify that the status of earlier submissions hasn't changed
        for sub in not_past_limit:
            self.assertTrue(sub.count_towards_daily_limit)
            self.assertFalse(sub.is_past_daily_limit)

    def test_submission_limit_from_past_day(self):
        timestamp = timezone.now() + timezone.timedelta(days=-3)
        limit = 2
        self.project.validate_and_update(submission_limit_per_day=limit)
        submissions = []
        sub = self._create_submission(group=self.group, timestamp=timestamp)
        sub.count_towards_daily_limit = False
        sub.save()
        submissions.append(sub)
        self.assertFalse(sub.count_towards_daily_limit)
        for i in range(limit):
            sub = self._create_submission(group=self.group, timestamp=timestamp)
            sub.count_towards_daily_limit = True
            sub.save()
            submissions.append(sub)
            self.assertTrue(sub.count_towards_daily_limit)

        for sub in submissions:
            self.assertFalse(sub.is_past_daily_limit)

    def test_num_submits_towards_limit(self):
        limit = random.randint(3, 5)
        self.project.validate_and_update(submission_limit_per_day=limit)
        total_num_submissions = limit + 2
        for i in range(total_num_submissions):
            self.assertEqual(i, self.group.num_submits_towards_limit)
            sub = self._create_submission(group=self.group)
            self.assertTrue(sub.count_towards_daily_limit)
            if i > limit:
                self.assertTrue(sub.is_past_daily_limit)

        self.assertEqual(total_num_submissions, self.group.num_submits_towards_limit)

    def test_num_submits_towards_limit_non_default_timezone(self):
        local_timezone = 'America/Chicago'
        now = timezone.now()
        now_local = now.astimezone(timezone.pytz.timezone(local_timezone))

        self.project.validate_and_update(
            submission_limit_reset_time=now_local - timezone.timedelta(minutes=5),
            submission_limit_reset_timezone=local_timezone)

        before_reset_time_submission = self._create_submission(
            group=self.group,
            timestamp=now - timezone.timedelta(hours=1))
        after_reset_time_submission = self._create_submission(
            group=self.group,
            timestamp=now + timezone.timedelta(hours=1))

        self.assertEqual(1, self.group.num_submits_towards_limit)

    def test_group_submissions_towards_limit_some_not_counted(self):
        limit = 3
        self.project.validate_and_update(submission_limit_per_day=limit)
        # We'll count every other submission towards the limit
        for i in range(limit * 2):
            count_towards_limit = i % 2 != 0

            sub = self._create_submission(group=self.group)
            sub.count_towards_daily_limit = count_towards_limit
            sub.save()
            self.assertEqual(count_towards_limit,
                             sub.count_towards_daily_limit)
            self.assertFalse(sub.is_past_daily_limit)

            # The number of submits towards the limit should increase by
            # 1 every other submission.
            self.assertEqual((i + 1) // 2, self.group.num_submits_towards_limit)

        sub = self._create_submission(group=self.group)
        self.assertTrue(sub.is_past_daily_limit)

    def test_non_default_limit_reset_time_and_timezone(self):
        reset_timezone = 'America/Detroit'
        reset_datetime = timezone.now().astimezone(
            timezone.pytz.timezone(reset_timezone)
        ).replace(hour=22)
        self.project.validate_and_update(
            submission_limit_reset_time=reset_datetime.time(),
            submission_limit_reset_timezone=reset_timezone,
            submission_limit_per_day=1)

        within_limit_timestamp = reset_datetime + timezone.timedelta(hours=-23)
        within_limit_submission = self._create_submission(
            group=self.group,
            timestamp=within_limit_timestamp)
        self.assertTrue(within_limit_submission.count_towards_daily_limit)
        self.assertFalse(within_limit_submission.is_past_daily_limit)

        past_limit_timestamp = reset_datetime + timezone.timedelta(hours=-1)
        past_limit_submission = self._create_submission(
            group=self.group,
            timestamp=past_limit_timestamp)
        self.assertTrue(past_limit_submission.count_towards_daily_limit)
        self.assertTrue(past_limit_submission.is_past_daily_limit)

        next_cycle_timestamp = reset_datetime
        next_cycle_submission = self._create_submission(
            group=self.group,
            timestamp=next_cycle_timestamp)
        self.assertTrue(next_cycle_submission.count_towards_daily_limit)
        self.assertFalse(next_cycle_submission.is_past_daily_limit)

    def test_statuses_counted_towards_limit(self):
        count_towards_limit_statuses = [
            ag_models.Submission.GradingStatus.received,
            ag_models.Submission.GradingStatus.queued,
            ag_models.Submission.GradingStatus.being_graded,
            ag_models.Submission.GradingStatus.waiting_for_deferred,
            ag_models.Submission.GradingStatus.finished_grading
        ]
        self.assertCountEqual(
            count_towards_limit_statuses,
            ag_models.Submission.GradingStatus.count_towards_limit_statuses)
        num_statuses = len(count_towards_limit_statuses)
        self.project.validate_and_update(submission_limit_per_day=1)

        not_past_limit = self._create_submission(group=self.group)
        self.assertEqual(1, self.group.num_submits_towards_limit)
        self.assertFalse(not_past_limit.is_past_daily_limit)

        for status in count_towards_limit_statuses:
            self.assertEqual(1, self.group.num_submits_towards_limit)
            submission = self._create_submission(group=self.group)
            submission.status = status
            submission.save()
            self.assertEqual(2, self.group.num_submits_towards_limit)
            self.assertTrue(submission.is_past_daily_limit)
            submission.delete()

    def test_statuses_not_counted_towards_limit(self):
        self.project.validate_and_update(submission_limit_per_day=2)
        first_sub = self._create_submission(group=self.group)
        self.assertEqual(1, self.group.num_submits_towards_limit)
        self.assertFalse(first_sub.is_past_daily_limit)

        removed_sub = self._create_submission(group=self.group)
        removed_sub.status = ag_models.Submission.GradingStatus.removed_from_queue
        removed_sub.save()
        self.assertEqual(1, self.group.num_submits_towards_limit)
        self.assertFalse(removed_sub.is_past_daily_limit)

        error_sub = self._create_submission(group=self.group)
        error_sub.status = ag_models.Submission.GradingStatus.error
        error_sub.save()
        self.assertEqual(1, self.group.num_submits_towards_limit)
        self.assertFalse(error_sub.is_past_daily_limit)

        second_sub = self._create_submission(group=self.group)
        self.assertEqual(2, self.group.num_submits_towards_limit)
        self.assertFalse(second_sub.is_past_daily_limit)

        third_sub = self._create_submission(group=self.group)
        self.assertEqual(3, self.group.num_submits_towards_limit)
        self.assertTrue(third_sub.is_past_daily_limit)

    def test_group_uses_bonus_submissions(self):
        num_bonus_submissions = 3
        limit = 5
        project = obj_build.make_project(
            visible_to_students=True,
            submission_limit_per_day=limit,
            num_bonus_submissions=num_bonus_submissions
        )
        group = obj_build.make_group(project=project)
        self.assertEqual(num_bonus_submissions, group.bonus_submissions_remaining)

        for i in range(limit):
            submission = self._create_submission(group)
            self.assertFalse(submission.is_bonus_submission)
            self.assertFalse(submission.is_past_daily_limit)

        self.assertEqual(limit, group.num_submits_towards_limit)

        for i in range(num_bonus_submissions):
            submission = self._create_submission(group)
            self.assertTrue(submission.is_bonus_submission)
            self.assertFalse(submission.is_past_daily_limit)

            group.refresh_from_db()
            self.assertEqual(num_bonus_submissions - (i + 1), group.bonus_submissions_remaining)

        self.assertEqual(limit + num_bonus_submissions, group.num_submits_towards_limit)
        self.assertEqual(0, group.bonus_submissions_remaining)

        num_past_limit = 2
        for i in range(num_past_limit):
            submission = self._create_submission(group)
            self.assertFalse(submission.is_bonus_submission)
            self.assertTrue(submission.is_past_daily_limit)

        self.assertEqual(limit + num_bonus_submissions + num_past_limit,
                         group.num_submits_towards_limit)

    def _create_submission(self, group: ag_models.Group,
                           timestamp: Optional[datetime.datetime]=None) -> ag_models.Submission:
        client = APIClient()
        client.force_authenticate(group.members.first())

        if timestamp is None:
            timestamp = timezone.now()

        with mock.patch('autograder.rest_api.views.submission_views.submission_views.timezone.now',
                        new=lambda: timestamp):
            response = client.post(reverse('submissions', kwargs={'pk': group.pk}),
                                   {'submitted_files': []}, format='multipart')
        self.assertEqual(status.HTTP_201_CREATED, response.status_code, msg=response.data)

        submission = ag_models.Submission.objects.get(pk=response.data['pk'])
        submission.status = ag_models.Submission.GradingStatus.finished_grading
        submission.save()
        return submission


class CreateSubmissionTotalLimitTestCase(UnitTestBase):
    def setUp(self):
        super().setUp()
        self.submission_limit = 2
        self.project = obj_build.make_project(
            total_submission_limit=self.submission_limit,
            visible_to_students=True,
            guests_can_submit=True
        )

        self.client = APIClient()

    def test_staff_submit_no_limit(self):
        group = obj_build.make_group(project=self.project, members_role=obj_build.UserRole.staff)

        for i in range(self.submission_limit + 1):
            self._do_and_check_valid_create_submission(group)

    def test_student_run_out_of_submissions(self):
        group = obj_build.make_group(project=self.project, members_role=obj_build.UserRole.student)

        for i in range(self.submission_limit):
            self._do_and_check_valid_create_submission(group)

        self._do_and_check_invalid_create_submission(group)

    def test_guest_run_out_of_submissions(self):
        group = obj_build.make_group(project=self.project, members_role=obj_build.UserRole.guest)

        for i in range(self.submission_limit):
            self._do_and_check_valid_create_submission(group)

        self._do_and_check_invalid_create_submission(group)

    def test_student_has_refunded_submission(self):
        group = obj_build.make_group(project=self.project, members_role=obj_build.UserRole.student)

        for i in range(self.submission_limit):
            self._do_and_check_valid_create_submission(group)

        self._do_and_check_invalid_create_submission(group)

        # Refund a submission
        refunded_submission: ag_models.Submission = group.submissions.first()
        refunded_submission.validate_and_update(count_towards_total_limit=False)

        self._do_and_check_valid_create_submission(group)

    def test_total_submission_limit_changed_late_new_submits_rejected(self):
        # This should only ever happen if the user makes a mistake.

        group = obj_build.make_group(project=self.project, members_role=obj_build.UserRole.student)
        self.project.validate_and_update(total_submission_limit=None)

        self._do_and_check_valid_create_submission(group)
        self._do_and_check_valid_create_submission(group)

        self.project.validate_and_update(total_submission_limit=1)

        self._do_and_check_invalid_create_submission(group)

    def _do_and_check_valid_create_submission(self, group: ag_models.Group):
        url = reverse('submissions', kwargs={'pk': group.pk})
        self.client.force_authenticate(group.members.first())

        response = self.client.post(url, {'submitted_files': []})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code, msg=response.data)
        self.assertTrue(response.data['count_towards_total_limit'])

        ag_models.Submission.objects.filter(
            pk=response.data['pk']
        ).update(status=ag_models.Submission.GradingStatus.finished_grading)

    def _do_and_check_invalid_create_submission(self, group: ag_models.Group):
        url = reverse('submissions', kwargs={'pk': group.pk})
        self.client.force_authenticate(group.members.first())

        response = self.client.post(url, {'submitted_files': []}, format='multipart')
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        self.assertIn('submission', response.data)


class RetrieveSubmissionAndFileTestCase(test_data.Client,
                                        test_data.Project,
                                        test_data.Submission,
                                        test_impls.GetObjectTest,
                                        UnitTestBase):
    def test_admin_or_staff_view_submission(self):
        for project in self.all_projects:
            for submission in self.at_least_enrolled_submissions(project):
                for user in self.admin, self.staff:
                    self.do_get_object_test(
                        self.client, user, submission_url(submission),
                        submission.to_dict())
                    self.do_get_files_test_case(submission, user)

        for project in self.public_projects:
            submission = self.non_enrolled_submission(project)
            for user in self.admin, self.staff:
                self.do_get_object_test(
                    self.client, user, submission_url(submission),
                    submission.to_dict())
                self.do_get_files_test_case(submission, user)

    def test_enrolled_view_submission(self):
        for project in self.visible_projects:
            submission = self.enrolled_submission(project)
            for user in submission.group.members.all():
                self.do_get_object_test(
                    self.client, user, submission_url(submission),
                    submission.to_dict())
                self.do_get_files_test_case(submission, user)

    def test_non_enrolled_view_submission(self):
        submission = self.enrolled_submission(self.visible_public_project)
        for user in submission.group.members.all():
            self.do_get_object_test(
                self.client, user, submission_url(submission),
                submission.to_dict())
            self.do_get_files_test_case(submission, user)

    def test_non_member_view_submission_forbidden(self):
        submission = self.enrolled_submission(self.visible_public_project)
        other_user = self.clone_user(self.enrolled)
        for user in other_user, self.nobody, self.handgrader:
            self.do_permission_denied_get_test(
                self.client, user, submission_url(submission))
            self.do_get_files_permission_denied_test_case(submission, user)

    def test_enrolled_view_submission_project_hidden_forbidden(self):
        for project in self.hidden_projects:
            submission = self.enrolled_submission(project)
            self.do_permission_denied_get_test(
                self.client, self.enrolled, submission_url(submission))
            self.do_get_files_permission_denied_test_case(
                submission, self.enrolled)

    def test_non_enrolled_view_submission_project_hidden_forbidden(self):
        submission = self.non_enrolled_submission(self.hidden_public_project)
        self.do_permission_denied_get_test(
            self.client, self.nobody, submission_url(submission))
        self.do_get_files_permission_denied_test_case(submission, self.nobody)

    def test_non_enrolled_view_submission_project_private_forbidden(self):
        submission = self.non_enrolled_submission(self.visible_public_project)
        self.visible_public_project.validate_and_update(
            guests_can_submit=False)
        self.do_permission_denied_get_test(
            self.client, self.nobody, submission_url(submission))
        self.do_get_files_permission_denied_test_case(submission, self.nobody)

    def test_get_malicious_filename_not_found(self):
        filename = os.path.abspath(__file__)
        submission = self.enrolled_submission(self.visible_public_project)
        self.client.force_authenticate(self.enrolled)
        url = file_url(submission, filename)
        response = self.client.get(url)
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_get_file_missing_filename_param(self):
        submission = self.enrolled_submission(self.visible_public_project)
        self.client.force_authenticate(self.enrolled)
        response = self.client.get(
            reverse('submission-file', kwargs={'pk': submission.pk}))
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def do_get_files_test_case(self, submission, user):
        for filename in submission.submitted_filenames:
            self.do_get_content_test(
                self.client, user, file_url(submission, filename),
                submission.get_file(filename).read())

    def do_get_files_permission_denied_test_case(self, submission, user):
        for filename in submission.submitted_filenames:
            self.do_permission_denied_get_test(
                self.client, user, file_url(submission, filename),
                format='multipart')

    def do_get_content_test(self, client, user, url, expected_content):
        client.force_authenticate(user)
        response = client.get(url)
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(
            expected_content,
            b''.join((chunk for chunk in response.streaming_content)))


class UpdateSubmissionTestCase(test_data.Client,
                               test_data.Project,
                               test_data.Submission,
                               test_impls.UpdateObjectTest,
                               UnitTestBase):
    def test_admin_edit_count_towards_limit(self):
        for project in self.all_projects:
            for submission in self.at_least_enrolled_submissions(project):
                self.assertTrue(submission.count_towards_daily_limit)
                for val in False, True:
                    self.do_patch_object_test(
                        submission, self.client, self.admin,
                        submission_url(submission),
                        {'count_towards_daily_limit': val})

        for project in self.visible_public_project, self.hidden_public_project:
            submission = self.non_enrolled_submission(project)
            self.assertTrue(submission.count_towards_daily_limit)
            for val in False, True:
                self.do_patch_object_test(
                    submission, self.client, self.admin,
                    submission_url(submission),
                    {'count_towards_daily_limit': val})

    def test_admin_edit_submission_invalid_fields(self):
        for submission in self.all_submissions(self.visible_public_project):
            self.do_patch_object_invalid_args_test(
                submission, self.client, self.admin,
                submission_url(submission), {'is_past_daily_limit': False})

    def test_other_edit_count_towards_limit_permission_denied(self):
        submissions = (
            self.staff_submission(self.visible_public_project),
            self.enrolled_submission(self.visible_public_project),
            self.non_enrolled_submission(self.visible_public_project))
        for submission in submissions:
            self.do_patch_object_permission_denied_test(
                submission, self.client,
                submission.group.members.first(),
                submission_url(submission),
                {'count_towards_daily_limit': False})

    def test_handgrader_edit_submission_permission_denied(self):
        submissions = (
            self.staff_submission(self.visible_public_project),
            self.enrolled_submission(self.visible_public_project),
            self.non_enrolled_submission(self.visible_public_project))
        for submission in submissions:
            self.do_patch_object_permission_denied_test(
                submission, self.client,
                self.handgrader,
                submission_url(submission),
                {'count_towards_daily_limit': False})


class RemoveFromQueueTestCase(test_data.Client,
                              test_data.Project,
                              test_data.Submission,
                              UnitTestBase):
    def test_admin_or_staff_remove_own_from_queue(self):
        for project in self.all_projects:
            for submission in self.staff_submissions(project):
                self.do_valid_remove_from_queue_test(submission)

    def test_enrolled_remove_own_from_queue(self):
        for project in self.visible_projects:
            submission = self.enrolled_submission(project)
            self.do_valid_remove_from_queue_test(submission)

    def test_non_enrolled_remove_own_from_queue(self):
        submission = self.non_enrolled_submission(self.visible_public_project)
        self.do_valid_remove_from_queue_test(submission)

    def test_enrolled_remove_from_queue_project_hidden_permission_denied(self):
        for project in self.hidden_projects:
            submission = self.enrolled_submission(project)
            self.do_permission_denied_remove_from_queue_test(
                submission, submission.group.members.first())

    def test_non_enrolled_remove_from_queue_project_hidden_permission_denied(self):
        submission = self.non_enrolled_submission(self.hidden_public_project)
        self.do_permission_denied_remove_from_queue_test(
            submission, submission.group.members.first())

    def test_handgrader_remove_student_submission_from_queue_permission_denied(self):
        self.do_permission_denied_remove_from_queue_test(
            self.enrolled_submission(self.visible_projects[0]), self.handgrader)

    def test_non_enrolled_remove_from_queue_project_private_permission_denied(self):
        submission = self.non_enrolled_submission(self.visible_public_project)
        self.visible_public_project.validate_and_update(
            guests_can_submit=False)
        self.do_permission_denied_remove_from_queue_test(
            submission, submission.group.members.first())

    def test_remove_others_submission_from_queue_permission_denied(self):
        for submission in self.all_submissions(self.visible_public_project):
            for user in self.admin, self.staff, self.enrolled, self.nobody:
                group = submission.group
                if group.members.filter(pk=user.pk).exists():
                    continue

                self.do_permission_denied_remove_from_queue_test(
                    submission, user)

    def test_error_remove_submission_not_in_queue(self):
        statuses = set(Submission.GradingStatus.values)
        statuses.remove(Submission.GradingStatus.queued)
        statuses.remove(Submission.GradingStatus.received)
        for submission in self.all_submissions(self.visible_public_project):
            for grading_status in statuses:
                submission.status = grading_status
                submission.save()
                self.do_invalid_remove_from_queue_test(submission)

    def do_valid_remove_from_queue_test(self, submission, user=None):
        for grading_status in (Submission.GradingStatus.received,
                               Submission.GradingStatus.queued):
            submission.status = grading_status
            submission.save()

            if user is None:
                user = submission.group.members.first()

            self.client.force_authenticate(user)
            response = self.client.post(
                submission_remove_from_queue_url(submission))
            self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

            submission.refresh_from_db()

            self.assertEqual(Submission.GradingStatus.removed_from_queue,
                             submission.status)

    def do_permission_denied_remove_from_queue_test(self, submission, user):
        self._do_bad_remove_from_queue_test(
            submission, user, status.HTTP_403_FORBIDDEN)

    def do_invalid_remove_from_queue_test(self, submission, user=None):
        self._do_bad_remove_from_queue_test(
            submission, user, status.HTTP_400_BAD_REQUEST)

    def _do_bad_remove_from_queue_test(self, submission, user, expected_status):
        original_status = submission.status
        if user is None:
            user = submission.group.members.first()

        self.client.force_authenticate(user)
        response = self.client.post(submission_remove_from_queue_url(submission))
        self.assertEqual(expected_status, response.status_code)

        submission.refresh_from_db()

        self.assertEqual(original_status, submission.status)


def submission_remove_from_queue_url(submission):
    return reverse('submission-remove-from-queue',
                   kwargs={'pk': submission.pk})


def submission_url(submission):
    return reverse('submission-detail', kwargs={'pk': submission.pk})


def file_url(submission, filename):
    query_params = QueryDict(mutable=True)
    query_params.update({'filename': filename})
    return (reverse('submission-file', kwargs={'pk': submission.pk})
            + '?' + query_params.urlencode())
