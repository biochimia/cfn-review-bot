import unittest

from .stack import StackSchema


class TestStackSchema(unittest.TestCase):
    def test_parameter_str_value_is_left_unchanged(self):
        self.assertEqual(
          StackSchema.validate({
            'template': 'some-template',
            'parameter': {'a': 'foo'},
          }),
          {
            'template': ['some-template'],
            'parameter': {'a': 'foo'},
            'capability': [],
            'tag': {},
          },
        )

    def test_parameter_int_value_is_converted_to_string(self):
        self.assertEqual(
          StackSchema.validate({
            'template': 'some-template',
            'parameter': {'a': 0, 'b': 1},
          }),
          {
            'template': ['some-template'],
            'parameter': {'a': '0', 'b': '1'},
            'capability': [],
            'tag': {},
          },
        )

    def test_parameter_bool_value_is_converted_to_string(self):
        self.assertEqual(
          StackSchema.validate({
            'template': 'some-template',
            'parameter': {'a': True, 'b': False},
          }),
          {
            'template': ['some-template'],
            'parameter': {'a': 'true', 'b': 'false'},
            'capability': [],
            'tag': {},
          },
        )

    def test_parameter_list_is_converted_to_string(self):
        self.assertEqual(
          StackSchema.validate({
            'template': 'some-template',
            'parameter': {'a': ['foo', 'bar', 'baz']},
          }),
          {
            'template': ['some-template'],
            'parameter': {'a': 'foo,bar,baz'},
            'capability': [],
            'tag': {},
          },
        )

    def test_parameter_int_list_is_converted_to_string(self):
        self.assertEqual(
          StackSchema.validate({
            'template': 'some-template',
            'parameter': {'a': [0, 1, 2, 3]},
          }),
          {
            'template': ['some-template'],
            'parameter': {'a': '0,1,2,3'},
            'capability': [],
            'tag': {},
          },
        )

    def test_parameter_bool_list_is_converted_to_string(self):
        self.assertEqual(
          StackSchema.validate({
            'template': 'some-template',
            'parameter': {'a': [True, False, False, True]},
          }),
          {
            'template': ['some-template'],
            'parameter': {'a': 'true,false,false,true'},
            'capability': [],
            'tag': {},
          },
        )
