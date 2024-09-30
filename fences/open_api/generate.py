from typing import List, Dict, Optional, TYPE_CHECKING

from .open_api import Operation, ParameterPosition, Parameter
from .format import format_parameter_value
from .exceptions import MissingDependencyException

from fences.json_schema import parse as json_schema
from fences.json_schema.normalize import normalize as normalize_schema, NormalizationConfig
from fences.core.node import Node, NoOpDecision, Decision, Leaf, NoOpLeaf

from dataclasses import dataclass, field
from urllib.parse import urlencode
import json

if TYPE_CHECKING:
    import requests  # optional dependency


@dataclass
class Request:
    operation: Operation
    body: Optional[str] = None
    query_parameters: dict = field(default_factory=dict)
    path_parameters: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)

    def make_path(self) -> str:
        path = self.operation.path
        for key, value in self.path_parameters.items():
            placeholder = '{' + key + '}'
            assert placeholder in path, f"{placeholder}, {path}, {self.operation.operation_id}"
            # assert values[0] != "" # TODO: this need to be ensured by the schema provided by the user
            path = path.replace(placeholder, value)
        if self.query_parameters:
            path += "?" + urlencode(self.query_parameters)
        return path

    def dump(self, body_max_chars=80):
        print(f"{self.operation.method.upper()} {self.make_path()}")
        if self.body is not None:
            body_json = json.dumps(self.body)
            if len(body_json) > body_max_chars:
                b = body_json[:body_max_chars] + '...'
            else:
                b = body_json
            print(f"  BODY: {b}")

    def insert_param_values(self, position: ParameterPosition, values: dict):
        storage: dict = {
            ParameterPosition.QUERY: self.query_parameters,
            ParameterPosition.HEADER: self.headers,
            ParameterPosition.PATH: self.path_parameters,
            ParameterPosition.COOKIE: self.cookies,
        }[position]
        storage.update(values)

    def build(self, host: str) -> "requests.models.Request":
        try:
            import requests  # optional dependency
        except ImportError:
            raise MissingDependencyException("Please install the requests library")

        if self.body is None:
            body = None
        else:
            body = json.dumps(self.body)

        if host.endswith('/'):
            host = host[:-1]
        return requests.models.Request(
            url=host + self.make_path(),
            method=self.operation.method,
            data=body,
            headers=self.headers
        )

    def execute(self, host: str) -> "requests.models.Response":
        try:
            import requests  # optional dependency
        except ImportError:
            raise MissingDependencyException("Please install the requests library")
        prepared_request = self.build(host).prepare()
        return requests.Session().send(prepared_request)


class CreateRequest(Decision):
    def __init__(self, operation: Operation) -> None:
        super().__init__(operation.operation_id, True)
        self.operation = operation

    def apply(self, data: any) -> any:
        return Request(self.operation)

    def description(self) -> str:
        return f"Create request for {self.operation.operation_id}"


class InsertParamLeaf(Leaf):
    def __init__(self, is_valid: bool, parameter: Parameter, raw_value: any) -> None:
        super().__init__(None, is_valid)
        self.parameter = parameter
        self.raw_value = raw_value
        self.values = format_parameter_value(parameter, raw_value)

    def description(self) -> str:
        return f"Insert {self.parameter.name} = {self.raw_value} into {self.parameter.position.name}"

    def apply(self, data: Request) -> any:
        data.insert_param_values(self.parameter.position, self.values)
        return data


class InsertBodyLeaf(Leaf):
    def __init__(self, is_valid: bool, body: str) -> None:
        super().__init__(None, is_valid)
        self.body = body

    def apply(self, data: Request) -> any:
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
        self.body_samples: Dict[str, Samples] = {}
        self.other_samples: Dict[str, Samples] = {}

    def _to_key(self, schema: any) -> str:
        return json.dumps(schema)

    def add(self, schema: any, is_body: bool) -> Samples:
        key = self._to_key(schema)
        try:
            if is_body:
                return self.body_samples[key]
            else:
                return self.other_samples[key]
        except KeyError:
            pass

        norm_conf = NormalizationConfig(
            full_merge=False,
        )
        schema_norm = normalize_schema(schema, norm_conf)
        config = json_schema.default_config()
        config.normalize = False
        if not is_body:
            # do not deviate from base type
            config.default_samples.clear()
        graph = json_schema.parse(schema_norm, config)
        samples = Samples()
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if i.is_valid:
                samples.valid.append(sample)
            else:
                samples.invalid.append(sample)
            if len(samples.valid) > 50 and len(samples.invalid) > 50:
                break
        if not samples.valid and not samples.invalid:
            raise Exception(f"Schema has no instances")

        if is_body:
            self.body_samples[key] = samples
        else:
            self.other_samples[key] = samples
        return samples


def generate_one_valid(operation: Operation, sample_cache: SampleCache, parameter_overwrites: Dict[str, any] = {}) -> Request:
    test_case = Request(operation)
    for param in operation.parameters:
        try:
            sample = parameter_overwrites[param.name]
        except KeyError:
            if not param.required:
                continue
            sample = sample_cache.add(param.schema, False).valid[0]
        sample = format_parameter_value(param, sample)
        test_case.insert_param_values(param.position, sample)
    if operation.request_body:
        bodies = sample_cache.add(operation.request_body.schema, True)
        test_case.body = bodies.valid[0]
    return test_case


def generate_all(operation: Operation, sample_cache: SampleCache, valid_values: Optional[Dict[str, List[any]]] = {}) -> Node:
    op_root = CreateRequest(operation)
    for param in operation.parameters:
        param_root = NoOpDecision(f"{operation.operation_id}/{param.name}")
        if param.position != ParameterPosition.PATH:
            param_root.add_transition(NoOpLeaf(is_valid=not param.required))
        samples = sample_cache.add(param.schema, False)
        try:
            samples.valid = valid_values[param.name]
        except KeyError:
            pass
        for sample in samples.valid:
            param_root.add_transition(InsertParamLeaf(True, param, sample))
        for sample in samples.invalid:
            param_root.add_transition(InsertParamLeaf(False, param, sample))
        op_root.add_transition(param_root)
    if operation.request_body:
        body_root = NoOpDecision('BODY')
        body_root.add_transition(NoOpLeaf(is_valid=not operation.request_body.required))
        bodies = sample_cache.add(operation.request_body.schema, True)
        for body in bodies.valid:
            body_root.add_transition(InsertBodyLeaf(True, body))
        for body in bodies.invalid:
            body_root.add_transition(InsertBodyLeaf(False, body))
        op_root.add_transition(body_root)
    if not op_root.outgoing_transitions:
        op_root.add_transition(NoOpLeaf(None, True))
    return op_root
