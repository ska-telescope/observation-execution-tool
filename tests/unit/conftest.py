import multiprocessing
import os
import threading
from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

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
    Test fixture that returns an OET FastAPI test client with the OET application
    """

    app = ui.create_fastapi_app()
    app.state.msg_src = "unit tests"
    app.state.sse_shutdown_event = threading.Event()
    # raise_server_exceptions can be useful for debugging, but for the tests we want to
    # see how the server handles the exceptions and wraps it into a response
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(name="async_client")
def fixture_async_client():
    app = ui.create_fastapi_app()
    app.state.msg_src = "unit tests"
    app.state.sse_shutdown_event = threading.Event()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost")


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
