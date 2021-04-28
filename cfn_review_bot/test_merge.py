import unittest

from .loader import OpaqueTagMapping, OpaqueTagScalar, OpaqueTagSequence
from .merge import deep_merge


class TestDeepMerge(unittest.TestCase):
    def test_merging_equal_strings_is_a_noop(self):
        old = 'same string'
        self.assertEqual(deep_merge(old, old), old)

    def test_merging_different_strings_raises_an_exception(self):
        old = 'some string'
        new = 'other string'

        with self.assertRaises(Exception) as cm:
            deep_merge(old, new)

        self.assertEqual(str(cm.exception), f'Unable to merge {old} with {new}')

    def test_merging_lists_joins_them_together(self):
        old = [1, 2, 3]
        new = ['A', 'B', 'C']

        self.assertEqual(deep_merge(old, new), old + new)

    def test_merging_dictionaries_goes_deep(self):
        old = {'a': 1, 'c': {'d': 3}}
        new = {'b': 2, 'c': {'e': 4}}

        self.assertEqual(
            deep_merge(old, new),
            {
                'a': 1,
                'b': 2,
                'c': {
                    'd': 3,
                    'e': 4,
                },
            },
        )

    def assertCannotMerge(self, lhs, rhs):
        with self.assertRaises(Exception) as cm:
            deep_merge(lhs, rhs)

        self.assertEqual(str(cm.exception), f'Unable to merge {lhs} with {rhs}')

    def test_merging_opaque_mappings_checks_equality(self):
        map1 = OpaqueTagMapping('map-tag', dict(a=1, b=2, c=3))
        map2 = OpaqueTagMapping('map-tag', dict(a=1, b=2, c=3))
        map3 = OpaqueTagMapping('map-tag2', dict(a=1, b=2, c=3))
        map4 = OpaqueTagMapping('map-tag', dict(a=1, b=2))

        self.assertEqual(deep_merge(map1, map2), map1)
        self.assertCannotMerge(map1, map3)
        self.assertCannotMerge(map1, map4)

    def test_merging_opaque_sequences_checks_equality(self):
        lst1 = OpaqueTagSequence('sequence-tag', list((1, 2, 3)))
        lst2 = OpaqueTagSequence('sequence-tag', list((1, 2, 3)))
        lst3 = OpaqueTagSequence('sequence-tag2', list((1, 2, 3)))
        lst4 = OpaqueTagSequence('sequence-tag', list((1, 2)))

        self.assertEqual(deep_merge(lst1, lst2), lst1)
        self.assertCannotMerge(lst1, lst3)
        self.assertCannotMerge(lst1, lst4)

    def test_merging_opaque_scalars_checks_equality(self):
        scl1 = OpaqueTagScalar('scalar-tag', 43)
        scl2 = OpaqueTagScalar('scalar-tag', 43)
        scl3 = OpaqueTagScalar('scalar-tag2', 43)
        scl4 = OpaqueTagScalar('scalar-tag', 44)

        self.assertEqual(deep_merge(scl1, scl2), scl1)
        self.assertCannotMerge(scl1, scl3)
        self.assertCannotMerge(scl1, scl4)

    def test_merging_opaque_values_checks_the_value_type(self):
        map1 = OpaqueTagMapping(None, None)
        scl1 = OpaqueTagScalar(None, None)
        lst1 = OpaqueTagSequence(None, None)

        self.assertCannotMerge(map1, lst1)
        self.assertCannotMerge(lst1, scl1)
        self.assertCannotMerge(scl1, map1)
