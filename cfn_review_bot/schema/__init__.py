import schema


schema.Schema._prepend_schema_name = \
    lambda s, m: f'{s._name}: {m}' if s._name else m
