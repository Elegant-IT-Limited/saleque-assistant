"""Jev by TypeSafe AI, used for decisions (scores, choices, yes/no) rather than language."""

from typesafe_sdk import TypeSafeClient

from app.core.config import Settings


def jev_client(settings: Settings) -> TypeSafeClient:
    key = settings.typesafe_api_key.get_secret_value() if settings.typesafe_api_key else ""
    return TypeSafeClient(api_key=key, model=settings.jev_model)
