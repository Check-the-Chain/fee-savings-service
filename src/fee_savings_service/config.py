from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    hyperliquid_info_url: str = Field(
        default="https://api.hyperliquid.xyz/info",
        alias="HYPERLIQUID_INFO_URL",
    )
    request_timeout_seconds: float = Field(default=10.0, alias="REQUEST_TIMEOUT_SECONDS")
    default_max_fill_requests: int = Field(default=3, alias="DEFAULT_MAX_FILL_REQUESTS")


settings = Settings()
