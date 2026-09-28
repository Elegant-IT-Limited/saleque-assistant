"""The tenant a request acts for.

Every service method takes a TenantCtx instead of a bare id, so the scope a call runs
in is always explicit in the signature and never read from a global. The product
context also carries organization_id and user_id; this service only needs the workspace.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantCtx:
    workspace_id: str
