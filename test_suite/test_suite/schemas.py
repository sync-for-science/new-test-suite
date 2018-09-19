patient_argonaut = {
  'type': 'object',
  'properties': {
    'identifier': {
      'minItems': 1,
      'items': {
        'required': ['system', 'value']
      }
    },
    'name': {
      'minItems': 1,
      'items': {
        'required': ['family', 'given']
      }
    },
    'gender': {
      'enum': ['male', 'female', 'other', 'unknown']
    }
  },
  'required': ['identifier', 'name', 'gender']
}


patient_cms = {
  'type': 'object',
  'properties': {
    'identifier': {
      'minItems': 1,
      'items': {
        'required': ['system', 'value']
      }
    },
    'name': {
      'minItems': 1,
      'maxItems': 1,
      'items': {
        'required': ['family', 'given', 'use']
      }
    },
    'gender': {
      'enum': ['male', 'female', 'other']
    },
  },
  'required': ['identifier', 'name', 'gender', 'address']
}
