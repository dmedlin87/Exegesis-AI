"""User preference configuration routes for AI workflows."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from exegesis.application.facades.database import get_session
from exegesis.application.facades.settings_store import load_setting, save_setting
from exegesis.infrastructure.api.app.models.ai import (
    TheologicalLensEnum,
    UserPreferencesRequest,
    UserPreferencesResponse,
)

router = APIRouter(prefix="/settings/ai", tags=["ai-settings"])

_USER_PREFERENCES_KEY = "user_preferences"


def _load_user_preferences(session: Session) -> dict[str, object]:
    """Load user preferences from the settings store."""
    payload = load_setting(session, _USER_PREFERENCES_KEY, default={})
    if not isinstance(payload, dict):
        return {}
    return payload


def _store_user_preferences(session: Session, preferences: dict[str, object]) -> None:
    """Persist user preferences to the settings store."""
    save_setting(session, _USER_PREFERENCES_KEY, preferences)


@router.get(
    "/user-preferences",
    response_model=UserPreferencesResponse,
    response_model_exclude_none=True,
)
def get_user_preferences(
    session: Session = Depends(get_session),
) -> UserPreferencesResponse:
    """Retrieve current user preferences."""
    preferences = _load_user_preferences(session)
    theological_lens_value = preferences.get("theological_lens")

    # Default to GENERAL if not set or invalid
    theological_lens = TheologicalLensEnum.GENERAL
    if isinstance(theological_lens_value, str):
        try:
            theological_lens = TheologicalLensEnum(theological_lens_value)
        except ValueError:
            pass

    return UserPreferencesResponse(theological_lens=theological_lens)


@router.put(
    "/user-preferences",
    response_model=UserPreferencesResponse,
    response_model_exclude_none=True,
)
def update_user_preferences(
    payload: UserPreferencesRequest,
    session: Session = Depends(get_session),
) -> UserPreferencesResponse:
    """Update user preferences."""
    preferences = _load_user_preferences(session)
    update_data = payload.model_dump(exclude_unset=True)

    # Update theological_lens if provided
    if "theological_lens" in update_data:
        theological_lens = update_data["theological_lens"]
        if theological_lens is not None:
            preferences["theological_lens"] = theological_lens.value

    _store_user_preferences(session, preferences)
    return get_user_preferences(session)


__all__ = [
    "router",
    "get_user_preferences",
    "update_user_preferences",
]
