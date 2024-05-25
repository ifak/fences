from typing import List, Dict, Optional, Tuple

from .open_api import OpenApi, Operation, ParameterPosition, Parameter
from .format import format_parameter_value

from fences.json_schema import parse as json_schema
from fences.json_schema.normalize import normalize as normalize_schema
from fences.core.node import Node, NoOpDecision, Decision, Leaf, NoOpLeaf

from dataclasses import dataclass, field
from urllib.parse import urlencode
import json


ListOfPairs = List[Tuple[any, any]]


@dataclass
class Request:
    path: str
    method: str
    headers: ListOfPairs
    body: Optional[str]

    def dump(self, body_max_chars=80):
        print(f"{self.method.upper()} {self.path}")
        if self.body:
            if len(self.body) > body_max_chars:
                b = self.body[:body_max_chars] + '...'
            else:
                b = self.body
            print(f"  BODY: {b}")


@dataclass
class TestCase:
    path: str
    operation: Operation
    body: Optional[str] = None
    query_parameters: ListOfPairs = field(default_factory=list)
    path_parameters: ListOfPairs = field(default_factory=list)
    headers: ListOfPairs = field(default_factory=list)
    cookies: ListOfPairs = field(default_factory=list)

    def to_request(self) -> Request:
        path = self.path
        for key, value in self.path_parameters:
            path = path.replace('{' + key + '}', value)
        if self.query_parameters:
            path += "?" + urlencode(self.query_parameters)
        headers: ListOfPairs = self.headers.copy()
        # TODO: content type should not be hardcoded
        headers.append(('content-type', 'application/json'))
        return Request(
            path=path,
            method=self.operation.method,
            headers=headers,
            body=self.body,
        )


class StartTestCase(Decision):
    def __init__(self, path: str, operation: Operation) -> None:
        super().__init__(operation.operation_id, True)
        self.operation = operation
        self.path = path

    def apply(self, data: any) -> any:
        return TestCase(self.path, self.operation)


class InsertParamLeaf(Leaf):
    def __init__(self, is_valid: bool, parameter: Parameter, value: any) -> None:
        super().__init__(None, is_valid)
        self.parameter = parameter
        self.value = value
        self.formatted_value = format_parameter_value(parameter, value)

    def description(self) -> str:
        return f"Insert {self.parameter.name} = {self.value} into {self.parameter.position.name}"

    def apply(self, data: TestCase) -> any:
        storage: ListOfPairs = {
            ParameterPosition.QUERY: data.query_parameters,
            ParameterPosition.HEADER: data.headers,
            ParameterPosition.PATH: data.path_parameters,
            ParameterPosition.COOKIE: data.cookies,
        }[self.parameter.position]
        storage.extend(self.formatted_value)
        return data


class InsertBodyLeaf(Leaf):
    def __init__(self, is_valid: bool, body: str) -> None:
        super().__init__(None, is_valid)
        self.body = body

    def apply(self, data: TestCase) -> any:
        data.body = self.body
        return data

    def description(self) -> str:
        return f"Set body = {self.body}"


@dataclass
class Samples:
    valid: List[any] = field(default_factory=list)
    invalid: List[any] = field(default_factory=list)


class SampleCache:

    def __init__(self) -> None:
        self.samples: Dict[str, Samples] = {}

    def _to_key(self, schema: any) -> str:
        return json.dumps(schema)

    def add(self, schema: any, components: Dict[str, any]) -> Samples:
        key = self._to_key(schema)
        if key in self.samples:
            return self.samples[key]

        composite_schema = {
            'components': components,
            'minLength': 1,
            **schema,
        }
        composite_schema = normalize_schema(composite_schema, False)
        config = json_schema.default_config()
        config.normalize = False
        graph = json_schema.parse(composite_schema, config)
        samples = Samples()
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if isinstance(sample, (str, int, float)) and not isinstance(sample, bool):
                if i.is_valid:
                    samples.valid.append(sample)
                else:
                    samples.invalid.append(sample)
            if len(samples.valid) + len(samples.invalid) > 20:
                break
        if not samples.valid and not samples.invalid:
            raise Exception(f"Schema has no string instances")
        self.samples[key] = samples
        return samples


def parse(open_api: any) -> Node:
    openapi: OpenApi = OpenApi.from_dict(open_api)
    super_root = NoOpDecision()
    sample_cache = SampleCache()

    # Create graph
    for path in openapi.paths:
        for operation in path.operations:
            root = StartTestCase(path.path, operation)
            for param in operation.parameters:
                param_root = NoOpDecision(f"{operation.operation_id}/{param.name}")
                samples = sample_cache.add(param.schema, openapi.components)
                for sample in samples.valid:
                    param_root.add_transition(InsertParamLeaf(True, param, sample))
                for sample in samples.invalid:
                    param_root.add_transition(InsertParamLeaf(False, param, sample))
                if param.position != ParameterPosition.PATH:
                    param_root.add_transition(NoOpLeaf(is_valid=not param.required))
                root.add_transition(param_root)
            if operation.request_body:
                body_root = NoOpDecision('BODY')
                bodies = sample_cache.add(operation.request_body.schema, openapi.components)
                for body in bodies.valid:
                    body_root.add_transition(InsertBodyLeaf(True, body))
                for body in bodies.invalid:
                    body_root.add_transition(InsertBodyLeaf(False, body))
                body_root.add_transition(NoOpLeaf(is_valid=not operation.request_body.required))
                root.add_transition(body_root)
            super_root.add_transition(root)
    return super_root
