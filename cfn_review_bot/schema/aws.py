'''
AWS-specific types for use in schema definitions.
'''

import schema


AccountId = schema.Regex(r'^\d+$')
Region = schema.Regex(r'^[a-z]+(-[a-z]+)+-\d+$')
