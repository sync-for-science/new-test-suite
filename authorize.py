import time
from urllib import parse
from uuid import uuid4

import requests

from selenium import webdriver
from selenium.webdriver.support.expected_conditions import visibility_of
from selenium.webdriver.support.ui import WebDriverWait


STEPS = [
    ('#sign-in', True),
    ('[data-patient-id=smart-1288992]', True),
    ('[data-slide=next]', True),
    ('[type=checkbox]', '''
Array.from(document.querySelectorAll('input.glyphbox')).forEach(function(el) { el.disabled = false; });
Array.from(document.querySelectorAll('input.glyphbox')).forEach(function(el) { el.checked = true; });
Array.from(document.querySelectorAll('button[data-slide=next]')).forEach(function(el) { el.disabled = false; });
Array.from(document.querySelectorAll('button[data-slide=next]'))[1].click();
    '''),
    ('#authorize', True)
]


CLIENT_ID = '890870a1-c021-4a2a-8df4-1e7113a8f5e0'
CLIENT_SECRET = '703e05fd-fec1-4b81-a699-cbb988f3c647'
REDIRECT_URI = 'https://not-a-real-site/authorized'
SCOPE = 'launch/patient patient/*.read offline_access'
AUTHORIZE_URI = 'https://portal.demo.syncfor.science/oauth/authorize'
TOKEN_URI = 'https://portal.demo.syncfor.science/oauth/token'
AUD = 'https://portal.demo.syncfor.science/api/fhir/'


class CurrentURIContains:
    def __init__(self, s):
        self._s = s

    def __call__(self, driver):
        return self._s in driver.current_url


def get_code():
    driver = webdriver.Firefox()
    driver.implicitly_wait(10)

    launch_params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPE,
        'state': uuid4(),
        'aud': AUD
    }

    authorize_url = f'{AUTHORIZE_URI}?{parse.urlencode(launch_params)}'
    driver.get(authorize_url)

    for step in STEPS:
        execute_step(driver, step)

    wait = WebDriverWait(driver, 60)
    wait.until(CurrentURIContains(REDIRECT_URI))

    url = parse.urlparse(driver.current_url)
    return parse.parse_qs(url.query)['code'][0]


def execute_step(driver, step):
    time.sleep(1)
    subject, predicate = step


    if predicate in (True, False):
        driver.find_element_by_css_selector(subject).click()
    else:
        driver.execute_script(predicate)


def get_bearer_token():
    code = get_code()
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI
    }
    response = requests.post(TOKEN_URI, auth=(CLIENT_ID, CLIENT_SECRET), data=data)
    return response.json()['access_token']


if __name__ == '__main__':
    print(get_bearer_token())
