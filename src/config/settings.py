from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_enabled: bool = True
    cache_ttl_scrape: int = 86400
    cache_ttl_gpt: int = 3600
    cache_ttl_parse: int = 604800
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    
    # Feature Flags
    enable_scraper: bool = True
    enable_sentiment: bool = True
    enable_analyzer: bool = True
    enable_chat: bool = True
    
    # Rate Limiting
    max_scrape_docs_per_source: int = 50
    scrape_timeout_seconds: int = 30
    max_concurrent_scrapes: int = 5
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
