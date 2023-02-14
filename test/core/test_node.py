from unittest import TestCase
from fences.core.exception import ResolveReferenceException
from fences.core.node import NoOpDecision, NoOpLeaf, Reference, Leaf, Decision
from fences.core.debug import check_consistency

class ItemsTest(TestCase):
    def test_empty(self):
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
        check_consistency(root)

    def test_root_is_ref(self):
        root = Reference('1', '2')
        child = NoOpLeaf('2', True)
        new_root = root.resolve([child])
        self.assertIs(new_root, child)
        check_consistency(root)

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
        check_consistency(root)

class MockLeaf(Leaf):

    def __init__(self, id: str, is_valid: bool) -> None:
        super().__init__(id, is_valid)
        self.count = 0

    def apply(self, data: any) -> any:
        self.count += 1
        return data

class MockDecision(Decision):

    def __init__(self, id: str, all_transitions: bool) -> None:
        super().__init__(id, all_transitions)
        self.count = 0

    def apply(self, data: any) -> any:
        self.count += 1
        return data

class GeneratePathsTest(TestCase):

    def test_one_node(self):
        node = MockLeaf('no-id', True)
        paths = list(node.generate_paths())
        self.assertEqual(len(paths), 1)
        node.execute(paths[0].path)
        self.assertEqual(node.count, 1)

    def test_or_decision(self):
        root = MockDecision('root', False)
        node1 = MockLeaf('leaf1', True)
        node2 = MockLeaf('leaf2', False)
        root.add_transition(node1)
        root.add_transition(node2)
        paths = list(root.generate_paths())
        self.assertEqual(len(paths), 2)
        for i in paths:
            root.execute(i.path)
        self.assertEqual(root.count, 2)
        self.assertEqual(node1.count, 1)
        self.assertEqual(node2.count, 1)
    
    def test_and_decision(self):
        root = MockDecision('root', True)
        node1 = MockLeaf('leaf1', True)
        node2 = MockLeaf('leaf2', True)
        root.add_transition(node1)
        root.add_transition(node2)
        paths = list(root.generate_paths())
        self.assertEqual(len(paths), 1)
        root.execute(paths[0].path)
        self.assertEqual(root.count, 1)
        self.assertEqual(node1.count, 1)
        self.assertEqual(node2.count, 1)
