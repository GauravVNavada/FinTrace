from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.controls.schemas import ActorContext, Role


def get_organization_id(x_organization_id: Annotated[str | None, Header()] = None) -> str:
    """Temporary development tenant context.

    Replace with authenticated session claims before any non-demo deployment.
    Never accept organization scope from a JSON request body.
    """
    if not x_organization_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return x_organization_id


def get_actor_context(
    organization_id: Annotated[str, Depends(get_organization_id)],
    x_actor_id: Annotated[str | None, Header()] = None,
    x_actor_role: Annotated[str | None, Header()] = None,
) -> ActorContext:
    """Temporary development actor context; replace with verified identity claims."""
    try:
        return ActorContext(
            organization_id=organization_id,
            actor_id=x_actor_id or "dev-analyst",
            role=Role(x_actor_role or "ANALYST"),
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid actor context") from error
