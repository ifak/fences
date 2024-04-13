import os
import yaml
import json
import time
from unittest import TestCase
from dataclasses import dataclass

from fences.json_schema.normalize import normalize, check_normalized
from fences.core.exception import JsonPointerException
from fences import parse_json_schema
from fences.core import util

from jsonschema import exceptions, validators
from jsonschema._utils import equal

from json_schema_tool import parse_schema, coverage

from hypothesis import given, settings, HealthCheck, errors
from hypothesis_jsonschema import from_schema


@dataclass
class Stats:
    num_skipped = 0
    num_failed = 0
    num_succeeded = 0


class RasingResolverException(Exception):
    pass


class RaisingResolver(validators.RefResolver):
    def __init__(self):
        pass

    def resolve(self, ref):
        raise RasingResolverException()

    def push_scope(self, scope):
        raise RasingResolverException()

    def pop_scope(self):
        raise RasingResolverException()

    def resolve_from_url(self, url):
        raise RasingResolverException()

    def resolve_fragment(self, document, fragment):
        raise RasingResolverException()

    def resolve_remote(self, uri):
        raise RasingResolverException()


script_dir = os.path.dirname(os.path.realpath(__file__))


def invert(orig_validator):
    """
    Returns a validator with inverted semantic
    """
    def impl(validator, local_schema, instance, schema):
        iterator = orig_validator(validator, local_schema, instance, schema)
        dummy = object()
        if next(iterator, dummy) is dummy:
            yield exceptions.ValidationError(f"Should be rejected")
    return impl


def validate_type(validator, types, instance, schema):
    """
    A type validator which is able to handle empty type lists
    For the original types validator, the following schema accepts everything
      {"type": []}
    This validator rejects everything
    """
    if not isinstance(types, list):
        types = [types]
    if not types:
        yield exceptions.ValidationError(f"{instance!r} is always invalid")
    if not any(validator.is_type(instance, type) for type in types):
        reprs = ", ".join(repr(type) for type in types)
        yield exceptions.ValidationError(f"{instance!r} is not of type {reprs}")


def validate_enum(validator, enums, instance, schema):
    """
    jsonschema's enum implementation is buggy, this one fixes it
    (see https://github.com/python-jsonschema/jsonschema/pull/1208)
    """
    if all(not equal(instance, each) for each in enums):
        yield exceptions.ValidationError(f"{instance!r} is not in enum")


class Normalize(TestCase):
    """
    Iterates the official JSON Schema test suite
    For each schema x it creates the normalized schema x'
    It then checks if all samples from the test suite are accepted by both x and x' or
    are rejected by both x and x', respectively.
    """

    def skip(self, schema_orig):
        blacklist = [
            'patternProperties',
            'unevaluatedItems',
            'unevaluatedProperties',
            'multipleOf',
            'dynamicRef',
            '$id',
            'oneOf',
        ]
        as_text = json.dumps(schema_orig)
        for i in blacklist:
            if i in as_text:
                return True
        return False

    def test_json_schema_test_suite(self):
        root = os.path.join(script_dir, '../fixtures/JSON-Schema-Test-Suite/tests/draft2020-12')
        stats = Stats()
        output = False
        for file in sorted(os.listdir(root)):
            if file == 'optional':
                continue
            if output:
                print("-"*20)
                print(file)
            with open(os.path.join(root, file)) as f:
                test_suites = json.load(f)
            for test_suite in test_suites:
                self.run_suite(test_suite, output, stats)
        print(f"Num Skipped:    {stats.num_skipped}")
        print(f"Num Failed:     {stats.num_failed}")
        print(f"Num Succeeded:  {stats.num_succeeded}")

    def run_suite(self, suite: dict, output: bool, stats: Stats):

        if output:
            print(suite['description'])

        schema_orig = suite['schema']

        if self.skip(schema_orig):
            stats.num_skipped += 1
            return

        # Normalize
        if output:
            print("Orig:")
            print(yaml.safe_dump(schema_orig, indent=4))
            print(json.dumps(schema_orig, indent=4))
        try:
            schema_norm = normalize(schema_orig)
        except JsonPointerException:
            # Currently does not support remote pointers
            stats.num_skipped += 1
            return

        # Check if normalized
        if output:
            print("Norm:")
            print(yaml.safe_dump(schema_norm, indent=4))
            print(json.dumps(schema_norm, indent=4))
        try:
            check_normalized(schema_norm)
        except JsonPointerException:
            stats.num_skipped += 1
            return

        # Check if schemas are equal
        base = validators.Draft202012Validator
        validator_orig = validators.extend(base, {
            'enum': validate_enum,
        })(schema_orig, resolver=RaisingResolver())

        validator_norm = validators.extend(base, {
            'enum': validate_enum,
            'NOT_enum': invert(validate_enum),
            'NOT_const': invert(base.VALIDATORS["const"]),
            'NOT_multipleOf': invert(base.VALIDATORS["multipleOf"]),
            'type': validate_type,
        })(schema_norm, resolver=RaisingResolver())
        for test_case in suite['tests']:
            data = test_case['data']
            try:
                validator_orig.validate(data)
                valid_by_orig = True
            except exceptions.ValidationError:
                valid_by_orig = False
            except (exceptions.SchemaError, RasingResolverException):
                # Ignore this sample, try next one
                continue

            self.assertEqual(valid_by_orig, test_case['valid'])

            try:
                validator_norm.validate(data)
                valid_by_norm = True
            except exceptions.ValidationError:
                valid_by_norm = False
            except (exceptions.SchemaError, RasingResolverException):
                # Ignore this sample, try next one
                continue

            if output:
                print("Is valid" if valid_by_orig else "is invalid")
                print(yaml.safe_dump(test_case['data'], indent=4))

            self.assertEqual(valid_by_norm, valid_by_orig)

        # success!
        stats.num_succeeded += 1

    def test_enum_fixed(self):
        schema1 = {
            "const": [False]
        }
        schema2 = {
            "enum": [
                [False]
            ],
        }
        instance = [0]
        ok1 = validators.Draft202012Validator(schema1).is_valid(instance)
        ok2 = validators.extend(validators.Draft202012Validator, {'enum': validate_enum})(schema2).is_valid(instance)
        self.assertEqual(ok1, ok2)


@dataclass
class CoverageStats:
    total = 0
    manual_coverage = 0
    manual_count = 0
    fences_coverage = 0
    fences_count = 0
    fences_time = 0
    hypothesis_coverage = 0
    hypothesis_count = 0
    hypothesis_time = 0


class Coverage(TestCase):
    blacklist = [
        # Not implemented, yet (object)
        'additionalProperties.json',
        'dependentRequired.json',
        'dependentSchemas.json',
        'maxProperties.json',
        'minProperties.json',
        'patternProperties.json',
        'propertyNames.json',
        'unevaluatedProperties.json',

        # Not implemented, yet (array)
        'unevaluatedItems.json',
        'uniqueItems.json',

        # Requires remote reference resolution, out of scope of fences
        'anchor.json',
        'defs.json',
        'id.json',
        'ref.json',
        'refRemote.json',
        'dynamicRef.json',

        # No coverage measurement available (and trivial anyway)
        'boolean_schema.json',

        # Optional
        'format.json',
        'optional',
        'unknownKeyword.json',
        'vocabulary.json',
    ]

    # Most of these are schemas which are not satisfiable, so that Fences cannot generate valid samples for them
    description_blacklist = [
        'items and subitems',
        'prefixItems with no additional items allowed',
        'prefixItems with boolean schemas',
        'allOf with boolean schemas, some false',
        'allOf with boolean schemas, all false',
        'anyOf with boolean schemas, all false',
        'not with boolean schema true',
        "collect annotations inside a 'not', even if collection is disabled",
        "oneOf with boolean schemas, all true",
        "oneOf with boolean schemas, one true",
        "oneOf with boolean schemas, all false",
        "oneOf with required",
        "oneOf with missing optional property",
    ]

    with_hypothesis = False
    output = False

    def trim(self, s: str, length=40) -> str:
        ellipsis = "..."
        length -= len(ellipsis)
        if len(s) > length:
            s = s[:length] + ellipsis
        return s

    def run_suite(self, file, table: util.Table, stats: CoverageStats):
        if self.output:
            print(file)
        with open(file, "rb") as f:
            suites = json.load(f)

        for suite in suites:
            schema = suite['schema']
            description = suite['description']
            if description in self.description_blacklist:
                continue
            if description != 'properties whose names are Javascript object property names':
                continue
            if self.output:
                print(description)
                print(json.dumps(schema, indent=4))
            row = []
            row.append(self.trim(suite['description']))
            validator = parse_schema(schema)
            stats.total += 1

            # Validate using official test data
            cov = coverage.SchemaCoverage(validator)
            count = 0
            for test in suite['tests']:
                data = test['data']
                expected_valid = test['valid']
                result = validator.validate(data)
                cov.update(result)
                self.assertEqual(expected_valid, result.ok)
                count += 1
            n = cov.coverage()
            stats.manual_coverage += n
            stats.manual_count += count
            row.extend([str(int(n*100)), str(count)])

            # Validate using generated test data from fences
            cov.reset()
            count = 0
            start = time.perf_counter()
            graph = parse_json_schema(schema)
            for i in graph.generate_paths():
                sample = graph.execute(i.path)
                result = validator.validate(sample)
                cov.update(result)
                count += 1
            stats.fences_time += time.perf_counter() - start
            n = cov.coverage()
            stats.fences_coverage += n
            stats.fences_count += count
            row.extend([str(int(n*100)), str(count)])

            # Validate using generated test data from Hypothesis
            if self.with_hypothesis:
                print(description)
                cov.reset()
                validation_results = []
                start = time.perf_counter()

                @given(from_schema(schema))
                @settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
                def test(value):
                    result = validator.validate(value)
                    validation_results.append(result)
                try:
                    test()
                except errors.Unsatisfiable:
                    pass

                for i in validation_results:
                    cov.update(i)
                stats.hypothesis_time += time.perf_counter() - start
                n = cov.coverage()
                stats.hypothesis_coverage += n
                stats.hypothesis_count += len(validation_results)
                row.extend([str(int(n*100)), str(len(validation_results))])
            else:
                row.extend(['-', '-'])

            table.append(row)

    def test_all_suites(self):
        root = os.path.join(script_dir, '../fixtures/JSON-Schema-Test-Suite/tests/draft2020-12')
        table = []
        table.append(['Suite', 'Manual', '', 'Fences', '', 'Hypothesis', ''])
        table.append(['', 'Cov.', 'Count', 'Cov.', 'Count', 'Cov.', 'Count'])
        table.append(None)
        stats = CoverageStats()
        for file in sorted(os.listdir(root)):
            if file in self.blacklist:
                continue
            table.append([file])
            self.run_suite(os.path.join(root, file), table, stats)
            table.append(None)
        table.append([
            'Total',
            str(int(stats.manual_coverage * 100 / stats.total)),     str(stats.manual_count),
            str(int(stats.fences_coverage * 100 / stats.total)),     str(stats.fences_count),
            str(int(stats.hypothesis_coverage * 100 / stats.total)), str(stats.hypothesis_count),
        ])
        print()
        util.print_table(table)

        print(f"Total time (Fences):     {stats.fences_time}")
        print(f"Total time (Hypothesis): {stats.hypothesis_time}")
