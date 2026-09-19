from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./raizes.db"

    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    webhook_secret: str = Field(min_length=16)

    bcrypt_rounds: int = Field(default=12, ge=4, le=16)

    pagamento_mock_callback_automatico: bool = True
    pagamento_mock_atraso_segundos: float = Field(default=0.0, ge=0)

    @property
    def documentacao_habilitada(self) -> bool:
        return self.app_env != "production"


@lru_cache
def obter_settings() -> Settings:
    return Settings()
