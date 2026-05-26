# Re-export from the shared config package so existing imports keep working.
# New code should import directly from packages.config.settings.
from packages.config.settings import Settings, get_settings  # noqa: F401

__all__ = ["Settings", "get_settings"]
