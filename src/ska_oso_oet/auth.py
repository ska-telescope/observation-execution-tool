from enum import Enum
from functools import partial

from ska_aaa_authhelpers import AuthContext, Requires, Role
from ska_aaa_authhelpers.test_helpers import TEST_ISSUER, TEST_PUBLIC_KEYS

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


def auth_allowed_to_read(auth: AuthContext) -> bool:
    ALLOWED_ROLES = {
        Role.SW_ENGINEER,
        Role.LOW_TELESCOPE_OPERATOR,
        Role.MID_TELESCOPE_OPERATOR,
    }

    if ALLOWED_ROLES.intersection(auth.roles):
        return True

    return False


def auth_allowed_to_execute_procedure(auth: AuthContext) -> bool:
    ALLOWED_ROLES = {
        Role.SW_ENGINEER,
        Role.LOW_TELESCOPE_OPERATOR,
        Role.MID_TELESCOPE_OPERATOR,
    }

    if ALLOWED_ROLES.intersection(auth.roles):
        return True

    return False


def auth_allowed_to_execute_activity(auth: AuthContext) -> bool:
    ALLOWED_ROLES = {
        Role.SW_ENGINEER,
        Role.LOW_TELESCOPE_OPERATOR,
        Role.MID_TELESCOPE_OPERATOR,
    }

    if ALLOWED_ROLES.intersection(auth.roles):
        return True

    return False
