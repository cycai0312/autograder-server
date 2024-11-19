from typing import Dict, List, Sequence

from django.core.serializers import serialize
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework import permissions, response, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.views import APIView

import autograder.core.models as ag_models
from autograder.rest_api.schema import (
    AGDetailViewSchemaGenerator, APIClassType, APITags, ContentType, CustomViewSchema,
    ParameterObject, as_array_content_obj, as_content_obj
)
from autograder.rest_api.schema.openapi_types import SchemaObject, ResponseObject, OrRef, RequestBodyObject
from autograder.rest_api.schema.utils import stderr
from autograder.rest_api.schema.view_schema_generators import AGViewSchemaGenerator
from autograder.rest_api.serialize_user import serialize_user
from autograder.rest_api.views.ag_model_views import (
    AGModelAPIView, AGModelDetailView, AlwaysIsAuthenticatedMixin, NestedModelView,
    require_body_params, require_query_params
)


class _Permissions(permissions.BasePermission):
    def has_permission(self, *args, **kwargs):
        return True

    def has_object_permission(self, request, view, obj):
        return view.kwargs['pk'] == request.user.pk


class CurrentUserView(AGModelAPIView):
    schema = AGDetailViewSchemaGenerator(
        tags=[APITags.users],
        api_class=User,
        operation_id_overrides={'GET': 'getCurrentUser'}
    )

    def get(self, *args, **kwargs):
        return response.Response(serialize_user(self.request.user))


class RevokeCurrentUserAPITokenView(AGModelAPIView):
    schema = AGViewSchemaGenerator(
        tags=[APITags.users],
        operation_id_overrides={'DELETE': 'revokeCurrentUserAPIToken'}
    )

    def delete(self, *args, **kwargs):
        """
        Revoke the current user's API token.
        """
        # Note: In order for this request to be processed,
        # the user must be authenticated, which means they must
        # have an API token. Therefore we do not need to handle any
        # ObjectDoesNotExist exceptions.
        token = Token.objects.get(user=self.request.user)
        token.delete()
        return response.Response(status=status.HTTP_204_NO_CONTENT)


class UserDetailView(AGModelDetailView):
    schema = AGDetailViewSchemaGenerator(tags=[APITags.users])
    permission_classes = [_Permissions]
    model_manager = User.objects

    def get(self, *args, **kwargs):
        return self.do_get()

    def serialize_object(self, obj):
        return serialize_user(obj)


# For objects related to the user,
# e.g. Courses is student in, Groups is member of.
class _UserEntityListViewSchema(CustomViewSchema):
    def __init__(self, tags: List[APITags], operation_id: str, api_class: APIClassType):
        super().__init__(tags, {
            'GET': {
                'operation_id': operation_id,
                'responses': {
                    '200': {
                        'content': as_array_content_obj(api_class),
                        'description': ''
                    }
                }
            }
        })


class _UserCoursesViewSchema(_UserEntityListViewSchema):
    def __init__(self, operation_id):
        super().__init__([APITags.users, APITags.courses], operation_id, ag_models.Course)


class _UserCoursesViewBase(NestedModelView):
    model_manager = User.objects

    permission_classes = [_Permissions]

    def get(self, *args, **kwargs):
        return self.do_list()


class CoursesIsAdminForView(_UserCoursesViewBase):
    schema = _UserCoursesViewSchema('coursesIsAdminFor')
    nested_field_name = 'courses_is_admin_for'


class CoursesIsStaffForView(_UserCoursesViewBase):
    schema = _UserCoursesViewSchema('coursesIsStaffFor')
    nested_field_name = 'courses_is_staff_for'


class CoursesIsEnrolledInView(_UserCoursesViewBase):
    schema = _UserCoursesViewSchema('coursesIsEnrolledIn')
    nested_field_name = 'courses_is_enrolled_in'


class CoursesIsHandgraderForView(_UserCoursesViewBase):
    schema = _UserCoursesViewSchema('coursesIsHandgraderFor')
    nested_field_name = 'courses_is_handgrader_for'


class GroupsIsMemberOfView(NestedModelView):
    schema = _UserEntityListViewSchema(
        [APITags.users, APITags.groups], 'groupsIsMemberOf', ag_models.Group
    )

    model_manager = User.objects
    nested_field_name = 'groups_is_member_of'

    permission_classes = [_Permissions]

    def get(self, *args, **kwargs):
        return self.do_list()


class _InvitationViewBase(NestedModelView):
    model_manager = User.objects

    permission_classes = [_Permissions]

    def get(self, *args, **kwargs):
        return self.do_list()


class GroupInvitationsSentView(_InvitationViewBase):
    schema = _UserEntityListViewSchema(
        [APITags.users, APITags.groups], 'groupInvitationsSent', ag_models.GroupInvitation
    )

    nested_field_name = 'group_invitations_sent'


class GroupInvitationsReceivedView(_InvitationViewBase):
    schema = _UserEntityListViewSchema(
        [APITags.users, APITags.groups], 'groupInvitationsReceived', ag_models.GroupInvitation
    )

    nested_field_name = 'group_invitations_received'


class CurrentUserCanCreateCoursesView(AlwaysIsAuthenticatedMixin, APIView):
    schema = CustomViewSchema([APITags.users], {
        'GET': {
            'operation_id': 'currentUserCanCreateCourses',
            'responses': {
                '200': {
                    'content': {
                        'application/json': {
                            'schema': {'type': 'boolean'}
                        }
                    },
                    'description': ''
                }
            }
        }
    })

    def get(self, request: Request, *args, **kwargs):
        """
        Indicates whether the current user can create empty courses.
        """
        return response.Response(request.user.has_perm('core.create_course'))
