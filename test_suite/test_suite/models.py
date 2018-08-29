from collections import defaultdict
import uuid

from django.db import models

import test_suite.tasks
from test_suite.tests import TestField


class SuiteRun(models.Model):
    """Represents a set of tests to be run for a vendor. Once this model is
    constructed, `run()` can be called to run the assembled test suite and
    populate the results.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(null=True)

    def run(self):
        """Groups the test by parallelization priority and then submits them to
        celery to run.
        """
        self.save()
        groups = defaultdict(list)
        for test_run in self.testrun_set.all():
            if test_run.test.test_group:
                groups[test_run.test.test_group].append(test_run)

        tests = [group for _, group in sorted(groups.items())]
        tests += groups[None]  # those with None should be run at the end, in series

        test_suite.tasks.submit_tests(tests)


class TestRun(models.Model):
    """Represents a single run of a single test."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = TestField(editable=False)
    suite = models.ForeignKey('SuiteRun', on_delete=models.CASCADE, editable=False)
    status = models.TextField(choices=(
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('finished', 'Finished')
    ), default='pending')
    result = models.TextField(choices=(
        ('passed', 'Passed'),
        ('warning', 'Warning'),
        ('failed', 'Failed')
    ), null=True)
    message = models.TextField(null=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    resource = models.ForeignKey('Resource', on_delete=models.SET_NULL, null=True)

    ### under construction
    bearer_token = models.TextField()
    patient_id = models.TextField()
    version = models.TextField()
    use_cases = models.TextField()
    ###

    def run(self):
        """Just debugging for now."""
        test = self.test(**self.__dict__)
        if test.should_run():
            self.message = test.run()
            self.save()


class Resource(models.Model):
    """Represents a retrieved resource for a test run."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.TextField()  # FHIR resource as JSON
