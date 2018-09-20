from test_suite.web import Browser
from test_suite.tests.core import BaseTest, FAIL, PASS, SKIP, WARN, register


class BehaviorTestMixin:
    def __init__(self, **kwargs):
        self.auth_config = kwargs.pop('auth_config')
        self.state = kwargs.pop('state')

        # TODO: move this somewhere else and make it more robust
        try:
            conformance_uris = {
                ex['url']: ex['valueUri']
                for ex in self.conformance['rest'][0]['security']['extension'][0]['extension']
            }
        except (KeyError, IndexError):
            raise

        self.auth_config['aud'] = self.base_fhir_uri
        self.auth_config['authorize_uri'] = conformance_uris['authorize']
        self.auth_config['token_uri'] = conformance_uris['token']

        self.browser = Browser(self.auth_config)
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
        self.results['Long `state` parameter'] = self.assert_success(
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
        self.results['Special characters in `state` parameter'] = self.assert_success(
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
        
        self.refresh_token = token.get('refresh_token')

    def should_skip(self):
        skipped, reason = super().should_skip()

        if not skipped:
            if not self.refresh_token:
                skipped = True
                reason = 'No refresh token was supplied'

        return skipped, reason

    def run(self):
        params = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
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
