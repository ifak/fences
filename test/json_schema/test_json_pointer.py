from unittest import TestCase
from fences.json_schema.json_pointer import JsonPointer

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