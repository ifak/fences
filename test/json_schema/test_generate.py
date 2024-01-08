from fences.json_schema import parse, normalize
from fences.core.debug import check_consistency
from jsonschema import Draft202012Validator, ValidationError
import unittest
import yaml
import os
import json
from fences.core.render import render

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class TestGenerateBase(unittest.TestCase):

    def check(self, schema, debug=False, strict_invalid=True):
        if debug:
            print("Input schema:")
            yaml.SafeDumper.ignore_aliases = lambda *args: True
            print(yaml.safe_dump(schema))
        validator = Draft202012Validator(schema)
        graph = parse.parse(schema)
        if debug:
            render(graph).write_svg('graph.svg')
        check_consistency(graph)
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if debug:
                print("Valid" if i.is_valid else "Invalid")
                print(json.dumps(sample, indent=4))
            if i.is_valid:
                validator.validate(sample)
            else:
                if strict_invalid:
                    with self.assertRaises(ValidationError):
                        validator.validate(sample)


class TestNumber(TestGenerateBase):

    def test_no_constraints(self):
        self.check({'type': 'number'})

    def test_minimum(self):
        self.check({'type': 'number', 'minimum': 100})
        self.check({'type': 'number', 'exclusiveMinimum': 100})

    def test_maximum(self):
        self.check({'type': 'number', 'maximum': -100})
        self.check({'type': 'number', 'exclusiveMaximum': -100})

    def test_multiple_of(self):
        self.check({'type': 'number', 'minimum': 100, 'multipleOf': 3})
        self.check({'type': 'number', 'exclusiveMinimum': 100, 'multipleOf': 3})
        self.check({'type': 'number', 'maximum': 100, 'multipleOf': 3})
        self.check({'type': 'number', 'exclusiveMaximum': 100, 'multipleOf': 3})


class TestBool(TestGenerateBase):

    def test_no_constraints(self):
        self.check({'type': 'boolean'})


class TestString(TestGenerateBase):

    def test_no_constraints(self):
        self.check({'type': 'string'})

    def test_length(self):
        self.check({'type': 'string', 'minLength': 10})
        self.check({'type': 'string', 'maxLength': 10})
        self.check({'type': 'string', 'minLength': 3, 'maxLength': 10})

    def test_mail(self):
        self.check({'type': 'string', 'format': "email"})


class TestArray(TestGenerateBase):

    def test_no_constraints(self):
        self.check({'type': 'array'})

    def test_items(self):
        self.check({'type': 'array', 'items': {'type': 'string'}})
        self.check({'type': 'array', 'items': {'type': 'number'}})
        self.check({'type': 'array', 'items': {'type': 'array'}})
        self.check({'type': 'array', 'items': {'type': 'boolean'}})
        self.check({'type': 'array', 'items': {'type': 'null'}})
        self.check({'type': 'array', 'items': {'type': 'object', 'properties': {'foo': {}}}})

    def test_length(self):
        self.check({'type': 'array', 'minItems': 3})
        self.check({'type': 'array', 'maxItems': 3})

    def test_prefix_items(self):
        self.check({'type': 'array', 'prefixItems': [{'type': 'string'}]})

    def test_contains(self):
        self.check({'type': 'array', 'contains': {'type': 'string'}})
        self.check({'type': 'array', 'contains': {'type': 'string'}, 'minContains': 2})
        self.check({
            'type': 'array',
            'contains': {'type': 'number', 'minimum': 3}, 'minContains': 2,
            'items': {'type': 'number'}
        })


class TestObject(TestGenerateBase):

    def test_no_constraints(self):
        self.check({'type': 'object'})

    def test_optional_properties(self):
        self.check({'type': 'object', 'properties': {'foo': {}}})

    def test_required_properties(self):
        self.check({'type': 'object', 'required': ['foo'], 'properties': {'foo': {}}})
        self.check({'type': 'object', 'required': ['foo'], 'properties': {'bar': {}}})
        self.check({'type': 'object', 'required': ['foo']})


class TestRefs(TestGenerateBase):

    def test_refs(self):
        schema = {
            "type": "object",
            "properties": {
                "test": {
                    "properties": {
                        "first": {
                            "type": "string"
                        },
                        "second": {
                            "type": "array",
                            "items": {
                                "$ref": "#/$defs/mydef"
                            }
                        }
                    }
                },
            },
            "$defs": {
                "mydef": {
                    "$ref": "#/$defs/foo"
                },
                "foo": {
                    "properties": {
                        "first": {
                            "type": "boolean"
                        },
                    }
                }
            }
        }
        self.check(schema)

    def test_recursive_ref(self):
        schema = {
            "type": "array",
            "items": {
                "properties": {
                    "second": {
                        "$ref": "#"
                    }
                }
            }
        }
        self.check(schema)

    def test_many_refs(self):
        schema = {
            "allOf": [
                {
                    "type": "object",
                    "properties": {
                        "assetAdministrationShells": {
                            "type": "array",
                            "items": {
                                "properties": {
                                    "assetInformation": {
                                        "type": "object",
                                        "properties": {
                                            "specificAssetIds": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/$defs/SpecificAssetId"
                                                },
                                                "minItems": 1
                                            }
                                        }
                                    }
                                },
                                "required": [
                                    "assetInformation"
                                ]
                            },
                            "minItems": 1
                        }
                    }
                }
            ],
            "$defs": {
                "SpecificAssetId": {
                    "allOf": [
                        {
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "minLength": 1
                                },
                                "value": {
                                    "type": "string",
                                    "minLength": 1
                                }
                            },
                            "required": [
                                "name",
                                "value"
                            ]
                        }
                    ]
                }
            }
        }
        self.check(schema)


class TestSpecial(TestGenerateBase):

    def test_empty(self):
        self.check({})

    def test_const(self):
        schema = {
            "type": "object",
            "properties": {
                "country": {
                    "const": "United States of America"
                }
            }
        }
        self.check(schema)

    def test_boolean_schema(self):
        schema = {'allOf': [True, True]}
        self.check(schema)

    def test_only_invalid_leafs(self):
        schema = {
            "type": "object",
            "anyOf": [{
                "properties": {
                    "a": {
                        "type": "object",
                        "properties": {
                            "b": False
                        },
                        "required": ["b"]
                    },
                },
                "required": ["a"]
            }, {
                "type": "object",
                "properties": {
                    "c": {"type": "string"}
                }
            }]
        }
        self.check(schema, strict_invalid=False)

    def test_dependent_required(self):
        schema = {
            "dependentRequired": {
                "a": ["b", "c"]
            },
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "boolean"},
                "c": {"type": "number"},
            }
        }
        self.check(schema, strict_invalid=False)


class TestLogicalApplicators(TestGenerateBase):

    def test_not_1(self):
        schema = {
            "not": {
                "properties": {
                    "b": {
                        "properties": {
                            "bb": {"not": {"type": "string"}}
                        }
                    }
                }
            }
        }
        self.check(schema)

    def test_not_2(self):
        schema = {
            "not": {
                "properties": {
                    "a": {
                        "type": "string"
                    },
                    "b": {
                        "properties": {
                            "bb": {"type": "string"}
                        }
                    }
                }
            }
        }
        self.check(schema, strict_invalid=False)

    def test_all_of_objects(self):
        schema = {
            "allOf": [
                {"$ref": "#/$defs/test"},
                {"$ref": "#/$defs/test2"},
            ],
            "$defs": {
                "test": {
                    "properties": {
                        "abc": {"type": "string"}
                    },
                    "required": ["abc"]
                },
                "test2": {
                    "properties": {
                        "xyz": {"type": "string"}
                    },
                    "required": ['xyz']
                }
            }
        }
        self.check(schema)

    def test_all_of_arrays(self):
        schema = {
            "type": "array",
            "items":
            {
                "allOf": [
                    {"$ref": "#/$defs/test"},
                    {"$ref": "#/$defs/test2"},
                ]
            },
            "$defs": {
                "test": {
                    "properties": {
                        "abc": {"type": "string"}
                    },
                    "required": ["abc"]
                },
                "test2": {
                    "properties": {
                        "xyz": {"type": "string"}
                    },
                    "required": ['xyz']
                }
            }
        }
        self.check(schema)

    def test_if(self):
        schema = {
            "if": {
                "properties": {
                    "a": {"const": "x"}
                }
            },
            "then": {
                "properties": {
                    "b": {"const": "y"}
                }
            },
            "else": {
                "properties": {
                    "b": {"const": "z"}
                }
            }
        }
        self.check(schema, strict_invalid=False)


class AasTest(TestGenerateBase):

    def test_constraint_aasd_014(self):
        schema = {
            "properties": {
                "globalAssetId": {"type": "string"},
                "specificAssetIds": {"type": "array"},
            },
            "if": {
                "properties": {
                    "entityType": {
                        "const": "SelfManagedEntity"
                    }
                },
                "required": ["entityType"]
            },
            "then": {
                "anyOf": [
                    {
                        "required": ["globalAssetId"],
                        "not": {
                            "required": ["specificAssetIds"]
                        }
                    },
                    {
                        "required": ["specificAssetIds"],
                        "not": {
                            "required": ["globalAssetId"]
                        }
                    }
                ]
            },
            "else": {
                "not": {
                    "required": ["globalAssetId", "specificAssetId"]
                }
            }
        }
        self.check(schema, strict_invalid=False)

    def test_aas(self):
        with open(os.path.join(SCRIPT_DIR, '..', 'fixtures', 'json', 'aas_small.yaml')) as file:
            schema = yaml.safe_load(file)
        schema = normalize.normalize(schema, False)
        schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
        config = parse.default_config()
        config.normalize = False
        graph = parse.parse(schema)
        check_consistency(graph)
        num_samples = 0
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            # validator = Draft202012Validator(schema)
            # if i.is_valid:
            #     validator.validate(sample)
            num_samples += 1
        print(f"Generated {num_samples} samples")
