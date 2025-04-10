import os
from functools import partial
from unittest import mock

from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_oet.auth import operator_role_for_telescope

TestAuthContext = partial(
    AuthContext,
    user_id="TEST_USER",
    principals=set(),
    groups=set(),
    scopes=set(),
    audience="TEST_AUDIENCE",
    access_token="TEST_TOKEN",
)


def test_correct_operator_role_set_from_telescope_env():
    with mock.patch.dict(os.environ, {"SKA_TELESCOPE": "SKA-mid"}):
        assert operator_role_for_telescope() is Role.MID_TELESCOPE_OPERATOR

    with mock.patch.dict(os.environ, {"SKA_TELESCOPE": "SKA-low"}):
        assert operator_role_for_telescope() is Role.LOW_TELESCOPE_OPERATOR
