from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    downloads_dir: Path = Path("/data/downloads")
    cortes_dir: Path = Path("/data/cortes")
    host: str = "0.0.0.0"
    port: int = 5101


settings = Settings()
