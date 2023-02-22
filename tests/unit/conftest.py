import multiprocessing
import threading

import pytest

from ska_oso_oet.procedure.application import restserver


@pytest.fixture(name="client")
def fixture_client():
    """
    Test fixture that returns a Flask application instance
    """
    app = restserver.create_app()
    app.config.update(TESTING=True)
    app.config.update(msg_src="unit tests")
    app.config.update(shutdown_event=threading.Event())
    # must create app_context for current_app to resolve correctly in SSE blueprint
    with app.app_context():
        with app.test_client() as client:
            yield client


@pytest.fixture(
    scope="module",
    params=[
        multiprocessing.get_context("spawn"),
        multiprocessing.get_context("fork"),
        multiprocessing.get_context("forkserver"),
    ],
)
def mp_fixture(request):
    """
    Test fixture that returns multiprocessing contexts.

    This fixture is used to ensure that functionality related to
    multiprocessing works correctly with each multiprocessing context, as
    different OSes use a different default multiprocessing context.
    """
    yield request.param
