from unittest import TestCase
from fences.core.exception import ResolveReferenceException, FencesException
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
        with self.assertRaises(ResolveReferenceException) as e:
            root.resolve([child])
            self.assertEqual(e.node_id, 'invalid_ref')

    def test_duplicate_id(self):
        root = NoOpDecision('1')
        child = NoOpDecision('1')
        with self.assertRaises(ResolveReferenceException) as e:
            root.resolve([child])
            self.assertEqual(e.node_id, '1')

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

    def test_no_valid_leaf(self):
        root = NoOpDecision('root', True)
        child1 = NoOpLeaf('child_1', False)
        child2 = NoOpLeaf('child_2', False)
        root.add_transition(child1)
        root.add_transition(child2)
        with self.assertRaises(FencesException):
            for _ in root.generate_paths(): pass

    def test_no_valid_leaf2(self):
        root = NoOpDecision('root', True)
        subroot1 = NoOpDecision('subroot1', False)
        subroot2 = NoOpDecision('subroot1', False)
        child11 = NoOpLeaf('child_11', False)
        child12 = NoOpLeaf('child_12', False)
        child21 = NoOpLeaf('child_21', False)
        child22 = NoOpLeaf('child_22', False)
        root.add_transition(subroot1)
        root.add_transition(subroot2)
        subroot1.add_transition(child11)
        subroot1.add_transition(child12)
        subroot2.add_transition(child21)
        subroot2.add_transition(child22)
        with self.assertRaises(FencesException):
            for _ in root.generate_paths(): pass

class OptimizeTest(TestCase):

    def test_do_nothing(self):
        root = MockDecision('root', False)
        child = MockLeaf('leaf', True)
        root.add_transition(child)
        self.assertEqual(len(list(root.items())), 2)
        root.optimize()
        self.assertEqual(len(list(root.items())), 2)

    def test_merge_many(self):
        root = MockDecision('root', False)
        n = root
        for _ in range(9):
            n.add_transition(NoOpDecision(None, True))
            n = n.outgoing_transitions[0].target
        child = MockLeaf('leaf', True)
        n.add_transition(child)
        self.assertEqual(len(list(root.items())), 2+9)
        root.optimize()
        self.assertEqual(len(list(root.items())), 2)
        self.assertTrue(root.all_transitions)
