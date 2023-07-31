from unittest import TestCase
from jsonschema import validators
from fences.json_schema.normlaize import normalize, check_normalized
from fences.core.exception import NormalizationException

import yaml


class CheckNormalizedTest(TestCase):

    def test_empty(self):
        with self.assertRaises(NormalizationException):
            check_normalized({})

    def test_all_of(self):
        with self.assertRaises(NormalizationException):
            check_normalized({'allOf': []})
        with self.assertRaises(NormalizationException):
            check_normalized({
                'properties': {
                    'foo': {
                        'allOf': []
                    }
                }
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'items': {
                    'allOf': []
                }
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'prefixItems': [{
                    'allOf': []
                }]
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'oneOf': [{
                    'allOf': []
                }]
            })

    def test_one_of(self):
        with self.assertRaises(NormalizationException):
            check_normalized({
                'oneOf': [],
                'items': [],
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'oneOf': [],
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'oneOf': [{}],
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'oneOf': [{}, {}],
            })

    def test_any_of(self):
        with self.assertRaises(NormalizationException):
            check_normalized({
                'anyOf': [],
                'oneOf': [],
            })
        check_normalized({
            'anyOf': [],
        })
        check_normalized({
            'anyOf': [{}],
        })
        check_normalized({
            'anyOf': [{}, {}],
        })

    def test_ref(self):
        with self.assertRaises(NormalizationException):
            check_normalized({'$ref': 'foo', 'x': 'bar'})
        with self.assertRaises(NormalizationException):
            check_normalized({'$ref': 'foo', 'anyOf': 'bar'})
        with self.assertRaises(NormalizationException):
            check_normalized({'anyOf': [{'$ref': '#/', 'invalid': 'x'}]})
        check_normalized({'anyOf': [{'$ref': '#/'}]})


class NormalizeTestCase(TestCase):

    def check(self, data: dict, debug=False):
        yaml.Dumper.ignore_aliases = lambda *args: True

        if debug:
            print("Before")
            print(yaml.safe_dump(data))
        n = normalize(data)
        if debug:
            print("After")
            print(yaml.safe_dump(n))
        check_normalized(n)

    def test_trivial(self):
        n = {
            'minimum': 10
        }
        self.check(n)

    def test_all_of_nested(self):
        n = {
            'allOf': [{
                'allOf': [{
                    'type': 'string'
                }]
            }]
        }
        self.check(n)

    def test_all_of_with_others(self):
        n = {
            'allOf': [{
                'multipleOf': 2,
                'minimum': 10
            }],
            'multipleOf': 3,
            'type': 'integer'
        }
        self.check(n)

    def test_all_of_in_subschemas(self):
        n = {
            'items': {
                'allOf': [
                    {'multipleOf': 2},
                    {'multipleOf': 3}
                ]
            }
        }
        self.check(n)

    def test_all_of_with_ref(self):
        n = {
            '$defs': {
                'foo': {
                    'type': 'string'
                },
                'bar': {
                    'pattern': 'a+'
                }
            },
            'allOf': [
                {'$ref': '#/$defs/foo'},
                {'$ref': '#/$defs/bar'},
            ]
        }
        self.check(n)

    def test_one_of_with_others(self):
        n = {
            'oneOf': [{'minimum': 10}],
            'minimum': 20
        }
        self.check(n)

    def test_one_of_nested(self):
        n = {
            'oneOf': [{
                'oneOf': [{
                    'type': 'integer'
                }]
            }]
        }
        self.check(n)

    def test_any_of_with_others(self):
        n = {
            'anyOf': [{'minimum': 10}],
            'minimum': 20
        }
        self.check(n)

    def test_one_of_nested(self):
        n = {
            'anyOf': [{
                'anyOf': [{
                    'type': 'integer'
                }]
            }]
        }
        self.check(n)

    def test_mixed(self):
        n = {
            'allOf': [{
                'oneOf': [{
                    'anyOf': [{
                        'type': 'string'
                    }]
                }]
            }]
        }
        self.check(n)

    def test_bool(self):
        n = {
            'allOf': [True, False]
        }
        self.check(n)
        n = {
            'oneOf': [False, False]
        }
        self.check(n)

    def test_if_then_else(self):
        n = {
            'if': {'multipleOf': 2},
            'then': {'multipleOf': 3},
            'else': {'multipleOf': 5},
        }
        self.check(n)

    def test_not(self):
        n = {
            'not': {
                'type': 'object'
            }
        }
        self.check(n)

    def test_properties(self):
        n = {
            'allOf': [{
                'properties': {
                    'foo': {
                        'type': 'string'
                    }
                }
            },
            {
                'properties': {
                    'foo': {
                        'type': 'integer'
                    }
                }
            }]
        }
        self.check(n)

    def test_recursive_ref(self):
        n = {
            'type': 'object',
            'properties': {
                'foo': {
                    "$ref": '#/'
                }
            }
        }
        self.check(n)

    def test_nested_refs(self):
        n = {
            'properties': {
                'children': {
                    '$ref': '#/',
                    'type': 'object'
                }
            }
        }
        self.check(n)

    def test_circular_reference(self):
        n = {
                "properties": {
                    "x": {
                        'anyOf': [{
                            "$ref": "#/"
                        }]
                    }
                }
            }
        self.check(n)

    def test_paper(self):
        n = {
        "type": "object",
        "required": [
            "children"
        ],
        "properties": {
            "children": {
            "allOf": [
                {
                "anyOf": [
                    {
                    "$ref": "#/"
                    },
                    {
                    "not": {
                        "minimum": 10
                    }
                    }
                ]
                },
                {
                "type": [
                    "integer",
                    "object"
                ]
                }
            ]
            }
        }
        }
        self.check(n)