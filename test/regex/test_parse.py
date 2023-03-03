from fences.regex import parse
import unittest
import re

class TestParse(unittest.TestCase):

    def check(self, s):
        graph = parse.parse(s)
        for i in graph.items():
            i.description()
        regex = re.compile(s)
        for i in graph.generate_paths():
            s = graph.execute(i.path)
            if i.is_valid:
                self.assertTrue( regex.match(s) is not None, f"valid '{s}'" )
            else:
                self.assertTrue( regex.match(s) is None, f"invalid '{s}'" )

    def test_simple(self):
        simple = "(a)+b?c+d{1,2}"
        self.check(simple)

    def test_content_type(self):
        content_type = "^[-\w.]+/[-\w.]+$"
        self.check(content_type)

    def test_interval(self):
        interval = "-?(([1-9][0-9][0-9][0-9]+)|(0[0-9][0-9][0-9]))-((0[1-9])|(1[0-2]))-((0[1-9])|([12][0-9])|(3[01]))T(((([01][0-9])|(2[0-3])):[0-5][0-9]:([0-5][0-9])([0-9]+)?)|24:00:00(0+)?)Z"
        self.check(interval)
