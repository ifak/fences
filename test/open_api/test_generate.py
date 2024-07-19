from fences.open_api.generate import generate_all, Request, SampleCache
from fences.open_api.open_api import OpenApi
from fences.core.render import render

import unittest
import os
import yaml

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class GenerateTestCase(unittest.TestCase):

    def check(self, schema, debug=False):
        sample_cache = SampleCache()
        schema = OpenApi.from_dict(schema)
        for operation in schema.operations.values():
            graph = generate_all(operation, sample_cache)
            if debug:
                render(graph).write_svg(f'graph_{operation.operation_id}.svg')

            for i in graph.generate_paths():
                request: Request = graph.execute(i.path)
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
                                'type': 'string',
                                'enum': ['a', 'b']
                            }
                        }, {
                            'name': 'foo',
                            'in': 'query',
                            'schema': {
                                'type': 'string',
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
