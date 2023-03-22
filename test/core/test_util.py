from fences.core.util import ConfusionMatrix, render_table
from unittest import TestCase

class RenderTableTest(TestCase):

    def check(self, table):
        lines = render_table(table)
        self.assertEqual(len(table), len(lines))
        for idx, row in enumerate(table):
            if row:
                for cell in row:
                    self.assertIn(cell, lines[idx])

    def test_simple(self):
        table = [
            [ 'a', 'b00' ],
            [ 'c00', 'd' ],
        ]
        self.check(table)

    def test_different_lengths(self):
        table = [
            [ 'a00', 'b' ],
            [ 'c', 'd00', 'e' ],
            [ 'f00000' ],
        ]
        self.check(table)

    def test_delimiters(self):
        table = [
            [ 'a', 'b00' ],
            None,
            [ 'c00', 'd' ],
        ]
        self.check(table)

    def test_empty(self):
        table = []
        self.check(table)

    def test_only_delimiters(self):
        table = [None, None, None]
        self.check(table)

class ConfusionMatrixTest(TestCase):

    def test_simple(self):
        c = ConfusionMatrix()
        c.valid_accepted = 1
        c.valid_rejected = 20
        c.invalid_accepted = 300
        c.invalid_rejected = 4000
        print()
        c.print()
