"""Session tokens.

The webapp sends `Authorization: Bearer <workspace_id>.<hmac>`. In the product this is
the JWT access token issued by the auth module; the reference build signs a minimal
HMAC token so the tests need no identity provider. The rule that matters is the same
either way: the workspace is taken from a verified token, never from the request body.
"""

import hashlib
import hmac


def sign_session(workspace_id: str, secret: bytes) -> str:
    return workspace_id + "." + hmac.new(secret, workspace_id.encode(), hashlib.sha256).hexdigest()


def verify_session(token: str, secret: bytes) -> str | None:
    """Return the workspace id if the token is genuine, otherwise None."""
    workspace_id, _, _ = token.partition(".")
    if not workspace_id:
        return None
    # compare_digest, not ==, so the check takes the same time for every wrong token
    if not hmac.compare_digest(token, sign_session(workspace_id, secret)):
        return None
    return workspace_id
