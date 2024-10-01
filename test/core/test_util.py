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
            ['a', 'b00'],
            ['c00', 'd'],
        ]
        self.check(table)

    def test_different_lengths(self):
        table = [
            ['a00', 'b'],
            ['c', 'd00', 'e'],
            ['f00000'],
        ]
        self.check(table)

    def test_delimiters(self):
        table = [
            ['a', 'b00'],
            None,
            ['c00', 'd'],
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

    def test_add(self):
        c1 = ConfusionMatrix()
        c1.valid_accepted = 2
        c1.valid_rejected = 3
        c1.invalid_accepted = 7
        c1.invalid_rejected = 11

        c2 = ConfusionMatrix()
        c2.valid_accepted = 19
        c2.valid_rejected = 24
        c2.invalid_accepted = 33
        c2.invalid_rejected = 45

        sum = c1 + c2
        self.assertEqual(sum.valid_accepted, 2+19)
        self.assertEqual(sum.valid_rejected, 3+24)
        self.assertEqual(sum.invalid_accepted, 7+33)
        self.assertEqual(sum.invalid_rejected, 11+45)

    def test_iadd(self):
        c1 = ConfusionMatrix()
        c1.valid_accepted = 2
        c1.valid_rejected = 3
        c1.invalid_accepted = 7
        c1.invalid_rejected = 11

        c2 = ConfusionMatrix()
        c2.valid_accepted = 19
        c2.valid_rejected = 24
        c2.invalid_accepted = 33
        c2.invalid_rejected = 45

        c1 += c2
        self.assertEqual(c1.valid_accepted, 2+19)
        self.assertEqual(c1.valid_rejected, 3+24)
        self.assertEqual(c1.invalid_accepted, 7+33)
        self.assertEqual(c1.invalid_rejected, 11+45)

        # c2 not touched
        self.assertEqual(c2.valid_accepted, 19)
        self.assertEqual(c2.valid_rejected, 24)
        self.assertEqual(c2.invalid_accepted, 33)
        self.assertEqual(c2.invalid_rejected, 45)

    def test_accuracy(self):
        c = ConfusionMatrix()
        c.valid_accepted = 2
        c.valid_rejected = 3
        c.invalid_accepted = 7
        c.invalid_rejected = 11
        self.assertAlmostEqual(c.accuracy(), 13/23)

    def test_balanced_accuracy(self):
        c = ConfusionMatrix()
        c.valid_accepted = 2
        c.valid_rejected = 3
        c.invalid_accepted = 7
        c.invalid_rejected = 11
        self.assertAlmostEqual(c.balanced_accuracy(), ((2/5) + (11/18)) / 2)
