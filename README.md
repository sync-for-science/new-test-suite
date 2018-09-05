# Getting started

#### Build and start the container, and start the redis and celery servers

    $ docker build -t new-tests .
    ...
    $ docker run --rm -it -p 8000:8000 new-tests bash
    root@302f0bc3078e:/usr/src/app# redis-server --daemonize yes
    root@302f0bc3078e:/usr/src/app# cd test_suite
    root@302f0bc3078e:/usr/src/app/test_suite# DJANGO_SETTINGS_MODULE=test_suite.settings celery worker -A test_suite.tasks -l DEBUG

#### Initialize the database and run a test suite

In another terminal:

    $ docker exec -it 302f0bc3078e bash
    root@302f0bc3078e:/usr/src/app# cd test_suite
    root@302f0bc3078e:/usr/src/app/test_suite# ./manage.py makemigrations test_suite
    ...
    root@302f0bc3078e:/usr/src/app/test_suite# ./manage.py migrate
    ...
    root@302f0bc3078e:/usr/src/app/test_suite# ./manage.py shell
    ...
    >>> token = 'OYKK58vTsvFViuCvkff5YYAoZfazlg'
    >>> from test_suite.models import *
    >>> from test_suite.tests import *
    >>> s = SuiteRun()
    >>> s.save()
    >>> f = FeatureRun(suite=s, test=PatientDemographicsTest, bearer_token=token, base_uri='http://portal.demo.syncfor.science/api/fhir', version='DSTU2', use_cases='EHR', patient_id='smart-1288992')
    >>> f.save()
    >>> s.run()
    <GroupResult: acfbf7ed-355c-4651-905f-989c6de07c75 [1892c472-540c-424f-8811-1456173da7a6]>
    >>> f.refresh_from_db()
    >>> f.status
    'running'
    >>> f.refresh_from_db()
    >>> f.status
    'finished'

To generate a new bearer token:

    root@302f0bc3078e:/usr/src/app# xvfb-run python authorize.py
    OYKK58vTsvFViuCvkff5YYAoZfazlg
