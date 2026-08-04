"""Immutable application configuration."""

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    """Runtime settings without secrets."""

    model_config = ConfigDict(frozen=True)

    nemotron_model: str = "nvidia/nemotron-3-nano-30b-a3b"
    session_idle_seconds: int = 3600
    data_path: str = "/app/data/sample_molecules.csv"


SETTINGS = Settings()
