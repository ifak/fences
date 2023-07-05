import os

from unittest import TestCase
from jsonschema import validators
from fences.json_schema.normlaize import normalize, check_normalized
from fences.core.exception import NormalizationException


class CheckNormalizedTest(TestCase):

    def test_empty(self):
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
        check_normalized({
            'oneOf': [{}, {}],
        })

    def test_any_of(self):
        with self.assertRaises(NormalizationException):
            check_normalized({
                'anyOf': [],
                'oneOf': [],
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'anyOf': [],
            })
        with self.assertRaises(NormalizationException):
            check_normalized({
                'anyOf': [{}],
            })
        check_normalized({
            'anyOf': [{}, {}],
        })


class NormalizeTestCase(TestCase):

    def test_all_of_nested(self):
        n = normalize({
            'allOf': [{
                'allOf': [{
                    'type': 'string'
                }]
            }]
        })
        self.assertDictEqual(n, {'type': 'string'})
        check_normalized(n)

    def test_all_of_with_others(self):
        n = normalize({
            'allOf': [{
                'multipleOf': 2,
                'minimum': 10
            }],
            'multipleOf': 3,
            'type': 'integer'
        })
        self.assertDictEqual(n, {
            'multipleOf': 6,
            'minimum': 10,
            'type': 'integer',
        })
        check_normalized(n)

    def test_all_of_in_subschemas(self):
        n = normalize({
            'items': {
                'allOf': [
                    {'multipleOf': 2},
                    {'multipleOf': 3}
                ]
            }
        })
        self.assertDictEqual(n, {'items': {'multipleOf': 6}})
        check_normalized(n)

    def test_all_of_with_ref(self):
        n = normalize({
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
        })
        del n['$defs']
        self.assertDictEqual({'type': 'string', 'pattern': 'a+'}, n)
        check_normalized(n)

    def test_one_of_with_others(self):
        n = normalize({
            'oneOf': [{'minimum': 10}],
            'minimum': 20
        })
        self.assertDictEqual(n, {'minimum': 20})
        check_normalized(n)

    def test_one_of_nested(self):
        n = normalize({
            'oneOf': [{
                'oneOf': [{
                    'type': 'integer'
                }]
            }]
        })
        self.assertDictEqual(n, {'type': 'integer'})
        check_normalized(n)

    def test_any_of_with_others(self):
        n = normalize({
            'anyOf': [{'minimum': 10}],
            'minimum': 20
        })
        self.assertDictEqual(n, {'minimum': 20})
        check_normalized(n)

    def test_one_of_nested(self):
        n = normalize({
            'anyOf': [{
                'anyOf': [{
                    'type': 'integer'
                }]
            }]
        })
        self.assertDictEqual(n, {'type': 'integer'})
        check_normalized(n)

    def test_mixed(self):
        n = normalize({
            'allOf': [{
                'oneOf': [{
                    'anyOf': [{
                        'type': 'string'
                    }]
                }]
            }]
        })
        self.assertDictEqual(n, {'type': 'string'})
        check_normalized(n)

    def test_bool(self):
        n = normalize({
            'allOf': [True, False]
        })
        self.assertEqual(n, False)
        check_normalized(n)
        n = normalize({
            'oneOf': [False, False]
        })
        self.assertEqual(n, False)
        check_normalized(n)

    def test_if_then_else(self):
        n = normalize({
            'if': {'multipleOf': 2},
            'then': {'multipleOf': 3},
            'else': {'multipleOf': 5},
        })
        check_normalized(n)

    def test_not(self):
        n = normalize({
            'not': {
                'type': 'object'
            }
        })
        check_normalized(n)
