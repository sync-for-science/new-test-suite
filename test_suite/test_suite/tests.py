from collections import defaultdict, OrderedDict
import json
from urllib import parse

from django.db import models
import jsonschema
import requests

from test_suite.browser import Browser, Requester
from test_suite import schemas


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

        self.requester = Requester()

    def fetch_fhir_resource(self, path, headers=None):
        if not headers:
            headers = dict()
        uri = f'{self.base_uri}/{path}'
        response = self.requester.get(uri, headers=headers)
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
            response = self.requester.post(uri, json=resource, headers={'Accept': 'application/json'})
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

    def test_profiles(self, resource):
        """Validate the resource against any associated profile."""
        # TODO: add class attribute with a schema against which to validate
        for name, schema in self.profiles:
            validator = jsonschema.Draft4Validator(schema)
            errors = '; '.join(
                error.message
                for error in validator.iter_errors(resource)
            )
            if not errors:
                result = (None, PASS)
            else:
                result = (errors, WARN)
            self.results[f'Resources fulfill the {name} profile'] = result

    def run(self):
        resource = self.get_resource()
        self.test_valid_fhir_resource(resource)
        self.test_resolvable_references(resource)
        self.test_valid_codes(resource)
        self.test_profiles(resource)


class BehaviorTestMixin:
    def __init__(self, **kwargs):
        self.auth_config = kwargs.pop('auth_config')
        self.state = kwargs.pop('state')

        self._browser = Browser(self.auth_config)
        super().__init__(**kwargs)

    def exchange(self, params, method=None):
        if method is None:
            method = self.requester.post

        auth = (
            self.auth_config['client_id'],
            self.auth_config['client_secret']
        )
        response = method(
            self.auth_config['token_uri'],
            auth=auth,
            data=params
        )
        return response

    def assert_exchange_failure(self, params, exchange_twice=False, **overrides):
        method = overrides.pop('method', self.requester.post)
        params = apply_overrides(params, overrides)

        response = self.exchange(params, method)
        if exchange_twice:
            response = self.exchange(params, method)

        if response.status_code == 200:
            return ('Response code should not be 200', FAIL)
        else:
            return (None, PASS)

    def assert_exchange_success(self, params, **overrides):
        params = apply_overrides(params, overrides)
        response = self.exchange(params)
        errors = list()
        if response.status_code != 200:
            errors.append('Status code should be 200')
        else:
            errors.extend(
                f'JSON response should contain `{key}`'
                for key in ('access_token', 'token_type', 'scope', 'patient')
                if key not in response.json()
            )
        if errors:
            return ('; '.join(errors), FAIL)
        else:
            return (None, PASS)


@register
class PatientDemographicsTest(ResourceTestMixin, BaseTest):
    slug = 'patient-demographics'
    resource_type = 'Patient/{patient_id}'
    use_cases = ('EHR', 'Financial')
    profiles = (('Argonaut patient', schemas.patient_argonaut), ('CMS patient', schemas.patient_cms))


@register
class AskForAuthorizationTest(BehaviorTestMixin, BaseTest):
    slug = 'ask-for-authorization'

    def assert_failure(self, *args, **kwargs):
        return self.result(False, *args, **kwargs)

    def assert_success(self, *args, **kwargs):
        return self.result(True, *args, **kwargs)

    def result(self, want_pass, params, **overrides):
        params = apply_overrides(params, overrides)
        b = Browser(self.auth_config)
        uri = b.init_authorization(params)
        success = b.run_authorization_steps(raise_error=False)
        del b

        if want_pass and not success:
            return ('The user should be able to authorize.', FAIL)
        if not want_pass and success:
            return ('The user should not be able to authorize.', FAIL)

        return (None, PASS)
    
    def run(self):
        params = {
            'response_type': 'code',
            'client_id': self.auth_config['client_id'],
            'redirect_uri': self.auth_config['redirect_uri'],
            'scope': self.auth_config['scope'],
            'state': self.state,
            'aud': self.auth_config['aud']
        }

        self.results['Missing `response_type` parameter'] = self.assert_failure(
            params,
            response_type=None
        )
        self.results['Wrong `response_type` parameter'] = self.assert_failure(
            params,
            response_type='token'
        )
        self.results['Missing `client_id` parameter'] = self.assert_failure(
            params,
            client_id=None
        )
        self.results['Wrong `client_id` parameter'] = self.assert_failure(
            params,
            client_id='example'
        )
        self.results['Missing `redirect_uri` parameter'] = self.assert_failure(
            params,
            redirect_uri=None
        )
        self.results['Wrong `redirect_uri` parameter'] = self.assert_failure(
            params,
            redirect_uri='https://example.com'
        )
        self.results['Missing `scope` parameter'] = self.assert_failure(
            params,
            scope=None
        )
        self.results['Missing `state` parameter'] = self.assert_failure(
            params,
            state=None
        )
        self.results['Long stater is accepted'] = self.assert_success(
            params,
            state='Lorem ipsum dolor sit amet, consectetur adipiscing elit. '
                'Nulla mollis libero interdum mi eleifend mollis. Phasellus '
                'velit lectus, feugiat eu turpis a, efficitur auctor leo. '
                'Praesent sed bibendum nisi, vel mollis dui. Nulla volutpat '
                'tortor in erat laoreet sodales. Nunc ex dolor, vehicula eget '
                'convallis non, volutpat a odio. Aenean nec rutrum nibh. '
                'Suspendisse fermentum sem a enim aliquet, non rhoncus dui '
                'faucibus.'
        )
        self.results['State with special characters is accepted'] = self.assert_success(
            params,
            state=r'`%2B~!@#$%^&*()-_=+[{]}\;:\'",<.>/?'
        )


@register
class ExchangeCodeForTokenTest(BehaviorTestMixin, BaseTest):
    slug = 'exchange-code-for-token'

    def get_code(self):
        b = Browser(self.auth_config)
        return b.authorize(self.state)

    def run(self):
        params = {
            'grant_type': 'authorization_code',
            'redirect_uri': self.auth_config['redirect_uri'],
        }

        self.results['Success response has all required parameters'] = self.assert_exchange_success(
            params,
            code=self.get_code()
        )
        self.results['We cannot use a "GET" request to retrieve an access token'] = self.assert_exchange_failure(
            params,
            code=self.get_code(),
            method=self.requester.get
        )
        self.results['Missing `grant_type` parameter'] = self.assert_exchange_failure(
            params,
            code=self.get_code(),
            grant_type=None
        )
        self.results['Wrong `grant_type` parameter'] = self.assert_exchange_failure(
            params,
            code=self.get_code(),
            grant_type='Hugh'
        )
        self.results['Missing `code` parameter'] = self.assert_exchange_failure(
            params,
            code=None
        )
        self.results['Wrong `code` parameter'] = self.assert_exchange_failure(
            params,
            code='WURVFXGJYTHEIZXSQXOBGSVRUDOOJXATBKT'
        )
        self.results['Missing `redirect_uri` parameter'] = self.assert_exchange_failure(
            params,
            code=self.get_code(),
            redirect_uri=None
        )
        self.results['Wrong `redirect_uri` parameter'] = self.assert_exchange_failure(
            params,
            code=self.get_code(),
            redirect_uri='https://example.com'
        )
        self.results['Use received code twice'] = self.assert_exchange_failure(
            params,
            code=self.get_code(),
            exchange_twice=True
        )


@register
class RefreshTokenTest(BehaviorTestMixin, BaseTest):
    slug = 'refresh-token'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        b = Browser(self.auth_config)
        code = b.authorize(self.state)
        params = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.auth_config['redirect_uri']
        }
        token = self.exchange(params).json()
        
        self._refresh_token = token.get('refresh_token')
        self._tmp = token

    def should_skip(self):
        skipped, reason = super().should_skip()

        if not skipped:
            if not self._refresh_token:
                skipped = True
                reason = 'No refresh token was supplied\n' + json.dumps(self._tmp)

        return skipped, reason

    def run(self):
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self._refresh_token
        }

        self.results['Success response has all required parameters'] = self.assert_exchange_success(
            params
        )
        self.results['Missing `grant_type` parameter'] = self.assert_exchange_failure(
            params,
            grant_type=None
        )
        self.results['Missing `refresh_token` parameter'] = self.assert_exchange_failure(
            params,
            refresh_token=None
        )


def apply_overrides(params, overrides):
    params = dict(params)  # copy
    for k, v in overrides.items():
        if v is None and k in params:
            del params[k]
        else:
            params[k] = v
    return params
