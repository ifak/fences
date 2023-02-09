from unittest import TestCase
from fences.core.exception import ResolveReferenceException
from fences.core.node import NoOpDecision, NoOpLeaf, Reference


class ItemsTest(TestCase):
    def _test_empty(self):
        root = NoOpDecision(None)
        items = [i for i in root.items()]
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0] is root)

    def test_cycle(self):
        root = NoOpDecision('1')
        child1 = NoOpDecision('2')
        child2 = NoOpDecision('3')

        root.add_transition(child1)
        child1.add_transition(child2)
        child2.add_transition(root)

        leaf = NoOpLeaf('x', True)
        child1.add_transition(leaf)
        child2.add_transition(leaf)

        items = [i for i in root.items()]
        self.assertEqual(len(items), 4)
        self.assertIn(root, items)
        self.assertIn(child1, items)
        self.assertIn(child2, items)
        self.assertIn(leaf, items)


class ResolveTest(TestCase):

    def test_empty(self):
        root = NoOpDecision('1')
        new_node = root.resolve([])
        self.assertIs(new_node, root)

    def test_root_is_ref(self):
        root = Reference('1', '2')
        child = NoOpLeaf('2', True)
        new_root = root.resolve([child])
        self.assertIs(new_root, child)

    def test_id_not_exists(self):
        root = Reference('1', 'invalid_ref')
        child = NoOpLeaf('2', True)
        with self.assertRaises(ResolveReferenceException):
            root.resolve([child])

    def test_duplicate_id(self):
        root = NoOpDecision('1')
        child = NoOpDecision('1')
        with self.assertRaises(ResolveReferenceException):
            root.resolve([child])

    def test_success(self):
        root = Reference('1', '2')
        subroot = NoOpDecision('2')
        leaf = NoOpLeaf(None, True)
        subroot.add_transition(leaf)
        new_root = root.resolve([subroot])
        self.assertIs(new_root, subroot)
