from __future__ import annotations

from pathlib import Path
from typing import Any, BinaryIO, Callable, Optional

from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework import response

import autograder.core.models as ag_models
import autograder.core.utils as core_ut
import autograder.rest_api.permissions as ag_permissions
from autograder.core.caching import get_cached_submission_feedback
from autograder.core.models.submission import get_submissions_with_results_queryset
from autograder.core.submission_feedback import (
    AGTestCommandResultFeedback, AGTestPreLoader, AGTestSuiteResultFeedback,
    SubmissionResultFeedback
)
from autograder.rest_api.schema import APITags, CustomViewSchema, as_content_obj
from autograder.rest_api.serve_file import serve_file
from autograder.rest_api.views.ag_model_views import AGModelAPIView, require_query_params

from .common import FDBK_CATEGORY_PARAM, validate_fdbk_category


class SubmissionResultsViewBase(AGModelAPIView):
    permission_classes = [
        ag_permissions.can_view_project(),
        ag_permissions.is_staff_or_group_member(),
        ag_permissions.can_request_feedback_category()
    ]
    model_manager = ag_models.Submission.objects.select_related('group__project__course')

    @method_decorator(require_query_params(FDBK_CATEGORY_PARAM))
    def get(self, *args: Any, **kwargs: Any) -> HttpResponse:
        fdbk_category = self._get_fdbk_category()
        submission_fdbk = self._get_submission_fdbk(fdbk_category)
        return self._make_response(submission_fdbk, fdbk_category)

    def _get_fdbk_category(self) -> ag_models.FeedbackCategory:
        fdbk_category_arg = self.request.query_params.get(FDBK_CATEGORY_PARAM)
        assert fdbk_category_arg is not None
        return validate_fdbk_category(fdbk_category_arg)

    def _get_submission_fdbk(
        self, fdbk_category: ag_models.FeedbackCategory
    ) -> SubmissionResultFeedback:
        submission = self.get_object()
        return SubmissionResultFeedback(
            submission,
            fdbk_category,
            AGTestPreLoader(submission.project)
        )

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        raise NotImplementedError


class SubmissionResultsView(SubmissionResultsViewBase):
    schema = CustomViewSchema([APITags.submissions], {
        'GET': {
            'operation_id': 'getSubmissionResults',
            'parameters': [{'$ref': '#/components/parameters/feedbackCategory'}],
            'responses': {
                '200': {
                    'content': as_content_obj(SubmissionResultFeedback),
                    'description': ''
                }
            }
        }
    })

    def _get_submission_fdbk(
        self, fdbk_category: ag_models.FeedbackCategory
    ) -> SubmissionResultFeedback:
        """
        Loads the requested submission, prefetching result data, and
        returns a SubmissionResultFeedback initialized with
        fdbk_category.
        """
        model_manager = get_submissions_with_results_queryset(base_manager=self.model_manager)
        submission = self.get_object(model_manager_override=model_manager)
        return SubmissionResultFeedback(
            submission,
            fdbk_category,
            AGTestPreLoader(submission.project)
        )

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        if (fdbk_category != ag_models.FeedbackCategory.normal
                or self.request.query_params.get('use_cache', 'true') != 'true'):
            return response.Response(submission_fdbk.to_dict())

        submission = self.get_object()
        not_done_enough_to_cache = (
            submission.status != ag_models.Submission.GradingStatus.waiting_for_deferred
            and submission.status != ag_models.Submission.GradingStatus.finished_grading)
        if not_done_enough_to_cache:
            return response.Response(submission_fdbk.to_dict())

        return response.Response(get_cached_submission_feedback(submission, submission_fdbk))


class _OutputViewSchema(CustomViewSchema):
    def __init__(self, operation_id: str):
        super().__init__([APITags.submission_output], {
            'GET': {
                'operation_id': operation_id,
                'parameters': [{'$ref': '#/components/parameters/feedbackCategory'}],
                'responses': {
                    '200': {
                        'content': {
                            'application/octet-stream': {
                                'schema': {'type': 'string', 'format': 'binary'},
                            },
                        },
                        'description': ''
                    }
                }
            }
        })


class AGTestSuiteResultStdoutView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getAGTestSuiteResultStdout')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        suite_result_pk = self.kwargs['result_pk']
        return _get_setup_output(submission_fdbk,
                                 suite_result_pk,
                                 lambda fdbk_calc: fdbk_calc.setup_stdout_filename)


class AGTestSuiteResultStderrView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getAGTestSuiteResultStderr')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        suite_result_pk = self.kwargs['result_pk']
        return _get_setup_output(submission_fdbk,
                                 suite_result_pk,
                                 lambda fdbk_calc: fdbk_calc.setup_stderr_filename)


class AGTestSuiteResultOutputSizeView(SubmissionResultsViewBase):
    schema = CustomViewSchema([APITags.submission_output], {
        'GET': {
            'operation_id': 'getAGTestSuiteResultOutputSize',
            'parameters': [{'$ref': '#/components/parameters/feedbackCategory'}],
            'responses': {
                '200': {
                    'description': '',
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'setup_stdout_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'setup_stdout_truncated': {
                                        'type': 'boolean',
                                        'nullable': True,
                                    },
                                    'setup_stderr_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'setup_stderr_truncated': {
                                        'type': 'boolean',
                                        'nullable': True,
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    })

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        suite_result_pk = self.kwargs['result_pk']
        suite_fdbk = _find_ag_suite_result(submission_fdbk, suite_result_pk)
        if suite_fdbk is None:
            return response.Response(None)
        return response.Response({
            'setup_stdout_size': suite_fdbk.get_setup_stdout_size(),
            'setup_stdout_truncated': suite_fdbk.setup_stdout_truncated,
            'setup_stderr_size': suite_fdbk.get_setup_stderr_size(),
            'setup_stderr_truncated': suite_fdbk.setup_stderr_truncated,
        })


def _get_setup_output(
    submission_fdbk: SubmissionResultFeedback,
    suite_result_pk: int,
    get_output_filename_fn: Callable[[AGTestSuiteResultFeedback], Path | None]
) -> HttpResponse:
    suite_fdbk = _find_ag_suite_result(submission_fdbk, suite_result_pk)
    if suite_fdbk is None:
        return response.Response(None)
    path = get_output_filename_fn(suite_fdbk)
    if path is None:
        return response.Response(None)
    return serve_file(path)


class AGTestSuiteDescriptionsView(SubmissionResultsViewBase):
    schema = CustomViewSchema([APITags.submissions], {
        'GET': {
            'operation_id': 'getAGTestSuiteResultDescriptions',
            'parameters': [{'$ref': '#/components/parameters/feedbackCategory'}],
            'responses': {
                '200': {
                    'description': '',
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'required': [
                                    'staff_description',
                                    'student_description',
                                ],
                                'properties': {
                                    'staff_description': {
                                        'type': 'string',
                                        'nullable': True,
                                    },
                                    'student_description': {
                                        'type': 'string',
                                        'nullable': True,
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    })

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        suite_result_pk = self.kwargs['result_pk']
        suite_fdbk = _find_ag_suite_result(submission_fdbk, suite_result_pk)
        if suite_fdbk is None:
            return response.Response(None)
        return response.Response({
            # 'staff_description':, FIXME
            # 'student_description':,
        })


def _find_ag_suite_result(submission_fdbk: SubmissionResultFeedback,
                          suite_result_pk: int) -> Optional[AGTestSuiteResultFeedback]:
    """
    :raises: Http404 exception if a suite result with the
             given primary key doesn't exist in the database.
    :return: The suite result with the given primary key
             if it can be found in submission_fdbk, None otherwise.
    """
    suite_result = get_object_or_404(ag_models.AGTestSuiteResult.objects.all(),
                                     pk=suite_result_pk)

    for suite_fdbk in submission_fdbk.ag_test_suite_results:
        if suite_fdbk.pk == suite_result.pk:
            return suite_fdbk

    return None


class AGTestCommandResultStdoutView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getAGTestCommandResultStdout')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        cmd_result_pk = self.kwargs['result_pk']
        return _get_cmd_result_output(
            submission_fdbk,
            cmd_result_pk,
            lambda fdbk_calc: fdbk_calc.stdout_filename)


class AGTestCommandResultStderrView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getAGTestCommandResultStderr')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        cmd_result_pk = self.kwargs['result_pk']
        return _get_cmd_result_output(
            submission_fdbk,
            cmd_result_pk,
            lambda fdbk_calc: fdbk_calc.stderr_filename)


class AGTestCommandResultOutputSizeView(SubmissionResultsViewBase):
    schema = CustomViewSchema([APITags.submission_output], {
        'GET': {
            'operation_id': 'getAGTestCommandResultOutputSize',
            'parameters': [{'$ref': '#/components/parameters/feedbackCategory'}],
            'responses': {
                '200': {
                    'description': '',
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'stdout_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'stdout_truncated': {
                                        'type': 'boolean',
                                        'nullable': True,
                                    },
                                    'stderr_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'stderr_truncated': {
                                        'type': 'boolean',
                                        'nullable': True,
                                    },
                                    'stdout_diff_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'stderr_diff_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    })

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        cmd_result_pk = self.kwargs['result_pk']
        cmd_fdbk = _find_ag_test_cmd_result(submission_fdbk, cmd_result_pk)
        if cmd_fdbk is None:
            return response.Response(None)
        return response.Response({
            'stdout_size': cmd_fdbk.get_stdout_size(),
            'stdout_truncated': cmd_fdbk.stdout_truncated,
            'stderr_size': cmd_fdbk.get_stderr_size(),
            'stderr_truncated': cmd_fdbk.stderr_truncated,
            'stdout_diff_size': cmd_fdbk.get_stdout_diff_size(),
            'stderr_diff_size': cmd_fdbk.get_stderr_diff_size(),
        })


def _get_cmd_result_output(
    submission_fdbk: SubmissionResultFeedback,
    cmd_result_pk: int,
    get_output_filename_fn: Callable[[AGTestCommandResultFeedback], Path | None]
) -> HttpResponse:
    cmd_fdbk = _find_ag_test_cmd_result(submission_fdbk, cmd_result_pk)
    if cmd_fdbk is None:
        return response.Response(None)
    path = get_output_filename_fn(cmd_fdbk)
    if path is None:
        return response.Response(None)
    return serve_file(path)


class _DiffViewSchema(CustomViewSchema):
    def __init__(self, operation_id: str):
        super().__init__([APITags.submission_output], {
            'GET': {
                'operation_id': operation_id,
                'parameters': [{'$ref': '#/components/parameters/feedbackCategory'}],
                'responses': {
                    '200': {
                        'description': '',
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'string',
                                    }
                                },
                                'examples': {
                                    'differencesFound': {
                                        'summary': 'Expected and actual output differ',
                                        'value': ['  spam', '+ egg', '- sausage']
                                    },
                                    'noDifference': {
                                        'summary': 'Expected and actual output match',
                                        'value': []
                                    }
                                }
                            },
                        }
                    }
                }
            }
        })


class AGTestCommandResultStdoutDiffView(SubmissionResultsViewBase):
    schema = _DiffViewSchema('getAGTestCommandResultStdoutDiff')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        cmd_result_pk = self.kwargs['result_pk']
        return _get_cmd_result_diff(
            submission_fdbk,
            cmd_result_pk,
            lambda fdbk_calc: fdbk_calc.stdout_diff)


class AGTestCommandResultStderrDiffView(SubmissionResultsViewBase):
    schema = _DiffViewSchema('getAGTestCommandResultStderrDiff')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        cmd_result_pk = self.kwargs['result_pk']
        return _get_cmd_result_diff(
            submission_fdbk,
            cmd_result_pk,
            lambda fdbk_calc: fdbk_calc.stderr_diff)


def _get_cmd_result_diff(
    submission_fdbk: SubmissionResultFeedback,
    cmd_result_pk: int,
    get_diff_fn: Callable[[AGTestCommandResultFeedback], core_ut.DiffResult | None]
) -> HttpResponse:
    cmd_fdbk = _find_ag_test_cmd_result(submission_fdbk, cmd_result_pk)
    if cmd_fdbk is None:
        return response.Response(None)

    diff = get_diff_fn(cmd_fdbk)
    if diff is None:
        return response.Response(None)

    return JsonResponse(diff.diff_content, safe=False)


def _find_ag_test_cmd_result(submission_fdbk: SubmissionResultFeedback,
                             cmd_result_pk: int) -> Optional[AGTestCommandResultFeedback]:
    """
    :raises: Http404 exception if a command result with the
             given primary key doesn't exist in the database.
    :return: The command result with the given primary key
             if it can be found in submission_fdbk, None otherwise.
    """
    queryset = ag_models.AGTestCommandResult.objects.select_related(
        'ag_test_case_result__ag_test_suite_result')
    cmd_result = get_object_or_404(queryset, pk=cmd_result_pk)

    for suite_fdbk in submission_fdbk.ag_test_suite_results:
        if suite_fdbk.pk != cmd_result.ag_test_case_result.ag_test_suite_result.pk:
            continue

        for case_fdbk in suite_fdbk.ag_test_case_results:
            if case_fdbk.pk != cmd_result.ag_test_case_result.pk:
                continue

            for cmd_fdbk in case_fdbk.ag_test_command_results:
                if cmd_fdbk.pk == cmd_result.pk:
                    return cmd_fdbk

    return None


class MutationTestSuiteResultSetupStdoutView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultSetupStdout')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.setup_stdout_filename)


class MutationTestSuiteResultSetupStderrView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultSetupStderr')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.setup_stderr_filename)


class MutationTestSuiteResultGetStudentTestsStdoutView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultTestDiscoveryStdout')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.get_student_test_names_stdout_filename)


class MutationTestSuiteResultGetStudentTestsStderrView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultTestDiscoveryStderr')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.get_student_test_names_stderr_filename)


class MutationTestSuiteResultValidityCheckStdoutView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultValidityCheckStdout')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.validity_check_stdout_filename)


class MutationTestSuiteResultValidityCheckStderrView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultValidityCheckStderr')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.validity_check_stderr_filename)


class MutationTestSuiteResultGradeBuggyImplsStdoutView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultGradeBuggyImplsStdout')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.grade_buggy_impls_stdout_filename)


class MutationTestSuiteResultGradeBuggyImplsStderrView(SubmissionResultsViewBase):
    schema = _OutputViewSchema('getMutationTestSuiteResultGradeBuggyImplsStderr')

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        return _get_mutation_suite_result_output_field(
            submission_fdbk,
            fdbk_category,
            mutation_suite_result_pk,
            lambda fdbk_calc: fdbk_calc.grade_buggy_impls_stderr_filename)


class MutationTestSuiteOutputSizeView(SubmissionResultsViewBase):
    schema = CustomViewSchema([APITags.submission_output], {
        'GET': {
            'operation_id': 'getMutationTestSuiteResultOutputSize',
            'parameters': [{'$ref': '#/components/parameters/feedbackCategory'}],
            'responses': {
                '200': {
                    'description': '',
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'setup_stdout_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'setup_stderr_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'get_student_test_names_stdout_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'get_student_test_names_stderr_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'validity_check_stdout_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'validity_check_stderr_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'grade_buggy_impls_stdout_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                    'grade_buggy_impls_stderr_size': {
                                        'type': 'integer',
                                        'nullable': True,
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    })

    def _make_response(self, submission_fdbk: SubmissionResultFeedback,
                       fdbk_category: ag_models.FeedbackCategory) -> HttpResponse:
        mutation_suite_result_pk = self.kwargs['result_pk']
        result = _find_mutation_suite_result(submission_fdbk, mutation_suite_result_pk)
        if result is None:
            return response.Response(None)

        return response.Response({
            'setup_stdout_size': result.get_setup_stdout_size(),
            'setup_stderr_size': result.get_setup_stderr_size(),
            'get_student_test_names_stdout_size': result.get_student_test_names_stdout_size(),
            'get_student_test_names_stderr_size': result.get_student_test_names_stderr_size(),
            'validity_check_stdout_size': result.get_validity_check_stdout_size(),
            'validity_check_stderr_size': result.get_validity_check_stderr_size(),
            'grade_buggy_impls_stdout_size': result.get_grade_buggy_impls_stdout_size(),
            'grade_buggy_impls_stderr_size': result.get_grade_buggy_impls_stderr_size(),
        })


GetMutationTestSuiteOutputFnType = Callable[
    [ag_models.MutationTestSuiteResult.FeedbackCalculator], Optional[BinaryIO]]


def _get_mutation_suite_result_output_field(
    submission_fdbk: SubmissionResultFeedback,
    fdbk_category: ag_models.FeedbackCategory,
    mutation_suite_result_pk: int,
    get_output_filename_fn: Callable[
        [ag_models.MutationTestSuiteResult.FeedbackCalculator], Path | None
    ]
) -> HttpResponse:
    result = _find_mutation_suite_result(submission_fdbk, mutation_suite_result_pk)
    if result is None:
        return response.Response(None)

    path = get_output_filename_fn(result)
    if path is None:
        return response.Response(None)

    return serve_file(path)


def _find_mutation_suite_result(
    submission_fdbk: SubmissionResultFeedback,
    mutation_suite_result_pk: int
) -> Optional[ag_models.MutationTestSuiteResult.FeedbackCalculator]:
    """
    :raises: Http404 exception if a mutation suite result with the given primary
             key doesn't exist in the database.

    :return: The mutation suite result with the given primary key
             if it can be found in submission_fdbk, None otherwise.
    """
    mutation_suite_result = get_object_or_404(
        ag_models.MutationTestSuiteResult.objects.all(),
        pk=mutation_suite_result_pk)

    for result in submission_fdbk.mutation_test_suite_results:
        if result.pk == mutation_suite_result.pk:
            return result

    return None
