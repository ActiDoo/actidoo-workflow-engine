# starlette_fastapi/__init__.py
from authlib.integrations.base_client import OAuthError
from .apps import StarletteOAuth2App

__all__ = [
    "OAuthError",
    "StarletteOAuth2App",
]