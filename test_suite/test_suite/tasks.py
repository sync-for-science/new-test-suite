from functools import wraps
from collections.abc import Sequence

import celery

import test_suite.models


REDIS = 'redis://localhost:6379/0'
app = celery.Celery('tasks', broker=REDIS, backend=REDIS)

@app.task
def test_runner(test_run_id):
    test_run = test_suite.models.TestRun.objects.get(id=test_run_id)
    test_run.run()


def test_group_to_task_group(test_runs):
    """Transforms a sequence of TestRun models into a celery group to be run in
    parallel. If `test_runs` is itself a TestRun, return the wrapped test
    directly without a group.
    """
    if isinstance(test_runs, Sequence):
        return celery.group(
            test_runner.si(test_run.id)
            for test_run in test_runs
        )
    return test_runner.si(test_runs.id)


def wrap(groups):
    """Wraps a sequence of test groups in celery primitives to be run. Each
    element of `groups` should be a sequence of TestRuns to be executed in
    parallel, or a single TestRun instance.
    """
    return celery.chain(
        test_group_to_task_group(test_runs)
        for test_runs in groups
    )


def submit_tests(groups):
    """Wraps the sequence of test sequences in celery primitives and runs them."""
    runnable = wrap(groups)
    runnable()
