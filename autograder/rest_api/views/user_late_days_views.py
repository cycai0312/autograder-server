from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework import response
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.views import APIView

import autograder.core.models as ag_models
from autograder.rest_api.schema import (
    APITags, CustomViewSchema, ParameterObject, as_content_obj)
from autograder.rest_api.schema.openapi_types import ResponseObject, OrRef, RequestBodyObject
from autograder.rest_api.schema.view_schema_generators import AGListCreateViewSchemaGenerator
from autograder.rest_api.views.ag_model_views import (
    AlwaysIsAuthenticatedMixin, require_body_params)


class ListLateDaysForUserView(AlwaysIsAuthenticatedMixin, APIView):
    schema = AGListCreateViewSchemaGenerator(
        [APITags.users, APITags.courses], ag_models.LateDaysForUser)

    def get(self, request: Request, *args, **kwargs):
        course = get_object_or_404(ag_models.Course.objects, pk=kwargs['pk'])
        self._check_read_permissions(course)
        late_days_for_users = [
            item.to_dict() for item in ag_models.LateDaysForUser.get_all(course)
        ]
        return response.Response(late_days_for_users)

    def _check_read_permissions(self, course: ag_models.Course):
        if not course.is_admin(self.request.user):
            raise PermissionDenied


class LateDaysView(AlwaysIsAuthenticatedMixin, APIView):
    _RESPONSE: ResponseObject = {
        'content': as_content_obj(ag_models.LateDaysForUser),
        'description': ''
    }
    _REQUEST: RequestBodyObject = {
        'content': {
            'application/json': {
                'schema': {
                    'type': 'object',
                    'required': ['extra_late_days_granted'],
                    'properties': {
                        'extra_late_days_granted': {
                            'type': 'integer',
                        },
                    }
                }
            }
        },
        'description': """
`extra_late_days_granted` + the number of late days set for the project must be greater than or
equal to `late_days_used`.

**Note:** the `late_days_used` field is a property computed from submission data and can't be
changed."""
    }

    _PARAMS: list[OrRef[ParameterObject]] = [
        {
            'name': 'pk',
            'in': 'path',
            'required': True,
            'schema': {'type': 'integer', 'format': 'id'}
        },
        {
            'name': 'username_or_pk',
            'in': 'path',
            'required': True,
            'description': 'The ID or username of the user.',
            'schema': {
                # Note: swagger-ui doesn't seem to be able to render
                # oneOf for params.
                'oneOf': [
                    {'type': 'string', 'format': 'username'},
                    {'type': 'integer', 'format': 'id'},
                ]
            }
        }
    ]

    schema = CustomViewSchema([APITags.courses, APITags.users], {
        'GET': {
            'operation_id': 'getLateDays',
            'parameters': _PARAMS,
            'responses': {
                '200': _RESPONSE
            }
        },
        'PUT': {
            'operation_id': 'putExtraLateDays',
            'parameters': _PARAMS,
            'request': _REQUEST,
            'responses': {
                '200': _RESPONSE
            }
        },
    })

    def get(self, request: Request, *args, **kwargs):
        try:
            user = get_object_or_404(User.objects, pk=int(kwargs['username_or_pk']))
        except ValueError:
            user = get_object_or_404(User.objects, username=kwargs['username_or_pk'])

        course = get_object_or_404(ag_models.Course.objects, pk=kwargs['pk'])

        self._check_read_permissions(user, course)
        late_days = ag_models.LateDaysForUser.get(user, course)

        return response.Response(late_days.to_dict())

    @method_decorator(require_body_params('extra_late_days'))
    def put(self, request: Request, *args, **kwargs):
        try:
            user = get_object_or_404(User.objects, pk=int(kwargs['username_or_pk']))
        except ValueError:
            user = get_object_or_404(User.objects, username=kwargs['username_or_pk'])

        course = get_object_or_404(ag_models.Course.objects, pk=int(kwargs['pk']))

        self._check_read_permissions(user, course)
        self._check_write_permissions(user, course)

        with transaction.atomic():
            extra_late_days = ag_models.ExtraLateDays.objects.get_or_create(
                user=user, course=course
            )[0]
            extra_late_days.extra_late_days = request.data['extra_late_days']
            extra_late_days.save()
            late_days = ag_models.LateDaysForUser.get(user, course)

            return response.Response(late_days.to_dict())

    def _check_read_permissions(self, requestee: User, course: ag_models.Course):
        user = self.request.user
        if user == requestee:
            return

        if course.is_staff(user):
            return

        raise PermissionDenied

    def _check_write_permissions(self, requestee: User, course: ag_models.Course):
        if not course.is_admin(self.request.user):
            raise PermissionDenied
