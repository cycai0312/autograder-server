from django.db import transaction

from rest_framework import viewsets, mixins, permissions

import autograder.core.models as ag_models
import autograder.rest_api.serializers as ag_serializers

from autograder.rest_api.views.project_views.permissions import ProjectPermissions
from autograder.rest_api.views.load_object_mixin import build_load_object_mixin


class ExpectedStudentFilePatternsViewSet(
        build_load_object_mixin(ag_models.Project),
        mixins.CreateModelMixin,
        mixins.ListModelMixin,
        viewsets.GenericViewSet):
    serializer_class = ag_serializers.ExpectedStudentFilePatternSerializer
    permission_classes = (permissions.IsAuthenticated, ProjectPermissions)

    def get_queryset(self):
        project = self.load_object(self.kwargs['project_pk'])
        return project.expected_student_file_patterns.all()

    @transaction.atomic()
    def create(self, request, project_pk, *args, **kwargs):
        request.data['project'] = self.load_object(project_pk)
        return super().create(request, *args, **kwargs)