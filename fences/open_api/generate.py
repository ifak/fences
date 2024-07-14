from typing import List, Dict, Optional, Tuple, TYPE_CHECKING, Union

from .open_api import OpenApi, Operation, ParameterPosition, Parameter
from .format import format_parameter_value
from .exceptions import MissingDependencyException

from fences.json_schema import parse as json_schema
from fences.json_schema.normalize import normalize as normalize_schema
from fences.core.node import Node, NoOpDecision, Decision, Leaf, NoOpLeaf

from dataclasses import dataclass, field
from urllib.parse import urlencode
import json
from enum import IntEnum, auto

if TYPE_CHECKING:
    import requests  # optional dependency

ListOfPairs = List[Tuple[any, any]]


@dataclass
class Request:
    operation: Operation
    path: str
    headers: ListOfPairs
    body: Optional[str]

    def dump(self, body_max_chars=80):
        print(f"{self.operation.method.upper()} {self.path}")
        if self.body is not None:
            if len(self.body) > body_max_chars:
                b = self.body[:body_max_chars] + '...'
            else:
                b = self.body
            print(f"  BODY: {b}")

    def execute(self, host: str) -> "requests.models.Response":
        try:
            import requests  # optional dependency
        except ImportError:
            raise MissingDependencyException("Please install the requests library")
        if host.endswith('/'):
            host = host[:-1]
        response = requests.request(
            url=host + self.path,
            method=self.operation.method,
            data=self.body,
            headers=dict(self.headers)
        )
        return response


@dataclass
class TestCase:
    operation: Operation
    body: Optional[str] = None
    query_parameters: ListOfPairs = field(default_factory=list)
    path_parameters: ListOfPairs = field(default_factory=list)
    headers: ListOfPairs = field(default_factory=list)
    cookies: ListOfPairs = field(default_factory=list)

    def to_request(self) -> Request:
        path = self.operation.path
        for key, value in self.path_parameters:
            placeholder = '{' + key + '}'
            assert placeholder in path, f"{placeholder}, {path}, {self.operation.operation_id}"
            # assert value != "" # TODO
            path = path.replace(placeholder, value)
        if self.query_parameters:
            path += "?" + urlencode(self.query_parameters)
        headers: ListOfPairs = self.headers.copy()
        # TODO: content type should not be hardcoded
        headers.append(('content-type', 'application/json'))
        body = None
        if self.body is not None:
            body = json.dumps(self.body)
        return Request(
            path=path,
            headers=headers,
            body=body,
            operation=self.operation
        )


class ExtractRequestLeaf(Leaf):

    def apply(self, data: TestCase) -> any:
        return data.to_request()

    def description(self) -> str:
        return "Convert to request"


class StartTestCase(Decision):
    def __init__(self, operation: Operation) -> None:
        super().__init__(operation.operation_id, True)
        self.operation = operation

    def apply(self, data: any) -> any:
        return TestCase(self.operation)

    def description(self) -> str:
        return "Start Test Case"


class InsertParamLeaf(Leaf):
    def __init__(self, is_valid: bool, parameter: Parameter, raw_value: any) -> None:
        super().__init__(None, is_valid)
        self.parameter = parameter
        self.raw_value = raw_value
        self.values = format_parameter_value(parameter, raw_value)

    def description(self) -> str:
        return f"Insert {self.parameter.name} = {self.raw_value} into {self.parameter.position.name}"

    def apply(self, data: TestCase) -> any:
        storage: ListOfPairs = {
            ParameterPosition.QUERY: data.query_parameters,
            ParameterPosition.HEADER: data.headers,
            ParameterPosition.PATH: data.path_parameters,
            ParameterPosition.COOKIE: data.cookies,
        }[self.parameter.position]
        storage.extend(self.values)
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

    def add(self, schema: any) -> Samples:
        key = self._to_key(schema)
        if key in self.samples:
            return self.samples[key]

        composite_schema = {
            'minLength': 1,
            'minItems': 1,
            **schema,
        }
        composite_schema = normalize_schema(composite_schema, False)
        config = json_schema.default_config()
        config.normalize = False
        graph = json_schema.parse(composite_schema, config)
        samples = Samples()
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if sample is None:
                continue
            if i.is_valid:
                samples.valid.append(sample)
            else:
                samples.invalid.append(sample)
            if len(samples.valid) > 50 and len(samples.invalid) > 50:
                break
        if not samples.valid and not samples.invalid:
            raise Exception(f"Schema has no instances")
        self.samples[key] = samples
        return samples

def generate_one(operation: Operation, sample_cache: SampleCache) -> Request:
    test_case = TestCase(operation)
    for param in operation.parameters:
        pass
    return test_case.to_request()

def _is_suitable_for_path(sample: any) -> bool:
    if isinstance(sample, list):
        return len(sample) > 0
    if isinstance(sample, dict):
        return len(sample.keys()) > 0
    if isinstance(sample, str):
        return len(sample) > 0
    if sample is None:
        return False
    return True

def parse_operation(operation: Operation, sample_cache: SampleCache, parameter_overwrites: Optional[Dict[str, any]] = None) -> Node:
    op_root = StartTestCase(operation)
    for param in operation.parameters:
        param_root = NoOpDecision(f"{operation.operation_id}/{param.name}")
        if parameter_overwrites and param.name in parameter_overwrites:
            samples = Samples(valid=parameter_overwrites[param.name])
        else:
            samples = sample_cache.add(param.schema)

        for sample in samples.valid:
            if param.position != ParameterPosition.PATH or _is_suitable_for_path(sample):
                param_root.add_transition(InsertParamLeaf(True, param, sample))
        for sample in samples.invalid:
            if param.position != ParameterPosition.PATH or _is_suitable_for_path(sample):
                param_root.add_transition(InsertParamLeaf(False, param, sample))
        param_root.add_transition(NoOpLeaf(is_valid=not param.required))
        op_root.add_transition(param_root)
    if operation.request_body:
        body_root = NoOpDecision('BODY')
        bodies = sample_cache.add(operation.request_body.schema)
        for body in bodies.valid:
            body_root.add_transition(InsertBodyLeaf(True, body))
        for body in bodies.invalid:
            body_root.add_transition(InsertBodyLeaf(False, body))
        body_root.add_transition(NoOpLeaf(is_valid=not operation.request_body.required))
        op_root.add_transition(body_root)
    op_root.add_transition(ExtractRequestLeaf())
    return op_root
