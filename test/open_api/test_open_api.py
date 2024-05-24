from fences.open_api import open_api
from fences.open_api import exceptions
from unittest import TestCase


class TestOpenApi(TestCase):

    def test_empty(self):
        with self.assertRaises(exceptions.OpenApiException):
            open_api.OpenApi.from_dict({})

    def test_minimal(self):
        open_api.OpenApi.from_dict({
            'info': {
                'title': 'a'
            },
            'paths': {},
            'components': {}
        })

    def test_complete(self):
        open_api.OpenApi.from_dict({
            'info': {
                'title': 'a'
            },
            'paths': {
                '/test': {
                    'get': {
                        'operationId': 'testOp',
                        'responses': {}
                    }
                }
            },
            'components': {}
        })
