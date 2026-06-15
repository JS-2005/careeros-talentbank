from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # Job search / matching performance controls
    JOB_SEARCH_MAX_RESULTS: int = int(os.getenv("JOB_SEARCH_MAX_RESULTS", "12"))
    JOB_SEARCH_MAX_ROLES: int = int(os.getenv("JOB_SEARCH_MAX_ROLES", "3"))
    SERPAPI_TIMEOUT_SECONDS: int = int(os.getenv("SERPAPI_TIMEOUT_SECONDS", "25"))
    JOB_SEARCH_DATE_CHIP: str = os.getenv("JOB_SEARCH_DATE_CHIP", "date_posted:month")
    FAST_MATCH_TOP_N_FOR_LLM: int = int(os.getenv("FAST_MATCH_TOP_N_FOR_LLM", "0"))
    PINECONE_TIMEOUT_SECONDS: int = int(os.getenv("PINECONE_TIMEOUT_SECONDS", "20"))

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
