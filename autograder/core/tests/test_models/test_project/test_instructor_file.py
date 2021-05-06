import os

from django.core import exceptions
from django.core.files.uploadedfile import SimpleUploadedFile

import autograder.core.utils as core_ut
import autograder.utils.testing.model_obj_builders as obj_build
from autograder import utils
from autograder.core import constants
from autograder.core.models.project.instructor_file import InstructorFile
from autograder.utils.testing import UnitTestBase


class _SetUp(UnitTestBase):
    def setUp(self):
        super().setUp()

        self.project = obj_build.build_project()
        self.file_obj = SimpleUploadedFile(
            'instructor_file.txt',
            b'contents more contents.')


# Note: Django 3.2 raises SuspiciousFileOperation when trying to create
# an UploadedFile (or any of its subclasses). Therefore, we no longer
# need to (or can) test that we throw a ValidationError if a filename
# is '..', '.', or '' when *creating* the file.
class CreateInstuctorFileTestCase(_SetUp):
    def test_valid_create(self):
        instructor_file = InstructorFile.objects.validate_and_create(
            project=self.project,
            file_obj=self.file_obj)

        self.assertEqual(self.file_obj.name, instructor_file.name)
        expected_abspath = os.path.join(
            core_ut.get_project_files_dir(self.project), self.file_obj.name)
        self.assertEqual(expected_abspath, instructor_file.abspath)
        self.assertEqual(self.file_obj.size, instructor_file.size)

        self.file_obj.seek(0)
        self.assertEqual(self.file_obj.read(), instructor_file.file_obj.read())

        with utils.ChangeDirectory(core_ut.get_project_files_dir(self.project)):
            self.assertTrue(os.path.isfile(self.file_obj.name))

    # Note: Django's uploaded file objects strip path information from
    # uploaded files
    def test_path_info_stripped_from_instructor_filenames(self):
        # This test makes sure that these objects don't allow
        # the user to add files in subdirectories (or worse,
        # somewhere else in the filesystem).
        new_filename = 'new_filename.txt'
        self.file_obj.name = '../../' + new_filename

        instructor_file = InstructorFile.objects.validate_and_create(
            project=self.project,
            file_obj=self.file_obj)

        self.assertEqual(new_filename, instructor_file.name)

    def test_error_file_too_big(self):
        too_big = SimpleUploadedFile('wee', b'a' * (constants.MAX_INSTRUCTOR_FILE_SIZE + 1))
        with self.assertRaises(exceptions.ValidationError) as cm:
            InstructorFile.objects.validate_and_create(project=self.project, file_obj=too_big)

        self.assertIn('content', cm.exception.message_dict)

    def test_error_filename_already_exists(self):
        self.file_obj.seek(0)
        instructor_file = InstructorFile.objects.validate_and_create(
            project=self.project,
            file_obj=self.file_obj)

        duplicate_file = SimpleUploadedFile(
            self.file_obj.name, b'some content that should not be here')
        with self.assertRaises(exceptions.ValidationError) as cm:
            InstructorFile.objects.validate_and_create(
                project=self.project, file_obj=duplicate_file)

        self.assertIn('filename', cm.exception.message_dict)
        self.file_obj.seek(0)
        self.assertEqual(instructor_file.file_obj.read(), self.file_obj.read())

    def test_different_projects_same_name_no_error(self):
        other_project = obj_build.make_project(course=self.project.course)
        InstructorFile.objects.validate_and_create(project=self.project, file_obj=self.file_obj)
        InstructorFile.objects.validate_and_create(project=other_project, file_obj=self.file_obj)


class RenameInstructorFileTestCase(_SetUp):
    def setUp(self):
        super().setUp()

        self.instructor_file = InstructorFile.objects.validate_and_create(
            project=self.project,
            file_obj=self.file_obj)

    def test_valid_rename(self):
        original_last_modified = self.instructor_file.last_modified
        new_name = 'new_filename'
        self.instructor_file.rename(new_name)

        self.instructor_file.refresh_from_db()

        self.assertNotEqual(original_last_modified, self.instructor_file.last_modified)
        self.assertEqual(new_name, self.instructor_file.name)
        with utils.ChangeDirectory(core_ut.get_project_files_dir(self.project)):
            self.assertTrue(os.path.isfile(new_name))

    def test_path_info_stripped_from_new_name(self):
        name_with_path = '../../hack/you'
        self.instructor_file.rename(name_with_path)

        self.instructor_file.refresh_from_db()

        expected_new_name = 'you'
        self.assertEqual(expected_new_name, self.instructor_file.name)
        with utils.ChangeDirectory(core_ut.get_project_files_dir(self.project)):
            self.assertTrue(os.path.isfile(expected_new_name))

    def test_error_illegal_filenames(self):
        for filename in ['', '.', '..']:
            with self.assertRaises(exceptions.ValidationError,
                                   msg='Filename: ' + filename) as cm:
                self.instructor_file.rename(filename)

            self.assertIn('name', cm.exception.message_dict)

    def test_error_new_name_already_exists(self):
        other_file: InstructorFile = InstructorFile.objects.validate_and_create(
            project=self.project,
            file_obj=SimpleUploadedFile(
                'other_file.txt',
                b'contents more contents.'
            )
        )

        with self.assertRaises(exceptions.ValidationError) as cm:
            other_file.rename(self.file_obj.name)

        self.assertIn('filename', cm.exception.message_dict)
        other_file.refresh_from_db()
        self.assertEqual('other_file.txt', other_file.name)


class DeleteInstructorFileTestCase(_SetUp):
    def test_file_deleted_from_filesystem(self):
        instructor_file = InstructorFile.objects.validate_and_create(
            project=self.project,
            file_obj=self.file_obj)
        self.assertTrue(os.path.exists(instructor_file.abspath))

        instructor_file.delete()
        self.assertFalse(os.path.exists(instructor_file.abspath))


class InstructorFileMiscTestCase(_SetUp):
    def test_order_by_name(self):
        file1 = InstructorFile.objects.validate_and_create(
            project=self.project, file_obj=SimpleUploadedFile('file1', b''))
        file3 = InstructorFile.objects.validate_and_create(
            project=self.project, file_obj=SimpleUploadedFile('file3', b''))
        file2 = InstructorFile.objects.validate_and_create(
            project=self.project, file_obj=SimpleUploadedFile('file2', b''))

        self.assertSequenceEqual([file1, file2, file3], InstructorFile.objects.all())

    def test_serializable_fields(self):
        expected = [
            'pk',
            'name',
            'size',
            'project',
            'last_modified',
        ]

        self.assertCountEqual(expected,
                              InstructorFile.get_serializable_fields())

        instructor_file = InstructorFile.objects.validate_and_create(
            project=self.project,
            file_obj=self.file_obj)
        self.assertTrue(instructor_file.to_dict())

    def test_editable_fields(self):
        expected = []
        self.assertCountEqual(expected, InstructorFile.get_editable_fields())
