patient_argonaut = {
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

allergies_argonaut = {
    'oneOf': [
        {'required': ['status', 'substance']},  # DSTU2???
        {'required': ['code']}  # STU3???
    ]
}

immunization_argonaut = {
    'required': ['date']
}

lab_results_argonaut = {
    'properties': {
        'category': {
            'contains': {
                'properties': {
                    'coding': {
                        'const': [{
                            'system': 'http://hl7.org/fhir/observation-category',
                            'code': 'laboratory'
                        }]
                    }
                },
                'required': ['coding']
            }
        }
    },
    'required': ['category', 'subject'],
    'oneOf': [
        {'required': ['valueQuantity']},
        {'required': ['valueCodeableConcept']},
        {'required': ['valueString']},
        {'required': ['valueRange']},
        {'required': ['valueRatio']},
        {'required': ['valueSampleData']},
        {'required': ['valueAttachment']},
        {'required': ['valueTime']},
        {'required': ['valueDateTime']},
        {'required': ['valuePeriod']},
        {'required': ['dataAbsentReason']}
    ]
}

medication_order_argonaut = {
    'required': ['dateWritten', 'status', 'patient', 'prescriber'],
    'oneOf': [
        {'required': ['medicationCodeableConcept']},
        {'required': ['medicationReference']}
    ]
}

medication_request_argonaut = medication_order_argonaut

medication_statement_argonaut = {
    'required': ['dateAsserted'],
    'oneOf': [
        {'required': ['medicationCodableConcept']},
        {'required': ['medicationReference']}
    ]
}

patient_documents_argonaut = {
    'properties': {
        'content': {
            'properties': {
                'attachment': {
                    'required': ['contentType', 'url']
                }
            },
            'required': ['format']
        }
    },
    'required': ['subject']
}

problems_argonaut = {
    'required': ['category'],
    'oneOf': [
        {
            'properties': {'verificationStatus': {'const': 'entered-in-error'}},
            'not': {'required': ['clinicalStatus']}
        },
        {
            'not': {'properties': {'verificationStatus': {'const': 'entered-in-error'}}},
            'required': ['clinicalStatus']
        }
    ]
}

procedures_argonaut = {
    'oneOf': [
        {'required': ['performedDateTime']},
        {'required': ['performedPeriod']}
    ]
}

smoking_status_argonaut = {
    'properties': {
        'code': {
            'properties': {
                'coding': {
                    'const': [{
                        'system': 'http://loinc.org',
                        'code': '72166-2'
                    }]
                }
            },
            'required': ['coding']
        }
    },
    'required': ['subject', 'issued', 'valueCodeableConcept']
}

vital_signs_argonaut = {
    'properties': {
        'category': {
            'minItems': 1,
            'maxItems': 1,
            'contains': {
                'properties': {
                    'coding': {
                        'const': [{
                            'system': 'http://hl7.org/fhir/observation-category',
                            'code': 'vital-signs'
                        }]
                    }
                },
                'required': ['coding']
            }
        },
        'related': {
            'items': {
                'properties': {
                    'type': {'const': 'has-member'}
                }
            }
        },
        'component': {
            'items': {
                'properties': {
                    'valueQuantity': {
                        'required': ['value']
                    }
                },
                'oneOf': [
                    {'required': ['valueQuantity']},
                    {'required': ['dataAbsentReason']}
                ]
            }
        },
        'valueQuantity': {
            'required': ['value']
        }
    },
    'required': ['subject',],
    'oneOf': [  # yuck
        {'required': ['effectiveDateTime', 'valueQuantity']},
        {'required': ['effectiveDateTime', 'dataAbsentReason']},
        {'required': ['effectivePeriod', 'valueQuantity']},
        {'required': ['effectivePeriod', 'dataAbsentReason']}
    ]
}
