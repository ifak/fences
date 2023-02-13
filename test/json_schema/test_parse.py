from unittest import TestCase
from fences.json_schema.parse import parse
from fences.json_schema.exceptions import ParseException

class ParseTest(TestCase):

    def test_empty(self):
        with self.assertRaises(ParseException):
            parse({})