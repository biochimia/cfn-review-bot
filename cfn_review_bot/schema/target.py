'''
Schema for deployment target configuration.


A deployment target is typically an account/region combination. Multiple targets
may be referenced by a single name.
'''

import schema

from . import aws
from . import util


LoginUrlSchema = schema.Schema(schema.Or(
    bool,             # show / hide login URL
    str,              # fixed user-defined URL
    schema.Schema({   # switch role URL
        'account': str,
        'role-name': str,
        schema.Optional('display-name'): str,
        schema.Optional('color'): str,
    }),
))

SingleTargetSchema = schema.Schema({
    schema.Optional('account-id'): aws.AccountId,
    schema.Optional('role-name'): schema.Or(None, str),
    schema.Optional('login-url'): LoginUrlSchema,
    schema.Optional('region'): util.OneOrMany(aws.Region),
    schema.Optional('tag', default={}): {str: str},
})

TargetConfigSchema = schema.Schema({
    schema.Optional('default', default=[]): util.OneOrMany(str),
    schema.Optional('account-id'): aws.AccountId,
    schema.Optional('role-name'): schema.Or(None, str),
    schema.Optional('login-url', default=True): LoginUrlSchema,
    schema.Optional('region', default=[]): util.OneOrMany(aws.Region),
    schema.Optional('tag', default={}): {str: str},
    schema.Optional('target', default={}): {
        str: util.OneOrMany(SingleTargetSchema),
    },
    schema.Optional('stack-root', default='./stack'): str,
    schema.Optional('template-root', default='./template'): str,
}, name='Target Configuration')
