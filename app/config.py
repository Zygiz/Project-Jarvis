# loads settings from .env
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Jarvis"
    environment: str = "development"
    database_url: str
    telegram_bot_token: str
    telegram_allowed_user_ids: str = ""
    gemini_api_key: str = ""
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    timezone: str = "Europe/Vilnius"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_user_ids(self) -> set[int]:
        """Parse the comma-separated .env string into a set of ints."""
        return {
            int(part.strip())
            for part in self.telegram_allowed_user_ids.split(",")
            if part.strip()
        }


# Creating this object triggers BaseSettings to read model_config,
# open .env, and fill in the fields (falling back to defaults if missing).
settings = Settings()