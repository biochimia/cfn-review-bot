from schema import And, Or, Use


def Any(data):
  return True

def OneOrMany(schema):
  return Or(And(schema, Use(lambda x: [x])), [schema])
