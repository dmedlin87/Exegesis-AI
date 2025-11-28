"""User settings routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from exegesis.application.facades.database import get_session
from exegesis.application.facades.settings import TheologicalLens
from exegesis.application.facades.settings_store import load_setting, save_setting
from exegesis.infrastructure.api.app.models.ai import (
    TheologicalLensRequest,
    TheologicalLensResponse,
)

router = APIRouter(prefix="/settings", tags=["settings"])

_THEOLOGICAL_LENS_KEY = "theological_lens"


@router.get(
    "/theological-lens",
    response_model=TheologicalLensResponse,
    summary="Get current theological lens setting",
)
def get_theological_lens(
    session: Session = Depends(get_session),
) -> TheologicalLensResponse:
    """Retrieve the current theological lens setting for the user."""
    lens_value = load_setting(
        session, _THEOLOGICAL_LENS_KEY, default=TheologicalLens.GENERAL.value
    )

    # Ensure the loaded value is a valid TheologicalLens
    if isinstance(lens_value, str):
        try:
            lens = TheologicalLens(lens_value)
        except ValueError:
            lens = TheologicalLens.GENERAL
    else:
        lens = TheologicalLens.GENERAL

    return TheologicalLensResponse(theological_lens=lens)


@router.put(
    "/theological-lens",
    response_model=TheologicalLensResponse,
    summary="Update theological lens setting",
)
def update_theological_lens(
    request: TheologicalLensRequest,
    session: Session = Depends(get_session),
) -> TheologicalLensResponse:
    """Update the theological lens setting for the user."""
    save_setting(session, _THEOLOGICAL_LENS_KEY, request.theological_lens.value)
    return TheologicalLensResponse(theological_lens=request.theological_lens)


__all__ = [
    "router",
    "get_theological_lens",
    "update_theological_lens",
]
