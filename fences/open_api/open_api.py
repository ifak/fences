from typing import Any, Optional, List, Dict, Set, Any, Type
from typing_extensions import Self

from dataclasses import dataclass, field
from enum import Enum
import warnings

from .resolver import Resolver
from .exceptions import OpenApiException

show_warnings = False


class NoDefault:
    pass


def assert_type(value: Any, _type: Type, json_path: str):
    if not isinstance(value, _type):
        raise OpenApiException('Expected "{}", got "{}" at {}'.format(_type, type(value), json_path))
    return value


def safe_dict_lookup(data: dict, key: str, _type: Type, json_path: str, default=NoDefault):
    if key not in data:
        if default is not NoDefault:
            return default
        else:
            raise OpenApiException('Expected key "{}" at {}'.format(key, json_path))
    return assert_type(data[key], _type, json_path + '.' + key)


@dataclass
class Info:
    title: str

    @classmethod
    def from_dict(self, data: Any, json_path: str) -> Self:
        return Info(
            title=safe_dict_lookup(data, 'title', str, json_path)
        )


class ParameterPosition(Enum):
    QUERY = "query"
    HEADER = "header"
    PATH = "path"
    COOKIE = "cookie"


class ParameterStyle(Enum):
    FORM = "form"
    SIMPLE = "simple"


@dataclass
class Parameter:
    name: str
    position: ParameterPosition
    required: bool
    style: ParameterStyle
    explode: bool
    schema: dict

    @classmethod
    def from_dict(self, components: Any, data: Any, json_path: str) -> Self:
        pos = ParameterPosition(safe_dict_lookup(data, 'in', str, json_path))
        schema = safe_dict_lookup(data, 'schema', dict, json_path)
        schema['components'] = components
        return Parameter(
            name=safe_dict_lookup(data, 'name', str, json_path),
            position=pos,
            required=safe_dict_lookup(data, "required", bool, json_path, pos == ParameterPosition.PATH),
            style=ParameterStyle(safe_dict_lookup(data, 'style', str, json_path, ParameterStyle.SIMPLE.value)),
            explode=safe_dict_lookup(data, 'explode', bool, json_path, False),
            schema=schema
        )


@dataclass
class RequestBody:
    description: str
    schema: Optional[Dict]
    required: bool

    @classmethod
    def from_dict(self, components: Any, data: Any, json_path: str) -> Self:
        assert_type(data, dict, json_path)
        content = safe_dict_lookup(data, 'content', dict, json_path)
        json_content_type = 'application/json'
        if len(content.keys()) != 1:
            if show_warnings:
                warnings.warn(f"Ignoring some content types at {json_path}")
        if json_content_type not in content.keys():
            if show_warnings:
                warnings.warn(f"Support for non-json request bodies not implemented, at {json_path}")
            json_content = {}
        else:
            json_content = safe_dict_lookup(content, json_content_type, dict, json_path)
        schema=safe_dict_lookup(json_content, 'schema', dict, json_path, {})
        schema['components'] = components
        return RequestBody(
            description=safe_dict_lookup(data, 'description', str, json_path, ''),
            required=safe_dict_lookup(data, 'required', bool, json_path, True),
            schema=schema,
        )


@dataclass
class Response:
    code: Optional[int]
    schema: Optional[Dict]

    @classmethod
    def from_dict(self, components: Any, code: str, data: Any, json_path) -> Self:
        content = safe_dict_lookup(data, 'content', dict, json_path, None)
        schema = None
        if content is not None:
            json_content_type = 'application/json'
            if len(content.keys()) != 1:
                if show_warnings:
                    warnings.warn(f"Ignoring some content types at {json_path}")
            if json_content_type not in content.keys():
                if show_warnings:
                    warnings.warn(f"Support for non-json request bodies not implemented, at {json_path}")
                json_content = {}
            else:
                json_content = safe_dict_lookup(content, json_content_type, dict, json_path)
            schema = safe_dict_lookup(json_content, 'schema', dict, json_path, None)
            if isinstance(schema, dict):
                schema['components'] = components

        return Response(
            code=None if code == 'default' else int(code),
            schema=schema,
        )


@dataclass
class Operation:
    path: str
    operation_id: str
    summary: str
    method: str
    parameters: List[Parameter]
    request_body: Optional[RequestBody]
    responses: List[Response]
    tags: Set[str]

    @classmethod
    def from_dict(self, components: dict, path: str, method: str, data: Any, json_path: str) -> Self:
        assert_type(data, dict, json_path)

        request_body = safe_dict_lookup(data, 'requestBody', dict, json_path, None)
        parameters=[
            Parameter.from_dict(components, i, json_path + '.parameters.' + str(idx))
            for idx, i in enumerate(safe_dict_lookup(data, 'parameters', list, json_path, []))
        ]
        for param in parameters:
            if any(i.name == param.name and i.position == param.position for i in parameters if i is not param):
                raise OpenApiException(f"Parameter {param.name} not unique for position {param.position.value} ({json_path})")

        return Operation(
            path=path,
            operation_id=safe_dict_lookup(data, 'operationId', str, json_path),
            summary=safe_dict_lookup(data, 'summary', str, json_path, ''),
            method=method,
            parameters=parameters,
            request_body=RequestBody.from_dict(components, request_body, json_path + '.' + 'requestBody') if request_body is not None else None,
            responses=[
                Response.from_dict(components, k, v, json_path + '.' + k)
                for k, v in safe_dict_lookup(data, 'responses', dict, json_path).items()
            ],
            tags=set(safe_dict_lookup(data, 'tags', list, json_path, []))
        )


@dataclass
class Path:
    path: str
    operations: List[Operation]

    @classmethod
    def from_dict(self, path_name: str, data: Any, json_path: str, resolver: Resolver) -> Self:
        assert_type(data, dict, json_path)
        operations: List[Operation] = []
        for k, v in assert_type(data, dict, json_path).items():
            operations.append(Operation.from_dict(k, v, json_path + '.' + k, resolver))
        return Path(
            path=path_name,
            operations=operations
        )


@dataclass
class OpenApi:
    info: Info
    operations: Dict[str, Operation] = field(default_factory=dict)

    @classmethod
    def from_dict(self, data: Any) -> Self:
        assert_type(data, dict, '')
        components=safe_dict_lookup(data, 'components', dict, '/', {})
        api = OpenApi(
            info=Info.from_dict(safe_dict_lookup(data, 'info', dict, '/'), 'info'),
        )
        for path_name, path_info in safe_dict_lookup(data, 'paths', dict, '/').items():
            for method, op_info in path_info.items():
                op = Operation.from_dict(components, path_name, method, op_info, f'/{path_name}/{method}')
                api.operations[op.operation_id] = op
        return api
