from fences.core.random import generate_random_string, StringProperties, generate_random_number
from fences.core.exception import FencesException

from unittest import TestCase


class GenerateStringTest(TestCase):

    def check(self, value: str, props: StringProperties):
        self.assertTrue(len(value) >= props.min_length)
        if props.max_length is not None:
            self.assertTrue(len(value) <= props.max_length)
        if props.pattern:
            self.assertRegex(value, props.pattern)

    def test_no_constraint(self):
        props = StringProperties()
        value = generate_random_string(props)
        self.check(value, props)

    def test_min_length(self):
        props = StringProperties(min_length=10)
        value = generate_random_string(props)
        self.check(value, props)

    def test_max_length(self):
        props = StringProperties(max_length=10)
        value = generate_random_string(props)
        self.check(value, props)

    def test_interval(self):
        props = StringProperties(min_length=10, max_length=20)
        value = generate_random_string(props)
        self.check(value, props)

    def test_pattern(self):
        props = StringProperties(pattern="a+")
        value = generate_random_string(props)
        self.check(value, props)

    def test_pattern_with_min_length(self):
        props = StringProperties(pattern="a+", min_length=30)
        value = generate_random_string(props)
        self.check(value, props)

    def test_impossible(self):
        props = StringProperties(pattern="(aaa)+", max_length=2)
        with self.assertRaises(FencesException):
            generate_random_string(props)


class GenerateNumberTest(TestCase):

    def check(self, min_value, max_value):
        n = generate_random_number(min_value, max_value)
        if min_value:
            self.assertGreaterEqual(n, min_value)
        if max_value:
            self.assertLessEqual(n, max_value)

    def test_simple(self):
        self.check(None, None)

    def test_min(self):
        self.check(10, None)

    def test_max(self):
        self.check(None, 100)

    def test_interval(self):
        self.check(10, 20)
    
    def test_trivial_interval(self):
        self.check(12, 12)
