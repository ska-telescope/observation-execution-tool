from functools import partial

import pytest
from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_oet.auth import (
    auth_allowed_to_execute_activity,
    auth_allowed_to_execute_procedure,
    auth_allowed_to_read,
)

TestAuthContext = partial(
    AuthContext,
    user_id="TEST_USER",
    principals=set(),
    groups=set(),
    scopes=set(),
    audience="TEST_AUDIENCE",
    access_token="TEST_TOKEN",
)


@pytest.mark.parametrize(
    ("auth", "expected"),
    (
        (TestAuthContext(roles={Role.SW_ENGINEER}), True),
        (TestAuthContext(roles={Role.LOW_TELESCOPE_OPERATOR}), True),
        (TestAuthContext(roles={Role.MID_TELESCOPE_OPERATOR}), True),
        (TestAuthContext(roles={Role.ANY}), False),
    ),
)
def test_auth_allowed_to_read(auth, expected):
    assert auth_allowed_to_read(auth) == expected


@pytest.mark.parametrize(
    ("auth", "expected"),
    (
        (TestAuthContext(roles={Role.SW_ENGINEER}), True),
        (TestAuthContext(roles={Role.LOW_TELESCOPE_OPERATOR}), True),
        (TestAuthContext(roles={Role.MID_TELESCOPE_OPERATOR}), True),
        (TestAuthContext(roles={Role.ANY}), False),
    ),
)
def test_auth_allowed_to_execute_activity(auth, expected):
    assert (
        auth_allowed_to_execute_activity(auth) == expected
    )  # TODO this needs to check sbd


@pytest.mark.parametrize(
    ("auth", "expected"),
    (
        (TestAuthContext(roles={Role.SW_ENGINEER}), True),
        (TestAuthContext(roles={Role.LOW_TELESCOPE_OPERATOR}), True),
        (TestAuthContext(roles={Role.MID_TELESCOPE_OPERATOR}), True),
        (TestAuthContext(roles={Role.ANY}), False),
    ),
)
def test_auth_allowed_to_execute_procedure(auth, expected):
    assert auth_allowed_to_execute_procedure(auth) == expected
