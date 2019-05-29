from django.core.cache import cache

import autograder.core.models as ag_models
from autograder.core.submission_feedback import SubmissionResultFeedback


def clear_submission_results_cache(project_pk: int) -> None:
    keys = cache.client.iter_keys(f'project_{project_pk}_submission_normal_results_*',
                                  itersize=5000)
    cache.delete_many(list(keys))


def delete_cached_submission_result(submission: ag_models.Submission) -> None:
    cache_key = 'project_{}_submission_normal_results_{}'.format(
        submission.group.project.pk, submission.pk)
    cache.delete(cache_key)


def get_cached_submission_feedback(submission: ag_models.Submission,
                                   feedback: SubmissionResultFeedback) -> dict:
    """
    Loads the serialized normal feedback for the given submission from
    the cache and returns it.
    If the serialized feedback is not cached, adds it to the cache
    before returning it.
    """
    cache_key = 'project_{}_submission_normal_results_{}'.format(
        submission.group.project.pk,
        submission.pk)

    result = cache.get(cache_key)
    if result is None:
        result = feedback.to_dict()
        cache.set(cache_key, result, timeout=None)

    return result
