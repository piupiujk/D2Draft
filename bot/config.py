from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    BOT_TOKEN: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    STRATZ_TOKEN: str
    OPENDOTA_BASE_URL: str = "https://api.opendota.com/api"
    LLM_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"
    STEAM_API_KEY: str = ""
    REDIS_URL: str = ""


settings = Settings()
