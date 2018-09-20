from collections import defaultdict, OrderedDict
import json

from django.db import models

from test_suite.web import Requester


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
        self.base_fhir_uri = kwargs.pop('base_fhir_uri')

        self.resources = OrderedDict()
        self.results = OrderedDict()

        self.requester = Requester()

    def fetch_fhir_resource(self, path, headers=None):
        if not headers:
            headers = dict()
        uri = f'{self.base_uri}/{path}'
        response = self.requester.get(uri, headers=headers)
        if response.status_code != 200:
            return None

        data = response.json()
        self.resources[path] = data
        return data

    def should_skip(self, *args, **kwargs):
        if self.instance_version not in self.versions:
            return True, f'This test only supports version(s) {", ".join(self.versions)}'
        if not self.instance_use_cases.intersection(self.use_cases):
            return True, f'This test only supports use case(s) {", ".join(self.use_cases)}'

        response = self.requester.get(f'{self.base_fhir_uri}metadata')
        if response.status_code != 200:
            return True, "The server's conformance statement could not be retrieved"
        self.conformance = response.json()

        return False, ''

    def run(self):
        raise NotImplemented
