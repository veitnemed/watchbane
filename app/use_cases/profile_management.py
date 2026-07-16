"""Profile selection and deferred reset use cases for desktop callers."""

from __future__ import annotations

from storage import profile_reset, profiles


def process_pending_reset() -> dict:
    return profile_reset.process_pending_profile_reset()


def selection_required() -> bool:
    return profile_reset.profile_selection_required()


def clear_selection_required() -> None:
    profile_reset.clear_profile_selection_required()


def list_profile_descriptions() -> list[dict[str, str]]:
    return profiles.describe_profiles()


def create_profile(name: str, *, display_name: str | None = None) -> str:
    return profiles.create_profile(name, display_name=display_name)


def set_active_profile(name: str) -> None:
    profiles.set_active_profile(name)


def active_profile() -> str:
    return profiles.get_active_profile()


def request_active_profile_reset() -> None:
    profile_reset.request_full_profile_reset()


MAIN_PROFILE = profiles.MAIN_PROFILE
