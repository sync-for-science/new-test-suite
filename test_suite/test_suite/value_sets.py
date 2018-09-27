class ValueSet:
    def __init__(self, name, uri, codings):
        self.name = name
        self.uri = uri
        self.codings = codings

    def contains(self, code, system=None):
        if not system:
            return any(code in code_set for code_set in self.codings.values())
        return (code in self.codings.get(system, set()))


administrative_gender = ValueSet(
    'Administrative gender',
    'http://hl7.org/fhir/ValueSet/administrative-gender',
    {'http://hl7.org/fhir/administrative-gender': {'xmale', 'xfemale', 'xother', 'xunknown'}}
)


marital_status = ValueSet(
    'Marital status',
    'http://hl7.org/fhir/ValueSet/marital-status',
    {
        'http://hl7.org/fhir/marital-status': {'U'},
        'http://hl7.org/fhir/v3/MaritalStatus': {'A', 'D', 'I', 'L', 'M', 'P', 'S', 'T', 'W'},
        'http://hl7.org/fhir/v3/NullFlavor': {'UNK'}
    }
)


patient_contact_relationship = ValueSet(
    'Patient-contact relationship',
    'http://hl7.org/fhir/ValueSet/patient-contact-relationship',
    {'http://hl7.org/fhir/patient-contact-relationship': {'emergency', 'family', 'guardian', 'friend', 'partner', 'work', 'caregiver', 'agent', 'guarantor', 'owner', 'parent'}}
)


# oh dear
language = ValueSet(
    'Language',
    'https://tools.ietf.org/html/bcp47',
    {'https://tools.ietf.org/html/bcp47': {}}
)


link_type = ValueSet(
    'Link type',
    'http://hl7.org/fhir/ValueSet/link-type',
    {'http://hl7.org/fhir/link-type': {'replace', 'refer', 'seealso'}}
)
