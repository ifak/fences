from fences.xml_schema.xpath import NormalizedXPath
from unittest import TestCase
from xml.etree import ElementTree

class test_xpath(TestCase):

    def test_to_str(self):
        self.assertEqual(str(NormalizedXPath()), '/')
        self.assertEqual(str(NormalizedXPath([])), '/')
        self.assertEqual(str(NormalizedXPath([('a', 0), ('b', 1)])), '/a[0]/b[1]')

    def test_append(self):
        path = NormalizedXPath([('a', 0)]) + ('b', 10)
        self.assertEqual(str(path), '/a[0]/b[10]')

    def test_enumerate_with_path(self):
        tree = ElementTree.fromstring("""
            <a>
                <b x="1"></b>
                <b x="2"></b>
                <b x="3"></b>
            </a>
        """)
        root_path = NormalizedXPath([('a', 0)])
        paths = [i for i in root_path.enumerate(tree)]
        self.assertEqual(str(paths[0][0]), '/a[0]/b[0]')
        self.assertEqual(paths[0][1].attrib['x'], '1')
        self.assertEqual(str(paths[1][0]), '/a[0]/b[1]')
        self.assertEqual(paths[1][1].attrib['x'], '2')
        self.assertEqual(str(paths[2][0]), '/a[0]/b[2]')
        self.assertEqual(paths[2][1].attrib['x'], '3')
