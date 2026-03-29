from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://meteruser:meteruser@localhost/meterdb"
    database_url_sync: str = "postgresql://meteruser:meteruser@localhost/meterdb"
    redis_url: str = "redis://localhost:6379/0"
    ree_token: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
