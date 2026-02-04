from fastapi import Depends, HTTPException, status
from flagsmith import Flagsmith

from app.core.config import config


class MockFlagsmith:
    """
    A fake Flagsmith client for local development.
    Defaults to True for all flags unless specified.
    """

    def __init__(self, default_value: bool = True):
        self.default_value = default_value

    def is_feature_enabled(self, feature_name: str) -> bool:
        overrides = {
            # "sign_up": False
        }
        return overrides.get(feature_name, self.default_value)

    def get_feature_value(self, feature_name: str):
        return "true"


if config.FLAGSMITH_TOKEN:
    try:
        flagsmith = Flagsmith(
            environment_key=config.FLAGSMITH_TOKEN,
        )
    except Exception:
        flagsmith = MockFlagsmith(default_value=True)
else:
    flagsmith = MockFlagsmith(default_value=True)


def get_flags():
    """
    FastAPI Dependency.
    Returns either real environment flags or the Mock client.
    """
    try:
        if hasattr(flagsmith, "get_environment_flags"):
            return flagsmith.get_environment_flags()
        return flagsmith
    except Exception:
        return MockFlagsmith(default_value=True)


def get_user_flags(user_id: str):
    """
    Helper for identity-based flags.
    """
    if hasattr(flagsmith, "get_identity_flags"):
        return flagsmith.get_identity_flags(identifier=user_id)
    return flagsmith


def signup_enabled(flags=Depends(get_flags)):
    if not flags.is_feature_enabled("sign_up"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public signup is currently disabled. Please contact administrator.",
        )
    return True
