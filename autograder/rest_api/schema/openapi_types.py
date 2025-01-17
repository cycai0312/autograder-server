from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Literal, TypedDict, TypeVar, Union

from typing_extensions import Required

if TYPE_CHECKING:
    from rest_framework.schemas.openapi import DRFOpenAPIInfo

# NOTE on imports: This module should NOT import from any of the other
# modules in the schema package.

# Where appropriate, types are defined from the OpenAPI 3 spec:
# https://github.com/OAI/OpenAPI-Specification/blob/master/versions/3.0.2.md
# These types are not exhaustive and may need to be added to to enable
# additional OpenAPI features.

# Placeholder for types we haven't needed yet.
FIXME_TYPE = Dict[str, object]

HTTPMethodName = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']


class _OpenAPIObjectRequired(TypedDict):
    openapi: str
    info: DRFOpenAPIInfo
    paths: Dict[str, PathItemObject]


class OpenAPIObject(_OpenAPIObjectRequired, total=False):
    servers: FIXME_TYPE
    components: ComponentsObject
    security: FIXME_TYPE
    tags: List[TagObject]
    externalDocs: FIXME_TYPE


class PathItemObject(TypedDict, total=False):
    summary: str
    description: str
    get: OperationObject
    put: OperationObject
    post: OperationObject
    delete: OperationObject
    options: OperationObject
    head: OperationObject
    patch: OperationObject
    trace: OperationObject
    parameters: OrRef[ParameterObject]
    servers: FIXME_TYPE


class OperationObject(TypedDict, total=False):
    responses: Required[Dict[str, OrRef[ResponseObject]]]
    tags: List[str]
    summary: str
    description: str
    operationId: str
    parameters: List[OrRef[ParameterObject]]
    requestBody: OrRef[RequestBodyObject]
    deprecated: bool
    externalDocs: FIXME_TYPE
    callbacks: FIXME_TYPE
    security: FIXME_TYPE
    servers: FIXME_TYPE


class ComponentsObject(TypedDict, total=False):
    schemas: Dict[str, OrRef[SchemaObject]]
    responses: Dict[str, OrRef[ResponseObject]]
    parameters: Dict[str, OrRef[ParameterObject]]
    examples: Dict[str, OrRef[ExampleObject]]
    requestBodies: Dict[str, OrRef[FIXME_TYPE]]
    headers: Dict[str, OrRef[FIXME_TYPE]]
    securitySchemes: Dict[str, OrRef[FIXME_TYPE]]
    links: Dict[str, OrRef[FIXME_TYPE]]
    callbacks: Dict[str, OrRef[FIXME_TYPE]]


class SchemaObject(TypedDict, total=False):
    description: str
    type: str
    format: str
    required: List[str]  # List of required field names
    nullable: bool
    readOnly: bool
    enum: List[str]
    default: object
    maximum: Union[int, float]

    items: OrRef[SchemaObject]
    properties: Dict[str, OrRef[SchemaObject]]
    anyOf: List[OrRef[SchemaObject]]
    allOf: List[OrRef[SchemaObject]]
    oneOf: List[OrRef[SchemaObject]]


ReferenceObject = TypedDict('ReferenceObject', {'$ref': str})
_R = TypeVar('_R')
OrRef = Union[_R, ReferenceObject]


class _ResponseObjectRequired(TypedDict):
    description: str


class ResponseObject(_ResponseObjectRequired, total=False):
    headers: Dict[str, OrRef[FIXME_TYPE]]
    content: Dict[ContentType, MediaTypeObject]
    links: Dict[str, OrRef[FIXME_TYPE]]


_ParameterObjectRequired = TypedDict('_ParameterObjectRequired', {
    'name': str,
    'in': str,
})


class ParameterObject(_ParameterObjectRequired, total=False):
    # Only required when "in" is "path". See OpenAPI spec.
    required: bool
    schema: OrRef[SchemaObject]
    description: str
    deprecated: bool
    allowEmptyValue: bool


class ExampleObject(TypedDict, total=False):
    summary: str
    description: str
    value: object
    externalValue: str


class RequestBodyObject(TypedDict, total=False):
    content: Required[Dict[ContentType, MediaTypeObject]]
    description: str
    required: bool


ContentType = Literal[
    'application/json',
    'multipart/form-data',
    'application/octet-stream',
    'application/zip',
]


class MediaTypeObject(TypedDict, total=False):
    schema: OrRef[SchemaObject]
    example: object
    examples: Dict[str, OrRef[ExampleObject]]
    encoding: FIXME_TYPE


class _TagObjectRequired(TypedDict):
    name: str


class TagObject(_TagObjectRequired, total=False):
    description: str
    externalDocs: FIXME_TYPE
