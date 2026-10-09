import os
from typing import Annotated

from fastapi import Depends, Header

import errors
from errors import APIError

# admin placeholder
# Stands in for real auth until implemented.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-admin-token")


def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    if x_admin_token is None:
        raise APIError(401, errors.UNAUTHENTICATED, "authentication required")
    if x_admin_token != ADMIN_TOKEN:
        raise APIError(403, errors.FORBIDDEN, "admin access required")


admin = Depends(require_admin)
