import json
import re

import jsonschema
import requests

from test_suite import schemas
from test_suite.tests.core import BaseTest, FAIL, PASS, SKIP, WARN, register


class ResourceTestMixin:
    """Mixin class for tests probing resources."""
    resource_type = None
    test_group = 1
    profiles = ()

    def __init__(self, **kwargs):
        self.token = kwargs.pop('bearer_token')
        self.patient_id = kwargs.pop('patient_id')
        super().__init__(**kwargs)

    def should_skip(self):
        skipped, reason = super().should_skip()
        if skipped:
            return skipped, reason

        supported_resource_types = [
            r['type']
            for r in self.conformance['rest'][0]['resource']
        ]

        resource_type = re.match(r'\w+', self.resource_type).group(0)
        if resource_type not in supported_resource_types:
            return (True, 'This resource type is not supported by the server')

        self.resource = self.get_resource()
        if not self.resource:
            return (True, 'The resource could not be fetched')

        return (False, '')

    def get_resource(self):
        if not self.resource_type:
            raise ValueError

        headers = {'Authorization': f'Bearer {self.token}'}
        resource_path = self.resource_type.format(patient_id=self.patient_id)
        return self.fetch_fhir_resource(resource_path, headers)

    def test_valid_fhir_resource(self):
        """Validate the resource with a HAPI FHIR server."""
        # TODO: use the reference stack's server
        uri = f'http://hapi.fhir.org/baseDstu{self.instance_version[-1]}/{self.resource["resourceType"]}/$validate'
        try:
            response = self.requester.post(uri, json=self.resource, headers={'Accept': 'application/json'})
            if 500 <= response.status_code < 600:
                raise Exception
        except:
            self.results[f'Resource is valid {self.instance_version} content'] = ('HAPI server unavailable or has errors', SKIP)
            return

        data = response.json()
        issues = [
            issue
            for issue in data.get('issue', list())
            if issue.get('severity') == 'error'
        ]

        if issues:
            message = f'These issues were reported:\n{json.dumps(issues, indent=2)}'
            result = FAIL
        else:
            message = None
            result = PASS

        self.results[f'Resource is valid {self.instance_version} content'] = (message, result)

    def test_resolvable_references(self):
        """Validate all the references in the resource."""
        failed_references = list()

        # TODO: replace with recursive reference finding
        reference = self.resource.get('reference')
        if reference:
            if reference.startswith('#'):
                matches = [
                    contained
                    for contained in self.resource.get('contained', list())
                    if contained['id'] == reference[1:]
                ]
                if not matches:
                    failed_references.append(reference)
            else:
                uri = f'{self.base_uri}/{reference}'
                try:
                    response = self.get_fetch_fhir_resource(uri, {'Authorization': f'Bearer {self.token}'})
                except requests.exceptions.HTTPError:
                    failed_references.append(reference)

        if failed_references:
            message = f'These references failed to resolve: {", ".join(failed_references)}'
            result = FAIL
        else:
            message = None
            result = PASS

        self.results['All references resolve'] = (message, result)

    def test_valid_codes(self):
        """Validate any codes in recognized systems."""
        # TODO: implement
        self.results['All codes are valid'] = (None, PASS)

    def test_profiles(self):
        """Validate the resource against any associated profile."""
        # TODO: add class attribute with a schema against which to validate
        for name, schema in self.profiles:
            validator = jsonschema.Draft4Validator(schema)
            errors = '; '.join(
                error.message
                for error in validator.iter_errors(self.resource)
            )
            if not errors:
                result = (None, PASS)
            else:
                result = (errors, WARN)
            self.results[f'Resources fulfill the {name} profile'] = result

    def run(self):
        self.test_valid_fhir_resource()
        self.test_resolvable_references()
        self.test_valid_codes()
        self.test_profiles()


@register
class PatientDemographicsTest(ResourceTestMixin, BaseTest):
    slug = 'patient-demographics'
    resource_type = 'Patient/{patient_id}'
    use_cases = ('EHR', 'Financial')
    profiles = (('Argonaut patient', schemas.patient_argonaut), ('CMS patient', schemas.patient_cms))

    def run(self):
        super().run()
        
        # check patient ID matches
        if self.resource['id'] != self.patient_id:
            result = ('Returned and queried patient IDs do not match', FAIL)
        else:
            result = (None, PASS)
        self.results['Returned patient ID matches queried patient ID'] = result


@register
class AllergiesAndIntoleranceTest(ResourceTestMixin, BaseTest):
    slug = 'allergies-and-intolerance'
    resource_type = 'AllergyIntolerance?patient={patient_id}'
    use_cases = ('EHR',)


@register
class CoverageTest(ResourceTestMixin, BaseTest):
    slug = 'coverage'
    resource_type = 'Coverage?beneficiary={patient_id}'
    versions = ('STU3',)
    use_cases = ('Financial',)


@register
class ExplanationOfBenefitTest(ResourceTestMixin, BaseTest):
    slug = 'explanation-of-benefit'
    resource_type = 'ExplanationOfBenefit?patient={patient_id}'
    versions = ('STU3',)
    use_cases = ('Financial',)


@register
class ImmunizationsTest(ResourceTestMixin, BaseTest):
    slug = 'immunizations'
    resource_type = 'Immunizations?patient={patient_id}'
    use_cases = ('EHR',)


@register
class LabResultsTest(ResourceTestMixin, BaseTest):
    slug = 'lab-results'
    resource_type = 'Observation?category=laboratory&patient={patient_id}'
    use_cases = ('EHR',)


@register
class MedicationAdministrationTest(ResourceTestMixin, BaseTest):
    slug = 'medication-administration'
    resource_type = 'MedicationAdministration?patient={patient_id}'
    use_cases = ('EHR',)


@register
class MedicationDispenseTest(ResourceTestMixin, BaseTest):
    slug = 'medication-dispense'
    resource_type = 'MedicationDispense?patient={patient_id}'
    use_cases = ('EHR',)


@register
class MedicationOrderTest(ResourceTestMixin, BaseTest):
    slug = 'medication-order'
    resource_type = 'MedicationOrder?patient={patient_id}'
    use_cases = ('EHR',)


@register
class MedicationRequestTest(ResourceTestMixin, BaseTest):
    slug = 'medication-request'
    resource_type = 'MedicationRequest?patient={patient_id}'
    use_cases = ('EHR',)


@register
class MedicationStatementTest(ResourceTestMixin, BaseTest):
    slug = 'medication-statement'
    resource_type = 'MedicationStatement?patient={patient_id}'
    use_cases = ('EHR',)


@register
class DocumentReferenceTest(ResourceTestMixin, BaseTest):
    slug = 'document-reference'
    resource_type = 'DocumentReference?patient={patient_id}'
    use_cases = ('EHR',)


@register
class ConditionTest(ResourceTestMixin, BaseTest):
    slug = 'condition'
    resource_type = 'Condition?patient={patient_id}'
    use_cases = ('EHR',)


@register
class ProcedureTest(ResourceTestMixin, BaseTest):
    slug = 'prodedure'
    resource_type = 'Procedure?patient={patient_id}'
    use_cases = ('EHR',)


@register
class SmokingStatusTest(ResourceTestMixin, BaseTest):
    slug = 'smoking-status'
    resource_type = 'Observation?code=http://loinc.org%7C72166-2&patient={patient_id}'
    use_cases = ('EHR',)


@register
class VitalSignsTest(ResourceTestMixin, BaseTest):
    slug = 'vital-signs'
    resource_type = 'Observation?category=vital-signs&patient={patient_id}'
    use_cases = ('EHR',)
