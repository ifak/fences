from unittest import TestCase
from fences.open_api.open_api import ParameterStyle, Parameter, ParameterPosition
from fences.open_api.format import format_parameter_value


class StyleSimpleTest(TestCase):

    def format(self, value: any, explode: bool) -> str:
        param = Parameter(
            name='my_param',
            position=ParameterPosition.QUERY,
            required=False,
            style=ParameterStyle.SIMPLE,
            explode=explode,
            schema={}
        )
        result = format_parameter_value(param, value)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 'my_param')
        return result[0][1]

    def test_string(self):
        value = self.format('foo', False)
        self.assertEqual(value, "foo")
        value = self.format('foo', True)
        self.assertEqual(value, "foo")

    def test_list(self):
        value = self.format(["blue", "black", "brown"], False)
        self.assertEqual(value, "blue,black,brown")
        value = self.format(["blue", "black", "brown"], True)
        self.assertEqual(value, "blue,black,brown")

    def test_object(self):
        obj = {"R": 100, "G": 200, "B": 150}
        value = self.format(obj, False)
        self.assertEqual(value, 'R,100,G,200,B,150')
        value = self.format(obj, True)
        self.assertEqual(value, 'R=100,G=200,B=150')


class StyleFormTest(TestCase):

    def format_raw(self, value: any, explode: bool) -> str:
        param = Parameter(
            name='my_param',
            position=ParameterPosition.QUERY,
            required=False,
            style=ParameterStyle.FORM,
            explode=explode,
            schema={}
        )
        return format_parameter_value(param, value)

    def format(self, value: any, explode: bool) -> str:
        result = self.format_raw(value, explode)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 'my_param')
        return result[0][1]

    def test_string(self):
        result = self.format('blue', False)
        self.assertEqual(result, 'blue')
        result = self.format('blue', True)
        self.assertEqual(result, 'blue')

    def test_list(self):
        arr = ["blue", "black", "brown"]
        result = self.format(arr, False)
        self.assertEqual(result, 'blue,black,brown')
        result = self.format_raw(arr, True)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0][0], 'my_param')
        self.assertEqual(result[1][0], 'my_param')
        self.assertEqual(result[2][0], 'my_param')
        self.assertEqual(result[0][1], 'blue')
        self.assertEqual(result[1][1], 'black')
        self.assertEqual(result[2][1], 'brown')

    def test_object(self):
        obj = {"R": 100, "G": 200, "B": 150}
        result = self.format(obj, False)
        self.assertEqual(result, 'R,100,G,200,B,150')
        result = self.format_raw(obj, True)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0][0], 'R')
        self.assertEqual(result[1][0], 'G')
        self.assertEqual(result[2][0], 'B')
        self.assertEqual(result[0][1], '100')
        self.assertEqual(result[1][1], '200')
        self.assertEqual(result[2][1], '150')
