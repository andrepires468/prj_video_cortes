from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Valores vêm de variáveis de ambiente / api/.env. O default só vale se a env não existir."""

    model_config = SettingsConfigDict(
        env_file=_API_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    downloads_dir: Path = Path("/data/downloads")
    cortes_dir: Path = Path("/data/cortes")
    host: str = "0.0.0.0"
    port: int = 5101

    mysql_host: str = ""
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_pass: str = ""
    mysql_db: str = "videocortes"

    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_use_ssl: bool = True
    minio_region: str = "us-east-1"
    minio_bucket: str = "videocortes"
    default_usuario_id: str = ""
    jwt_secret: str = ""
    jwt_expire_days: int = 7
    auth_cookie_name: str = "vc_token"
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")
    minio_cors_origins: str = Field(default="", validation_alias="MINIO_CORS_ORIGINS")
    playback_url_expire_seconds: int = 7200

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def database_url(self) -> str:
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_pass)
        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )


settings = Settings()
