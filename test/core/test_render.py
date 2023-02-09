from unittest import TestCase

from fences.core.node import NoOpDecision, NoOpLeaf, Reference
from fences.core.render import render

class RenderTest(TestCase):

    def test_empty(self):
        render(NoOpDecision(None))

    def test_success(self):
        root = NoOpDecision('root')
        child = NoOpDecision(None)
        leaf = NoOpLeaf(None, True)
        ref = Reference('foo', 'bar')
        root.add_transition(child)
        child.add_transition(leaf)
        child.add_transition(ref)
        render(root)
