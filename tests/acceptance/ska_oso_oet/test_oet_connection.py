import logging
from os import getenv

import pytest
from pytest_bdd import given, parsers, scenario, then
from ska_db_oda.unit_of_work.restunitofwork import RESTUnitOfWork

LOGGER = logging.getLogger()

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")


@scenario(
    "features/oda_connection.feature", "OET can connect with a deployment of the ODA"
)
def test_connection():
    pass


@given("the ODA REST API is running and is connected to an empty Postgres instance")
def create_script():
    pass


@then(
    parsers.parse(
        "a request to get SBDefinition with sbd_id {sbd_id} returns a valid Not Found"
        " response"
    )
)
def execution_ends_in_expected_state(sbd_id):
    # This doesn't quite test that the OET can connect to postgres. Rather, it tests the test runner can connect.
    # This test was just added in BTN-1622 to show the chart is included properly, once the OET functionality is
    # expanded to include a call to the ODA, this test can be improved.
    uow = RESTUnitOfWork(f"http://ska-db-oda-rest-test:5000/{KUBE_NAMESPACE}/api/v1")
    with pytest.raises(KeyError):
        with uow:
            uow.sbds.get(sbd_id)
