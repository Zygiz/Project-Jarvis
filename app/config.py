#loads settings from .env
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jarvis"
    environment: str = "development"
    database_url: str
    telegram_bot_token: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Creating this object triggers BaseSettings to read model_config(This is what BaseSettings do - looks for model_config),
# open .env, and fill in the fields (falling back to defaults if missing).
settings = Settings()
