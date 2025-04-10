from enum import Enum
from functools import partial

from ska_aaa_authhelpers import Requires, Role
from ska_aaa_authhelpers.test_helpers import TEST_ISSUER, TEST_PUBLIC_KEYS
from ska_oso_scripting.functions.environment import (
    is_ska_low_environment,
    is_ska_mid_environment,
)

AUDIENCE = "TODO"

if (
    True
):  # TODO do not merge this - if we are going with this approach for the ITs we should set this in a way that makes it as difficult as possible to do in a real deployment
    Permissions = partial(
        Requires, audience=AUDIENCE, keys=TEST_PUBLIC_KEYS, issuer=TEST_ISSUER
    )
else:
    Permissions = partial(Requires, audience=AUDIENCE)


class Scopes(str, Enum):
    ACTIVITY_READ = "activity:read"
    ACTIVITY_EXECUTE = "activity:execute"
    PROCEDURE_EXECUTE = "procedure:execute"


def operator_role_for_telescope():
    if is_ska_low_environment():
        return Role.LOW_TELESCOPE_OPERATOR
    if is_ska_mid_environment():
        return Role.MID_TELESCOPE_OPERATOR

    # Currently this will never be reached as is_ska_mid_environment is the negation of is_ska_low_environment
    raise ValueError(
        "SKA_TELESCOPE environment variable must be set to 'SKA-mid' or 'SKA-low'"
    )


OPERATOR_ROLE_FOR_TELESCOPE = operator_role_for_telescope()
