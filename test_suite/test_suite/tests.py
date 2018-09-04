from collections import defaultdict, OrderedDict
import json

from django.db import models
import requests


FAIL = 'failed'
WARN = 'warning'
PASS = 'passed'
SKIP = 'skipped'


# decorator which keeps tracks of defined tests:
# `REGISTRY` is a mapping of test slugs to test classes;
# `USE_CASES` is a mapping of use cases to a list of test classes, e.g. EHR
REGISTRY = dict()
USE_CASES = defaultdict(list)
def register(cls):
    REGISTRY[cls.slug] = cls

    for use_case in cls.use_cases:
        USE_CASES[use_case].append(cls)

    return cls


class TestField(models.TextField):
    """Represents a test class. Stored as the test class slug in the DB."""
    def from_db_value(self, value, expression=None, connection=None):
        if value is None:
            return value
        try:
            return REGISTRY[value]
        except KeyError:
            raise RuntimeError(f'Test "{value}" not found.')

    def to_python(self, value):
        if issubclass(value, BaseTest):
            return value
        return self.from_db_value(value)

    def get_prep_value(self, value):
        return value.slug


class BaseTest:
    """Base test class from which tests should inherit."""
    versions = ('DSTU2', 'STU3')
    use_cases = ('EHR', 'Financial', 'Security')
    test_group = None

    def __init__(self, **kwargs):
        self.instance_version = kwargs.pop('version')
        self.instance_use_cases = set(kwargs.pop('use_cases'))
        self.base_uri = kwargs.pop('base_uri').rstrip('/')

        self.resources = OrderedDict()
        self.results = OrderedDict()

    def fetch_fhir_resource(self, path, headers=None):
        if not headers:
            headers = dict()
        uri = f'{self.base_uri}/{path}'
        response = requests.get(uri, headers=headers)
        response.raise_for_status()

        data = response.json()
        self.resources[path] = data
        return data

    def should_skip(self, *args, **kwargs):
        if self.instance_version not in self.versions:
            return True, f'This test only supports version(s) {", ".join(self.versions)}'
        if not self.instance_use_cases.intersection(self.use_cases):
            return True, f'This test only supports use case(s) {", ".join(self.use_cases)}'

        return False, ''

    def run(self):
        raise NotImplemented


class ResourceTestMixin:
    """Mixin class for tests probing resources."""
    resource_type = None
    resource_name = None
    test_group = 1

    def __init__(self, **kwargs):
        self.token = kwargs.pop('bearer_token')
        self.patient_id = kwargs.pop('patient_id')
        super().__init__(**kwargs)

    def get_resource(self):
        if not self.resource_type:
            raise ValueError

        headers = {'Authorization': f'Bearer {self.token}'}
        resource_path = self.resource_type.format(patient_id=self.patient_id)
        return self.fetch_fhir_resource(resource_path, headers)

    def test_valid_fhir_resource(self, resource):
        """Validate the resource with a HAPI FHIR server."""
        # TODO: use the reference stack's server
        uri = f'http://hapi.fhir.org/baseDstu{self.instance_version[-1]}/{resource["resourceType"]}/$validate'
        try:
            response = requests.post(uri, json=resource, headers={'Accept': 'application/json'})
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

    def test_resolvable_references(self, resource):
        """Validate all the references in the resource."""
        failed_references = list()

        # TODO: replace with recursive reference finding
        reference = resource.get('reference')
        if reference:
            if reference.startswith('#'):
                matches = [
                    contained
                    for contained in resource.get('contained', list())
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

    def test_valid_codes(self, resource):
        """Validate any codes in recognized systems."""
        # TODO: implement
        self.results['All codes are valid'] = (None, PASS)

    def test_argonaut_profile(self, resource):
        """Validate the resource against an Argonaut profile."""
        # TODO: add class attribute with a schema against which to validate
        # for now, this is just an example of a warning result
        self.results[f'Resources fulfill the argonaut {self.resource_name} profile'] = (
            'Something is wrong!', WARN
        )

    def run(self):
        resource = self.get_resource()
        self.test_valid_fhir_resource(resource)
        self.test_resolvable_references(resource)
        self.test_valid_codes(resource)
        self.test_argonaut_profile(resource)


@register
class PatientDemographicsTest(ResourceTestMixin, BaseTest):
    slug = 'patient-demographics'
    resource_type = 'Patient/{patient_id}'
    use_cases = ('EHR', 'Financial')
