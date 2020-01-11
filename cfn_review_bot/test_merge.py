import unittest

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
