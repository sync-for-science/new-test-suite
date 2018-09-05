from collections import defaultdict
from datetime import datetime
import json
import uuid

from django.db import models

import test_suite.tasks
from test_suite.tests import TestField, PASS, WARN, FAIL, SKIP


class SuiteRun(models.Model):
    """Represents a set of tests to be run for a vendor. Once this model is
    constructed, `run()` can be called to run the assembled test suite and
    populate the results.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    start = models.DateTimeField(auto_now_add=True)
    end = models.DateTimeField(null=True)

    def run(self, *args, **kwargs):
        """Groups the test by parallelization priority and then submits them to
        celery to run.
        """
        # TODO: this grouping is too complicated and probably unneeded
        self.save()
        groups = defaultdict(list)
        for feature_run in self.featurerun_set.all():
            if feature_run.test.test_group:
                groups[feature_run.test.test_group].append(feature_run)

        tests = [group for _, group in sorted(groups.items())]
        tests += groups[None]  # those with None should be run at the end, in series

        return test_suite.tasks.submit_tests(tests, *args, **kwargs)


class FeatureRun(models.Model):
    """Represents a single run of a single test (feature)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = TestField(editable=False)
    suite = models.ForeignKey('SuiteRun', on_delete=models.CASCADE, editable=False)
    status = models.TextField(choices=(
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('finished', 'Finished'),
        ('skipped', 'Skipped')
    ), default='pending')
    result = models.TextField(choices=(
        ('passed', 'Passed'),
        ('warning', 'Warning'),
        ('failed', 'Failed')
    ), null=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    message = models.TextField()

    ### context values
    base_uri = models.TextField()
    version = models.TextField()
    use_cases = models.TextField()
    bearer_token = models.TextField()
    patient_id = models.TextField()
    ###

    def run(self):
        test = self.test(
            base_uri = self.base_uri,
            version = self.version,
            use_cases = self.use_cases.split('|'),
            bearer_token = self.bearer_token,
            patient_id = self.patient_id
        )

        skipped, reason = test.should_skip()
        if skipped:
            self.status = 'skipped'
            self.message = reason
            self.save()
            return

        self.start = datetime.now()
        self.status = 'running'
        self.save()

        test.run()

        for uri, resource in test.resources.items():
            model = Resource(test=self, resource=json.dumps(resource))
            model.save()

        passing = True
        failing = False
        for idx, (scenario_name, (message, result)) in enumerate(test.results.items()):
            if result in (FAIL, WARN):
                passing = False
            if result == FAIL:
                failing = True

            model = Scenario(
                test=self,
                title=scenario_name,
                message=message,
                result=result,
                sequence=idx
            )
            model.save()

        if passing:
            self.result = 'passed'
        elif not failing:
            self.result = 'warning'
        else:
            self.result = 'failed'
        self.status = 'finished'
        self.end = datetime.now()
        self.save()


class Scenario(models.Model):
    """Represents a scenario in a test (feature), with a title and results."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = models.ForeignKey('FeatureRun', on_delete=models.CASCADE, editable=False)
    title = models.TextField()
    message = models.TextField(null=True)
    sequence = models.IntegerField()
    result = models.TextField(choices=(
        ('passed', 'Passed'),
        ('warning', 'Warning'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped')
    ))


class Resource(models.Model):
    """Represents a retrieved resource for a test run."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test = models.ForeignKey('FeatureRun', on_delete=models.CASCADE, editable=False)
    resource = models.TextField()  # FHIR resource as JSON
