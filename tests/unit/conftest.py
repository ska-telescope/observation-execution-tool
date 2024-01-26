import multiprocessing
import os
import threading
from importlib.metadata import version

import pytest

from ska_oso_oet import ui

OET_MAJOR_VERSION = version("ska-oso-oet").split(".")[0]
# Default as it uses the default namespace. When deployed to a different namespace the first part will change to that namespace.
DEFAULT_API_PATH = f"ska-oso-oet/oet/api/v{OET_MAJOR_VERSION}"
PROCEDURES_ENDPOINT = f"{DEFAULT_API_PATH}/procedures"
ACTIVITIES_ENDPOINT = f"{DEFAULT_API_PATH}/activities"


@pytest.fixture(name="base_url")
def fixture_base_url():
    url = os.environ.get("OET_URL", f"http://localhost/{DEFAULT_API_PATH}")
    return url


@pytest.fixture(name="client")
def fixture_client():
    """
    Test fixture that returns an OET Flask application instance
    """

    app = ui.create_app()
    app.config.update(TESTING=True)
    app.config.update(msg_src="unit tests")
    app.config.update(shutdown_event=threading.Event())
    # must create app_context for current_app to resolve correctly in SSE blueprint
    with app.app_context():
        with app.test_client() as client:
            yield client


@pytest.fixture(
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
