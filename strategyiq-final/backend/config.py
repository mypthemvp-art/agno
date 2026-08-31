from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pinecone_api_key: str = ""
    pinecone_index: str = "strategyiq-docs"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    xai_api_key: str = ""
    polygon_api_key: str = ""
    finnhub_api_key: str = ""
    coingecko_api_key: str = ""
    fmp_api_key: str = ""
    benzinga_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_elite: str = ""
    database_url: str = "postgresql+psycopg2://strategy:pass@localhost:5432/strategyiq"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change_this_64_random_chars"
    jwt_algorithm: str = "HS256"
    screener_cache_ttl: int = 900

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
