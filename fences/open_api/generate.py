from typing import List, Dict, Optional

from .open_api import OpenApi, Operation, ParameterPosition, Parameter
from fences.json_schema.parse import parse as parse_json_schema
from fences.core.node import Node, NoOpDecision, Decision, Leaf

from dataclasses import dataclass, field
from urllib.parse import urlencode
import json


@dataclass
class Request:
    path: str
    method: str
    headers: Dict[str, str]
    body: Optional[str]


@dataclass
class TestCase:
    path: str
    operation: Operation
    body: Optional[str] = None
    query_parameters: Dict[str, any] = field(default_factory=dict)
    path_parameters: Dict[str, any] = field(default_factory=dict)
    headers: Dict[str, any] = field(default_factory=dict)
    cookies: Dict[str, any] = field(default_factory=dict)

    def to_request(self) -> Request:
        path = self.path
        for key, value in self.path_parameters.items():
            path = path.replace('{' + key + '}', value)
        if self.query_parameters:
            path += "?" + urlencode(self.query_parameters)
        return Request(
            path=path,
            method=self.operation.method,
            # TODO: content type should not be hardcoded
            headers={**self.headers, 'content-type': 'application/json'},
            body=self.body,
        )


class StartTestCase(Decision):
    def __init__(self, path: str, operation: Operation) -> None:
        super().__init__(operation.operation_id, True)
        self.test_request = TestCase(path, operation)

    def apply(self, data: any) -> any:
        return self.test_request


class InsertParamLeaf(Leaf):
    def __init__(self, is_valid: bool, position: ParameterPosition, name: str, value: any) -> None:
        super().__init__(None, is_valid)
        self.position = position
        self.name = name
        self.value = value

    def description(self) -> str:
        return f"Insert {self.name} = {self.value} into {self.position.name}"


class InsertQueryParamLeaf(InsertParamLeaf):
    def apply(self, data: TestCase) -> any:
        data.query_parameters[self.name] = self.value
        return data


class InsertPathParamLeaf(InsertParamLeaf):
    def apply(self, data: TestCase) -> any:
        data.path_parameters[self.name] = self.value
        return data


class InsertHeaderLeaf(InsertParamLeaf):
    def apply(self, data: TestCase) -> any:
        data.headers[self.name] = self.value
        return data


class InsertCookieLeaf(InsertParamLeaf):
    def apply(self, data: TestCase) -> any:
        data.cookies[self.name] = self.value
        return data


class InsertBodyLeaf(Leaf):
    def __init__(self, is_valid: bool, body: str) -> None:
        super().__init__(None, is_valid)
        self.body = body

    def apply(self, data: TestCase) -> any:
        data.body = self.body
        return data

    def description(self) -> str:
        return "Add body"


class SampleDatabase:

    def __init__(self) -> None:
        self.samples: Dict[str, Node] = {}

    def _to_key(self, param: Parameter) -> str:
        return param.position.value + json.dumps(param.schema)

    def add(self, parameter: Parameter, components: Dict[str, any]):
        key = self._to_key(parameter)
        if key in self.samples:
            return
        node_class = {
            ParameterPosition.PATH: InsertPathParamLeaf,
            ParameterPosition.QUERY: InsertQueryParamLeaf,
            ParameterPosition.HEADER: InsertHeaderLeaf,
            ParameterPosition.COOKIE: InsertCookieLeaf,
        }[parameter.position]

        composite_schema = {
            **parameter.schema,
            'components': components
        }
        graph = parse_json_schema(composite_schema)
        root = NoOpDecision()
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if isinstance(sample, (str, int, float)) and not isinstance(sample, bool):
                node = node_class(i.is_valid, parameter.position, parameter.name, str(sample))
                root.add_transition(node)
            if len(root.outgoing_transitions) > 100:
                break
        if not root.outgoing_transitions:
            raise Exception(f"Parameter {parameter.name} has no string instances")
        self.samples[key] = root

    def get(self, parameter: Parameter) -> Node:
        return self.samples[self._to_key(parameter)]


def parse(open_api: any) -> Node:
    openapi: OpenApi = OpenApi.from_dict(open_api)
    super_root = NoOpDecision()

    # collect all parameters
    sample_db = SampleDatabase()
    for path in openapi.paths:
        for operation in path.operations:
            for param in operation.parameters:
                sample_db.add(param, openapi.components)

    # Create graph
    for path in openapi.paths:
        for operation in path.operations:
            root = StartTestCase(path.path, operation)
            for param in operation.parameters:
                samples = sample_db.get(param)
                root.add_transition(samples)
            if operation.request_body:
                root.add_transition(InsertBodyLeaf(True, operation.request_body.schema))
            super_root.add_transition(root)
    return super_root
