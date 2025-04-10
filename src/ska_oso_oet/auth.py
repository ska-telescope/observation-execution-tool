from enum import Enum
from functools import partial
from os import getenv

from ska_aaa_authhelpers import Requires, Role
from ska_aaa_authhelpers.test_helpers import TEST_ISSUER, TEST_PUBLIC_KEYS
from ska_oso_scripting.functions.environment import (
    is_ska_low_environment,
    is_ska_mid_environment,
)

AUDIENCE = "TODO"

# As our component tests send requests to a real deployment, they either need to receive real
# tokens signed with Microsoft's private key, or some test tokens that we mint in the test using
# our own test private key. To then verify these test tokens, we need to deploy the OET using the
# corresponding test public keys
#
# This should never be true in production as it will allow test tokens to be authenticated by the OET.
# (The tokens should still be authenticated at the ingress gateway with the real keys so this is not a complete back door)
if getenv("PIPELINE_TESTS_DEPLOYMENT", "false") == "true":
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
    # Currently this will never be reached as is_ska_mid_environment
    # is the negation of is_ska_low_environment


OPERATOR_ROLE_FOR_TELESCOPE = operator_role_for_telescope()
