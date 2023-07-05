from unittest import TestCase
from fences.json_schema.json_pointer import JsonPointer
from fences.core.exception import JsonPointerException


class AddTest(TestCase):

    def test_add_string(self):
        p = JsonPointer()
        p = p + 'x'
        self.assertEqual(len(p.elements), 1)
        self.assertIn('x', p.elements)

    def test_add_int(self):
        p = JsonPointer()
        p = p + 42
        self.assertEqual(len(p.elements), 1)
        self.assertIn('42', p.elements)

    def test_add_invalid(self):
        p = JsonPointer()
        with self.assertRaises(Exception):
            p = p + None


class IsRootTest(TestCase):

    def test_empty(self):
        p = JsonPointer()
        self.assertTrue(p.is_root())

    def test_non_empty(self):
        p = JsonPointer(['1'])
        self.assertFalse(p.is_root())


class FromStringTest(TestCase):

    def test_empty(self):
        s = JsonPointer.from_string('#/')
        self.assertTrue(s.is_root())

    def test_non_empty(self):
        s = JsonPointer.from_string('#/a/1/c')
        self.assertEqual(len(s.elements), 3)
        self.assertEqual(s.elements[0], 'a')
        self.assertEqual(s.elements[1], '1')
        self.assertEqual(s.elements[2], 'c')

    def test_invalid(self):
        with self.assertRaises(JsonPointerException):
            JsonPointer.from_string('')
        with self.assertRaises(JsonPointerException):
            JsonPointer.from_string('12')


class LookupTest(TestCase):

    def test_empty(self):
        d = JsonPointer().lookup("foo")
        self.assertEqual(d, "foo")

    def test_object(self):
        d = JsonPointer(['a', 'b']).lookup({'a': {'b': 'foo'}})
        self.assertEqual(d, "foo")

    def test_array(self):
        d = JsonPointer(['0', '1']).lookup([['bar', 'foo']])
        self.assertEqual(d, "foo")

    def test_too_short(self):
        with self.assertRaises(JsonPointerException):
            JsonPointer(['a', 'b']).lookup({})
        with self.assertRaises(JsonPointerException):
            JsonPointer(['0', '0']).lookup([])

    def test_cannot_lookup(self):
        with self.assertRaises(JsonPointerException):
            JsonPointer(['0']).lookup("FOO")
        with self.assertRaises(JsonPointerException):
            JsonPointer(['foo']).lookup([])
