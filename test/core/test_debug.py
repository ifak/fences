from unittest import TestCase
from fences.core.node import NoOpDecision, NoOpLeaf, IncomingTransition, OutgoingTransition
from fences.core.debug import check_consistency, ConsistencyException

class CheckTest(TestCase):

    def test_invalid_outgoing_idx(self):
        child = NoOpLeaf(None, True)
        root = NoOpDecision(None)
        child.incoming_transitions.append( IncomingTransition(root, 1) )
        root.outgoing_transitions.append( OutgoingTransition(child, False) )
        with self.assertRaises(ConsistencyException):
            check_consistency(child)
        child.incoming_transitions[0].outgoing_idx = 0
        check_consistency(child)

    def test_source_not_decision(self):
        dummy = NoOpLeaf(None, True)
        child = NoOpLeaf(None, True)
        root = NoOpDecision(None)
        child.incoming_transitions.append( IncomingTransition(dummy, 0) )
        root.outgoing_transitions.append( OutgoingTransition(child, False) )
        with self.assertRaises(ConsistencyException):
            check_consistency(child)
        child.incoming_transitions[0].source = root
        check_consistency(child)

    def test_invalid_target(self):
        dummy = NoOpDecision(None)
        child = NoOpLeaf(None, True)
        root = NoOpDecision(None)
        child.incoming_transitions.append( IncomingTransition(root, 0) )
        root.outgoing_transitions.append( OutgoingTransition(dummy, False) )
        with self.assertRaises(ConsistencyException):
            check_consistency(child)
        root.outgoing_transitions[0].target = child
        check_consistency(child)

    def test_invalid_index(self):
        child = NoOpLeaf(None, True)
        root = NoOpDecision(None)
        child.incoming_transitions.append( IncomingTransition(root, 1) )
        root.outgoing_transitions.append( OutgoingTransition(child, False ))
        with self.assertRaises(ConsistencyException):
            check_consistency(root)
        child.incoming_transitions[0].outgoing_idx = 0
        check_consistency(root)

    def test_no_matching_incoming(self):
        child = NoOpLeaf(None, True)
        root = NoOpDecision(None)
        root.outgoing_transitions.append( OutgoingTransition(child, False) )
        with self.assertRaises(ConsistencyException):
            check_consistency(root)
        child.incoming_transitions.append( IncomingTransition(root, 0) )
        check_consistency(root)

    def test_duplicate_id(self):
        root = NoOpDecision('x')
        child = NoOpLeaf('x', True)
        root.add_transition(child)
        root.add_transition(child)
