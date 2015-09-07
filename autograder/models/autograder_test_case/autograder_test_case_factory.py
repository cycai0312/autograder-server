from .compiled_autograder_test_case import CompiledAutograderTestCase
from .compilation_only_autograder_test_case import CompilationOnlyAutograderTestCase


class AutograderTestCaseFactory(object):
    def new_instance(type_str, **kwargs):
        return _get_class(type_str)(**kwargs)

    def validate_and_create(type_str, **kwargs):
        return _get_class(type_str).objects.validate_and_create(**kwargs)


def _get_class(type_str):
    try:
        return _STR_TO_CLASS_MAPPINGS[type_str]
    except KeyError:
        raise ValueError("Invalid test case type: '{}'".format(type_str))

_STR_TO_CLASS_MAPPINGS = {
    'compiled_test_case': CompiledAutograderTestCase,
    'compilation_only_test_case': CompilationOnlyAutograderTestCase
}