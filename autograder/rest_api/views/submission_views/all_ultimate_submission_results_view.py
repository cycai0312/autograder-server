import itertools

from rest_framework.pagination import PageNumberPagination

from autograder.core.models.get_ultimate_submissions import get_ultimate_submissions
from autograder.rest_api.views.ag_model_views import AGModelAPIView
import autograder.rest_api.permissions as ag_permissions
import autograder.core.models as ag_models
from autograder.rest_api.views.schema_generation import APITags

from autograder import utils


class UltimateSubmissionPaginator(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'groups_per_page'
    max_page_size = 200


class AllUltimateSubmissionResults(AGModelAPIView):
    permission_classes = (ag_permissions.is_admin(),)
    model_manager = ag_models.Project
    pk_key = 'project_pk'

    api_tags = (APITags.submissions,)

    def get(self, *args, **kwargs):
        project: ag_models.Project = self.get_object()

        include_staff = self.request.query_params.get('include_staff', 'true') == 'true'
        if include_staff:
            groups = project.groups.all()
        else:
            staff = list(
                itertools.chain(project.course.staff.all(),
                                project.course.admins.all())
            )
            groups = project.groups.exclude(members__in=staff)

        full_results = self.request.query_params.get('full_results') == 'true'

        paginator = UltimateSubmissionPaginator()
        page = paginator.paginate_queryset(queryset=groups, request=self.request, view=self)
        print(page)

        ultimate_submissions = get_ultimate_submissions(project, *page)

        results = []
        for submission in ultimate_submissions:
            submission_data = submission.to_dict()
            submission_results = submission.get_fdbk(ag_models.FeedbackCategory.max).to_dict()
            if not full_results:
                submission_results = utils.filter_dict(
                    submission_results, ['total_points', 'total_points_possible'])

            submission_data['results'] = submission_results
            group_data = submission.group.to_dict()

            for username in submission.group.member_names:
                user_data = {
                    'username': username,
                    'group': group_data,
                    'ultimate_submission': submission_data
                }
                results.append(user_data)

        return paginator.get_paginated_response(results)
