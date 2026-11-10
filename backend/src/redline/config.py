import os
from dataclasses import dataclass

DATABASE_URL_VARIABLE = "DATABASE_URL"
LOG_LEVEL_VARIABLE = "LOG_LEVEL"


@dataclass(frozen=True)
class Settings:
    """Settings the server needs to start."""

    database_url: str
    log_level: str


def read_environment_variable(name: str) -> str:
    """Return one environment variable, or raise when it is missing."""
    if name not in os.environ:
        raise RuntimeError(f"Environment variable {name} is missing")
    return os.environ[name]


def load_settings() -> Settings:
    """Read settings from the environment, failing when one is missing."""
    return Settings(
        database_url=read_environment_variable(DATABASE_URL_VARIABLE),
        log_level=read_environment_variable(LOG_LEVEL_VARIABLE),
    )
