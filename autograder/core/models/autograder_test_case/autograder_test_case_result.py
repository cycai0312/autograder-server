import difflib
import uuid

from django.core.cache import cache
from django.utils import timezone
from django.db import models

from . import feedback_config as fdbk_conf


class AutograderTestCaseResult(models.Model):
    """
    This class stores the data from an autograder test case
    and provides an interface for serializing the data.
    """
    # Using a string here instead of class to get around circular dependency
    test_case = models.ForeignKey(
        "AutograderTestCaseBase", related_name='dependent_results',
        help_text='''The test case whose results this object is storing.''')

    submission = models.ForeignKey(
        'Submission',
        related_name='results',
        help_text='''The submission the test case was run for.''')

    return_code = models.IntegerField(
        null=True, default=None,
        help_text='''The return code of the program that was tested.''')

    standard_output = models.TextField(
        help_text='''The contents of the standard output stream of the
            program that was tested.''')
    standard_error_output = models.TextField(
        help_text='''The contents of the standard error stream of the
            program that was tested.''')

    timed_out = models.BooleanField(
        default=False,
        help_text='''Whether the program exceeded the time limit.''')

    valgrind_return_code = models.IntegerField(
        null=True, default=None,
        help_text='''The return code of the program valgrind when run
            against the program being tested.''')
    valgrind_output = models.TextField(
        help_text='''The stderr contents of the program valgrind when
            run against the program being tested.''')

    # COMPILED TEST CASES ONLY

    compilation_return_code = models.IntegerField(
        null=True, default=None,
        help_text='''The return code of the command used to compile the
            program being tested.''')
    compilation_standard_output = models.TextField(
        help_text='''The contents of the standard output stream of the
            command used to compile the program being tested.''')
    compilation_standard_error_output = models.TextField(
        help_text='''The contents of the standard error stream of the
            command used to compile the program being tested.''')

    # -------------------------------------------------------------------------

    @property
    def basic_score(self):
        '''
        The number of points awarded for the related test case using the
        primary feedback configuration, self.test_result.feedback_config
        '''
        key = self.basic_score_cache_key
        score = cache.get(key)
        if score is not None:
            return score

        fdbk = self.get_feedback()
        try:
            valgrind_val = -fdbk.valgrind_points_deducted
        except Exception:
            valgrind_val = None

        values = (fdbk.return_code_points, fdbk.stdout_points,
                  fdbk.stderr_points, fdbk.compilation_points,
                  valgrind_val)

        score = sum((val for val in values if val is not None))
        cache.set(key, score, timeout=None)
        return score

    @property
    def basic_score_cache_key(self):
        return 'result_basic_score{}'.format(self.pk)

    def get_feedback(self, user=None, is_ultimate_submission=False,
                     use_student_view=False):
        return AutograderTestCaseResult._FeedbackCalculator(
            self, user, is_ultimate_submission, use_student_view)

    class _FeedbackCalculator:
        def __init__(self, result, user, is_ultimate_submission,
                     use_student_view):
            # Note to self: staff viewers always get "staff viewer" fdbk, but
            # only see "visible to staff viewer" results when listing results.
            # "staff viewer" fdbk should default to max.

            # If user is staff viewing their own result, max fdbk
            # If user is staff viewing someone else's result,
            #   use "staff viewer fdbk" unless "use_student_view" is true
            # If user is student or use_student_view is true:
            #   - If submission was past limit, use "past limit fdbk"
            #   - If submission is ultimate and is_ultimate_submission is True,
            #       use "ultimate fdbk"

            self._fdbk = result.test_case.feedback_configuration
            self._result = result

        @property
        def fdbk_config_dict(self):
            '''
            Returns the internal feedback configuration as a dictionary.
            '''
            return self._fdbk.to_dict()

        @property
        def ag_test_name(self):
            random = fdbk_conf.AGTestNameFdbkLevel.randomly_obfuscate_name
            if self._fdbk.ag_test_name_fdbk == random:
                return 'test{}'.format(uuid.uuid4().hex)

            deterministic = (
                fdbk_conf.AGTestNameFdbkLevel.deterministically_obfuscate_name)
            if self._fdbk.ag_test_name_fdbk == deterministic:
                return 'test{}'.format(self._result.test_case.pk)

            return self._result.test_case.name

        @property
        def return_code_correct(self):
            if (not self._ret_code_checked() or
                    self._no_ret_code_correctness_fdbk()):
                return None

            if self._result.test_case.expect_any_nonzero_return_code:
                return self._result.return_code != 0

            return (self._result.return_code ==
                    self._result.test_case.expected_return_code)

        @property
        def expected_return_code(self):
            if not self._ret_code_checked() or not self._show_ret_code_diff():
                return None

            return self._result.test_case.expected_return_code

        @property
        def actual_return_code(self):
            if self._fdbk.show_return_code:
                return self._result.return_code

            if not self._ret_code_checked() or not self._show_ret_code_diff():
                return None

            return self._result.return_code

        def _show_ret_code_diff(self):
            return (
                self._fdbk.return_code_fdbk ==
                fdbk_conf.ReturnCodeFdbkLevel.show_expected_and_actual_values)

        @property
        def return_code_points(self):
            if (not self._ret_code_checked() or
                    self._no_ret_code_correctness_fdbk() or
                    self._no_pts_fdbk()):
                return None

            if not self.return_code_correct:
                return 0

            return self._result.test_case.points_for_correct_return_code

        def _no_ret_code_correctness_fdbk(self):
            return (self._fdbk.return_code_fdbk ==
                    fdbk_conf.ReturnCodeFdbkLevel.no_feedback)

        def _ret_code_checked(self):
            return (self._result.test_case.expected_return_code is not None or
                    self._result.test_case.expect_any_nonzero_return_code)

        # ---------------------------------------------------------------------

        @property
        def stdout_correct(self):
            if (self._no_stdout_correctness_fdbk() or
                    not self._stdout_checked()):
                return None

            return (self._result.standard_output ==
                    self._result.test_case.expected_standard_output)

        @property
        def stdout_content(self):
            if not self._fdbk.show_stdout_content:
                return None

            return self._result.standard_output

        @property
        def stdout_diff(self):
            if not self._show_stdout_diff() or not self._stdout_checked():
                return None

            if self.stdout_correct:
                return ''

            return _get_diff(self._result.test_case.expected_standard_output,
                             self._result.standard_output)

        @property
        def stdout_points(self):
            if (not self._stdout_checked() or
                    self._no_stdout_correctness_fdbk() or
                    self._no_pts_fdbk()):
                return None

            return (0 if not self.stdout_correct
                    else self._result.test_case.points_for_correct_stdout)

        def _no_stdout_correctness_fdbk(self):
            return (self._fdbk.stdout_fdbk ==
                    fdbk_conf.StdoutFdbkLevel.no_feedback)

        def _show_stdout_diff(self):
            return (self._fdbk.stdout_fdbk ==
                    fdbk_conf.StdoutFdbkLevel.show_expected_and_actual_values)

        def _stdout_checked(self):
            return self._result.test_case.expected_standard_output

        # ---------------------------------------------------------------------

        @property
        def stderr_correct(self):
            if (self._no_stderr_correctness_fdbk() or
                    not self._stderr_checked()):
                return None

            return (self._result.standard_error_output ==
                    self._result.test_case.expected_standard_error_output)

        @property
        def stderr_content(self):
            if not self._fdbk.show_stderr_content:
                return None

            return self._result.standard_error_output

        @property
        def stderr_diff(self):
            if not self._stderr_checked() or not self._show_stderr_diff():
                return None

            if self.stderr_correct:
                return ''

            return _get_diff(
                self._result.test_case.expected_standard_error_output,
                self._result.standard_error_output)

        @property
        def stderr_points(self):
            if (not self._stderr_checked() or
                    self._no_stderr_correctness_fdbk() or
                    self._no_pts_fdbk()):
                return None

            return (0 if not self.stderr_correct
                    else self._result.test_case.points_for_correct_stderr)

        def _no_stderr_correctness_fdbk(self):
            return (self._fdbk.stderr_fdbk ==
                    fdbk_conf.StderrFdbkLevel.no_feedback)

        def _show_stderr_diff(self):
            return (self._fdbk.stderr_fdbk ==
                    fdbk_conf.StderrFdbkLevel.show_expected_and_actual_values)

        def _stderr_checked(self):
            return self._result.test_case.expected_standard_error_output

        # ---------------------------------------------------------------------

        @property
        def compilation_succeeded(self):
            if (self._no_compiler_fdbk() or
                    not self._result.test_case.test_checks_compilation()):
                return None

            return self._result.compilation_return_code == 0

        @property
        def compilation_stdout(self):
            if (not self._show_compiler_output() or
                    not self._result.test_case.test_checks_compilation()):
                return None

            return self._result.compilation_standard_output

        @property
        def compilation_stderr(self):
            if (not self._show_compiler_output() or
                    not self._result.test_case.test_checks_compilation()):
                return None

            return self._result.compilation_standard_error_output

        @property
        def compilation_points(self):
            if (self._no_compiler_fdbk() or
                    self._no_pts_fdbk() or
                    not self._result.test_case.test_checks_compilation()):
                return None

            return (0 if not self.compilation_succeeded
                    else self._result.test_case.points_for_compilation_success)

        def _no_compiler_fdbk(self):
            compiler_fdbk = (
                self._result.test_case.feedback_configuration.compilation_fdbk)
            return compiler_fdbk == fdbk_conf.CompilationFdbkLevel.no_feedback

        def _show_compiler_output(self):
            compiler_fdbk = (
                self._result.test_case.feedback_configuration.compilation_fdbk)
            return (compiler_fdbk ==
                    fdbk_conf.CompilationFdbkLevel.show_compiler_output)

        # ---------------------------------------------------------------------

        @property
        def valgrind_errors_reported(self):
            if (self._no_valgrind_fdbk() or
                    not self._result.test_case.use_valgrind):
                return None

            return self._result.valgrind_return_code != 0

        @property
        def valgrind_output(self):
            if (not self._show_valgrind_output() or
                    not self._result.test_case.use_valgrind):
                return None

            return self._result.valgrind_output

        @property
        def valgrind_points_deducted(self):
            if (self._no_valgrind_fdbk() or
                    self._no_pts_fdbk() or
                    not self._result.test_case.use_valgrind):
                return None

            return (0 if not self.valgrind_errors_reported
                    else self._result.test_case.deduction_for_valgrind_errors)

        def _no_valgrind_fdbk(self):
            valgrind_fdbk = (
                self._result.test_case.feedback_configuration.valgrind_fdbk)
            return valgrind_fdbk == fdbk_conf.ValgrindFdbkLevel.no_feedback

        def _show_valgrind_output(self):
            valgrind_fdbk = (
                self._result.test_case.feedback_configuration.valgrind_fdbk)
            return (valgrind_fdbk ==
                    fdbk_conf.ValgrindFdbkLevel.show_valgrind_output)

        # ---------------------------------------------------------------------

        def _no_pts_fdbk(self):
            return self._fdbk.points_fdbk == fdbk_conf.PointsFdbkLevel.hide

# -----------------------------------------------------------------------------

_DIFFER = difflib.Differ()


def _get_diff(first, second):
    return list(_DIFFER.compare(
        first.splitlines(keepends=True), second.splitlines(keepends=True)))
