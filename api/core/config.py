"""
Configurações da aplicação FastAPI utilizando Pydantic Settings.
Carrega variáveis de ambiente do arquivo .env centralizado.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Configurações globais da API de Imóveis."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Identificação da API
    PROJECT_NAME: str = "Real Estate Lakehouse API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Banco de Dados (PostgreSQL Neon)
    POSTGRES_USER: str = Field(default="neondb_owner")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="neondb")
    POSTGRES_SSL: str = Field(default="require")

    @property
    def async_database_url(self) -> str:
        """Gera URL de conexão assíncrona compatível com SQLAlchemy 2.0 e asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
