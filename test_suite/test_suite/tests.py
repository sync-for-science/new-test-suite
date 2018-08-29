from collections import defaultdict

from django.db import models
import requests


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
        uri = f'{self.base_uri}/{resource_path}'
        response = requests.get(uri, headers=headers)
        response.raise_for_status()

        return response.json()

    def run(self):
        return 'Test has run', self.get_resource()


@register
class PatientDemographicsTest(ResourceTestMixin, BaseTest):
    slug = 'patient-demographics'
    resource_type = 'Patient/{patient_id}'
    use_cases = ('EHR', 'Financial')
