from functools import partial

import requests
from acceptance.ska_oso_oet.util import OET_URL
from pytest_bdd import given, parsers, scenario, then, when
from ska_aaa_authhelpers import Role
from ska_aaa_authhelpers.test_helpers import mint_test_token

from ska_oso_oet.auth import AUDIENCE, Scopes


@scenario(
    "features/aaa.feature",
    "The Role of a user is used to authenticate requests to the Procedure domain",
)
def test_activity_with_script_requiring_sb():
    pass


@given(
    "an OET deployment",
)
def new_test_harness():
    # The setup fixture already confirms this
    pass


@when(
    parsers.parse("a {method} request is sent to {resource}"),
    target_fixture="requests_partial",
)
def build_partial_request(method, resource):
    requests_fn = {"GET": requests.get, "POST": requests.post, "PUT": requests.put}.get(
        method
    )
    return partial(requests_fn, url=f"{OET_URL}{resource}")


@when(
    parsers.parse("the request token is for a user with {role}"),
    target_fixture="response",
)
def send_request_with_token(requests_partial, role):
    role = {
        "SW_ENGINEER": Role.SW_ENGINEER,
        "MID_TELESCOPE_OPERATOR": Role.MID_TELESCOPE_OPERATOR,
        "LOW_TELESCOPE_OPERATOR": Role.LOW_TELESCOPE_OPERATOR,
        "ANY": Role.ANY,
    }.get(role)

    test_token = mint_test_token(
        audience=AUDIENCE,
        scopes={
            Scopes.ACTIVITY_READ,
            Scopes.ACTIVITY_EXECUTE,
            Scopes.PROCEDURE_EXECUTE,
        },
        roles={role},
    )
    response = requests_partial(headers={"Authorization": f"Bearer {test_token}"})
    return response


@then(parsers.parse("the response should be {status:d}"))
def assert_response_status(response, status: int):
    assert response.status_code == status
