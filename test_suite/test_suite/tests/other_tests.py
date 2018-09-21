from urllib.parse import urlparse

from test_suite.tests.core import BaseTest, FAIL, PASS, SKIP, WARN, register


class S4STestBase(BaseTest):
    use_cases = ('EHR',)

    # override these
    slug = ''
    medication_resources = ()

    def run(self):
        supported_resource_types = {
            r['type']
            for r in self.conformance['rest'][0]['resource']
        }

        must_support_resources = [
            ('Patient demographics', 'Patient'),
            ('Smoking status', 'Observation'),
            ('Problems', 'Condition'),
            ('Allergies and intolerances', 'AllergyIntolerance'),
            ('Lab results', 'Observation'),
            ('Vital signs', 'Observation'),
            ('Procedures', 'Procedure'),
            ('Immunizations', 'Immunization'),
            ('Patient documents', 'DocumentReference'),
        ]

        for label, resource_type in must_support_resources:
            if resource_type in supported_resource_types:
                result = (None, PASS)
            else:
                result = (f'The server must support the {resource_type} resource type', FAIL)
            self.results[f'Server implements {label}'] = result

        if any(
                medication_resource_type in supported_resource_types
                for medication_resource_type in self.medication_resources
        ):
            result = (None, PASS)
        else:
            result = (f'The server must support at least one of {", ".join(self.medication_resources)}', FAIL)
        self.results['Server implements Medications'] = result


        try:
            conformance_uris = {
                ex['url']: ex['valueUri']
                for ex in self.conformance['rest'][0]['security']['extension'][0]['extension']
            }
            missing_endpoints = [
                endpoint
                for endpoint in ('authorize', 'token')
                if endpoint not in conformance_uris
            ]
            if missing_endpoints:
                result1 = (f'The conformance statement is missing the {" and ".join(missing_endpoints)} endpoint(s)', FAIL)
            else:
                result1 = (None, PASS)

            invalid_endpoints = [
                endpoint
                for endpoint in ('authorize', 'token')
                if endpoint not in missing_endpoints
                and not urlparse(conformance_uris[endpoint]).scheme
            ]
            if invalid_endpoints:
                result2 = (f'The {" and ".join(invalid_endpoints)} endpoint(s) are invalid', FAIL)
            else:
                result2 = (None, PASS)
        except (KeyError, IndexError):
            result1 = result2 = ('The conformance statement does not provide a `security` extension', FAIL)
        self.results['Conformance statement specifies the authorize and token endpoints'] = result1
        self.results['Conformance statement OAuth endpoints are valid'] = result2


@register
class S4STestDSTU2(S4STestBase):
    slug = 's4s-dstu2'
    versions = ('DSTU2',)
    medication_resources = ('MedicationOrder', 'MedicationStatement', 'MedicationDispense', 'MedicationAdministration')


@register
class S4STestSTU3(S4STestBase):
    slug = 's4s-stu3'
    versions = ('STU3',)
    medication_resources = ('MedicationRequest', 'MedicationStatement', 'MedicationDispense', 'MedicationAdministration')
