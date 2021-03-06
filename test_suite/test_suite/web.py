from collections import OrderedDict
import json
from time import sleep
from urllib import parse
from uuid import uuid4

import requests  # ?

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait


class Browser:
    def __init__(self, config):
        self._config = config
        self._driver = webdriver.Firefox()
        self._driver.implicitly_wait(10)

    def __del__(self):
        self._driver.close()

    def init_authorization(self, params):
        authorize_uri = f'{self._config["authorize_uri"]}?{parse.urlencode(params)}'
        self._driver.get(authorize_uri)
        return self._driver.current_url

    def run_authorization_steps(self, raise_error=True):
        try:
            for step in self._config['authorization_steps']:
                self.execute_step(step)
        except WebDriverException:
            if raise_error:
                raise
            else:
                return False
        return True

    def authorize(self, state, params=None):
        if params is None:
            params = self.get_default_params(state)

        self.init_authorization(params)
        self.run_authorization_steps()

        wait = WebDriverWait(self._driver, 60)
        wait.until(lambda d: self._config['redirect_uri'] in d.current_url)

        url = parse.urlparse(self._driver.current_url)
        return parse.parse_qs(url.query)['code'][0]

    def execute_step(self, step):
        sleep(1)

        action, target, data = step
        if action == 'click':
            self._driver.find_element_by_css_selector(target).click()
        elif action == 'send_keys':
            self._driver.find_element_by_css_selector(target).send_keys(data)
        elif action == 'script':
            self._driver.execute_script(data)

    def get_default_params(self, state):
        return {
            'response_type': 'code',
            'client_id': self._config['client_id'],
            'redirect_uri': self._config['redirect_uri'],
            'scope': self._config['scope'],
            'state': state,
            'aud': self._config['aud']
        }


class Requester:
    def __init__(self):
        self._messages = list()

    def get(self, *args, **kwargs):
        return self._request(requests.get, *args, **kwargs)

    def post(self, *args, **kwargs):
        return self._request(requests.post, *args, **kwargs)

    def _request(self, func, *args, **kwargs):
        response = func(*args, **kwargs)
        self._messages.append(request_to_dict(response.request))
        self._messages.append(response_to_dict(response))

        return response

    def to_json(self):
        return json.dumps(self._messages)


def request_to_dict(request):
    # request.body is str when `data` is used and bytes when `json` is used :(
    body = request.body
    if body and isinstance(body, bytes):
        body = body.decode('utf-8')

    return {
        'type': 'request',
        'method': request.method,
        'url': request.url,
        'headers': dict(request.headers),
        'body': body
    }


def response_to_dict(response):
    return {
        'type': 'response',
        'status': response.status_code,
        'headers': dict(response.headers),
        'body': response.text
    }
