from fences.open_api.generate import parse, TestCase
from fences.core.render import render

import unittest
import os
import yaml

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class GenerateTestCase(unittest.TestCase):

    def check(self, schema, debug=False):
        graph = parse(schema)
        if debug:
            render(graph).write_svg('graph.svg')

        for i in graph.generate_paths():
            test_case: TestCase = graph.execute(i.path)
            request = test_case.to_request()
            if debug:
                request.dump()

    def test_simple(self):
        schema = {
            'info': {
                'title': 'a'
            },
            'paths': {
                '/test/{foo}': {
                    'get': {
                        'operationId': 'testOp',
                        'parameters': [{
                            'name': 'foo',
                            'in': 'path',
                            'schema': {
                                'enum': ['a', 'b']
                            }
                        }, {
                            'name': 'foo',
                            'in': 'query',
                            'schema': {
                                'minLength': 10
                            }
                        }, {
                            'name': 'bar',
                            'in': 'query',
                            'schema': {'type': 'number'}
                        }],
                        'requestBody': {
                            'content': {
                                'application/json': {
                                    'schema': {
                                        'const': 'foo'
                                    }
                                }
                            }
                        },
                        'responses': {}
                    }
                }
            },
            'components': {}
        }
        self.check(schema)

    def test_aas(self):
        with open(os.path.join(SCRIPT_DIR, '..', 'fixtures', 'open_api', 'aas.yml')) as file:
            schema = yaml.safe_load(file)
        self.check(schema)
